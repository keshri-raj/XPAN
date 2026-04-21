import math

from sim.audio import AudioStream
from sim.config import SimulationConfig
from sim.controller import ServiceAwareController, XpanPredictiveController, XpanReactiveController
from sim.environment import build_scenarios
from sim.handover import HandoverEngine
from sim.link_models import LELinkModel, P2PLinkModel, WHCLinkModel
from sim.metrics import SimulationMetrics
from sim.power import build_power_strategies


def _rssi_like_to_dbm(rssi_like: float, link_name: str) -> float:
    if link_name == "le":
        return -90.0 + 60.0 * rssi_like
    if link_name == "p2p":
        return -86.0 + 48.0 * rssi_like
    return -82.0 + 42.0 * rssi_like


def _evaluate_kpis(config: SimulationConfig, summary: dict[str, float]) -> dict[str, str]:
    kpis = config.kpis
    wifi_band_required = not (summary["service_type"] == "voice_call" or summary["phone_low_power"])
    checks = {
        "wifi_band": "PASS" if (not wifi_band_required) or summary["active_band"] == kpis.wifi_band else "FAIL",
        "e2e_latency": "PASS" if summary["average_latency_ms"] <= kpis.e2e_latency_ms else "FAIL",
        "max_data_rate": "PASS" if summary["peak_data_rate_mbps"] >= kpis.max_data_rate_mbps else "FAIL",
        "bearer_switch_time": "PASS"
        if summary["handovers"] == 0.0 or 0.0 < summary["bearer_switch_time_ms"] <= kpis.bearer_switch_time_ms
        else "FAIL",
        "bearer_switch_quality": "PASS"
        if summary["handover_target"] == "none" or summary["gap_free"] >= 1.0
        else "FAIL",
        "whole_home_transition_time": "PASS"
        if summary["handover_target"] == "none"
        or kpis.xpan_transition_time_min_ms <= summary["transition_time_ms"] <= kpis.xpan_transition_time_max_ms
        else "FAIL",
        "rssi": "PASS" if summary["min_active_rssi_dbm"] >= kpis.min_rssi_dbm else "FAIL",
    }
    return checks


def _delivered_on_time(
    success_prob: float,
    latency_ms: float,
    jitter_ms: float,
    deadline_ms: int,
    step: int,
    overlap: bool,
    delivery_margin_delta: float,
) -> bool:
    # The overlap bonus is a simple way to model that dual-bearer make-before-break
    # should slightly improve delivery margin during the switch window.
    signal_variation = 0.08 * math.sin(step / 17.0) + 0.05 * math.cos(step / 11.0)
    if overlap:
        signal_variation += 0.08
    delivery_margin = success_prob + signal_variation + delivery_margin_delta
    effective_delay = latency_ms + jitter_ms - (6.0 if overlap else 0.0)
    return delivery_margin >= 0.88 and effective_delay <= deadline_ms


def _step_energy_mj(
    config: SimulationConfig,
    active_link: str,
    prewarmed: bool,
    overlap: bool,
    step_ms: int,
    active_power_scale: float,
    standby_power_scale: float,
) -> float:
    # Energy is intentionally approximate; it is meant for policy comparison,
    # not silicon-accurate power estimation.
    power_mw = config.le_base_power_mw if active_link == "le" else config.p2p_base_power_mw * active_power_scale
    if prewarmed:
        power_mw += config.whc_standby_power_mw * standby_power_scale
    if active_link == "whc":
        power_mw += config.whc_active_power_mw * active_power_scale
    if overlap:
        power_mw += config.dual_overlap_extra_power_mw
    return power_mw * step_ms / 1000.0


def _step_energy_breakdown(
    config: SimulationConfig,
    active_link: str,
    prewarmed: bool,
    overlap: bool,
    step_ms: int,
    active_power_scale: float,
    standby_power_scale: float,
) -> dict[str, float]:
    # Break energy into components so we can compare why one policy costs more
    # than another, not just how much total energy it spent.
    energies = {
        "le_energy_mj": 0.0,
        "p2p_energy_mj": 0.0,
        "whc_active_energy_mj": 0.0,
        "whc_standby_energy_mj": 0.0,
        "overlap_energy_mj": 0.0,
    }
    if active_link == "le":
        energies["le_energy_mj"] = config.le_base_power_mw * step_ms / 1000.0
    else:
        energies["p2p_energy_mj"] = config.p2p_base_power_mw * active_power_scale * step_ms / 1000.0
    if prewarmed:
        energies["whc_standby_energy_mj"] = config.whc_standby_power_mw * standby_power_scale * step_ms / 1000.0
    if active_link == "whc":
        energies["whc_active_energy_mj"] = config.whc_active_power_mw * active_power_scale * step_ms / 1000.0
    if overlap:
        energies["overlap_energy_mj"] = config.dual_overlap_extra_power_mw * step_ms / 1000.0
    return energies


def run_simulation(
    profile_name: str,
    scenario_name: str = "walk_away",
    power_strategy_name: str = "always_on",
) -> dict[str, float]:
    config = SimulationConfig()
    scenarios = {scenario.name: scenario for scenario in build_scenarios()}
    if scenario_name not in scenarios:
        raise ValueError(f"Unknown scenario: {scenario_name}")
    scenario = scenarios[scenario_name]
    power_strategies = build_power_strategies()
    if power_strategy_name not in power_strategies:
        raise ValueError(f"Unknown power strategy: {power_strategy_name}")
    power_strategy = power_strategies[power_strategy_name]
    le_model = LELinkModel()
    p2p_model = P2PLinkModel()
    whc_model = WHCLinkModel()
    audio = AudioStream(config.base_buffer_ms, config.packet_interval_ms)
    metrics = SimulationMetrics()

    controller = None
    handover = None
    initial_link = "le"
    handover_target = "none"
    active_service_type = "music"
    phone_low_power = False
    if profile_name == "normal_buds":
        initial_link = "le"
    elif profile_name == "xpan_reactive":
        # XPAN starts on direct P2P and falls back to WHC only after visible degradation.
        initial_link = "p2p"
        handover_target = "whc"
        controller = XpanReactiveController()
    elif profile_name == "xpan_predictive":
        # Predictive XPAN tries to prepare WHC early enough to keep P2P->WHC gap-free.
        initial_link = "p2p"
        handover_target = "whc"
        controller = XpanPredictiveController(
            prewarm_threshold=config.prewarm_threshold,
            switch_threshold=config.p2p_switch_threshold,
            hold_steps=config.predictive_switch_hold_steps,
            return_hold_steps=config.return_switch_hold_steps,
            predictive_horizon_steps=config.predictive_horizon_steps,
            predictive_gain_threshold=config.predictive_gain_threshold,
            predictive_prewarm_gain_threshold=config.predictive_prewarm_gain_threshold,
            p2p_return_success_threshold=config.p2p_return_success_threshold,
            p2p_return_distance_m=config.p2p_return_distance_m,
            whc_return_hysteresis_margin=config.whc_return_hysteresis_margin,
        )
    elif profile_name == "xpan_service_aware":
        initial_link = "p2p"
        controller = ServiceAwareController(
            prewarm_threshold=config.prewarm_threshold,
            switch_threshold=config.p2p_switch_threshold,
            hold_steps=config.predictive_switch_hold_steps,
            return_hold_steps=config.return_switch_hold_steps,
            predictive_horizon_steps=config.predictive_horizon_steps,
            predictive_gain_threshold=config.predictive_gain_threshold,
            predictive_prewarm_gain_threshold=config.predictive_prewarm_gain_threshold,
            p2p_return_success_threshold=config.p2p_return_success_threshold,
            p2p_return_distance_m=config.p2p_return_distance_m,
            whc_return_hysteresis_margin=config.whc_return_hysteresis_margin,
        )
    else:
        raise ValueError(f"Unknown profile: {profile_name}")

    handover = HandoverEngine(config, initial_link)

    total_latency = 0.0
    total_rssi_dbm = 0.0
    min_rssi_dbm = 0.0
    total_data_rate_mbps = 0.0
    peak_data_rate_mbps = 0.0
    total_awake_ratio = 0.0
    prewarm_start_step: int | None = None
    switch_step: int | None = None
    switch_interruption_ms = 0.0
    prewarm_episode_steps = 0
    prewarm_episode_committed = False
    lead_times_ms: list[float] = []
    previous_link = initial_link
    previous_handover_step: int | None = None
    previous_handover_from = initial_link
    previous_handover_to = initial_link
    steps = int(config.duration_s * 1000 / config.step_ms)
    for step in range(steps):
        time_s = step * config.step_ms / 1000.0
        env = scenario.state_at(time_s)
        active_service_type = env.service_type
        phone_low_power = env.phone_low_power
        le = le_model.quality(env)
        p2p = p2p_model.quality(env)
        whc = whc_model.quality(env)

        if controller is None:
            status = handover.status
        else:
            decision = controller.decide(handover.status.active_link, le, p2p, whc, env)
            status = handover.update(decision)
        if status.whc_prewarmed_steps > 0:
            prewarm_episode_steps += 1
        elif prewarm_episode_steps > 0:
            if not prewarm_episode_committed:
                metrics.unnecessary_prewarm_events += 1
            prewarm_episode_steps = 0
            prewarm_episode_committed = False
            prewarm_start_step = None
        if controller is not None and decision.prewarm_whc and prewarm_start_step is None and handover.status.active_link == "p2p":
            prewarm_start_step = step
        if switch_step is None and status.active_link == "whc":
            switch_step = step
        if status.active_link != previous_link:
            handover_from = previous_link
            handover_to = status.active_link
            if handover_from == "p2p" and handover_to == "whc":
                prewarm_episode_committed = True
                if prewarm_start_step is not None:
                    lead_times_ms.append((step - prewarm_start_step) * config.step_ms)
                if p2p.success_prob > 0.94 and p2p.latency_ms + p2p.jitter_ms < 20.0:
                    metrics.early_switches += 1
                if status.overlap_steps_remaining == 0 or p2p.success_prob < 0.8:
                    metrics.late_switches += 1
                prewarm_start_step = None
            if (
                previous_handover_step is not None
                and step - previous_handover_step <= config.ping_pong_window_steps
                and handover_from == previous_handover_to
                and handover_to == previous_handover_from
            ):
                metrics.ping_pong_count += 1
            previous_handover_step = step
            previous_handover_from = handover_from
            previous_handover_to = handover_to
            previous_link = status.active_link

        if status.active_link == "le":
            active = le
        elif status.active_link == "p2p":
            active = p2p
        else:
            active = whc
        overlap = status.overlap_steps_remaining > 0
        power_adjustments = power_strategy.adjustments(
            status.active_link,
            status.whc_prewarmed_steps > 0,
            overlap,
            env,
            audio.status.buffered_ms,
        )
        active_rssi_dbm = _rssi_like_to_dbm(active.rssi_like, active.name)
        active_data_rate_mbps = active.data_rate_mbps
        delivered = _delivered_on_time(
            active.success_prob,
            active.latency_ms + power_adjustments.extra_latency_ms,
            active.jitter_ms + power_adjustments.extra_jitter_ms,
            config.packet_deadline_ms,
            step,
            overlap,
            power_adjustments.delivery_margin_delta,
        )
        interruption_before = audio.status.interruption_ms
        audio.tick(delivered, config.step_ms)
        total_latency += active.latency_ms + active.jitter_ms + power_adjustments.extra_latency_ms + power_adjustments.extra_jitter_ms
        total_rssi_dbm += active_rssi_dbm
        min_rssi_dbm = active_rssi_dbm if step == 0 else min(min_rssi_dbm, active_rssi_dbm)
        total_data_rate_mbps += active_data_rate_mbps
        peak_data_rate_mbps = max(peak_data_rate_mbps, active_data_rate_mbps)
        total_awake_ratio += power_adjustments.awake_ratio
        metrics.energy_mj += _step_energy_mj(
            config,
            status.active_link,
            status.whc_prewarmed_steps > 0,
            overlap,
            config.step_ms,
            power_adjustments.active_power_scale,
            power_adjustments.standby_power_scale,
        )
        energy_breakdown = _step_energy_breakdown(
            config,
            status.active_link,
            status.whc_prewarmed_steps > 0,
            overlap,
            config.step_ms,
            power_adjustments.active_power_scale,
            power_adjustments.standby_power_scale,
        )
        metrics.le_energy_mj += energy_breakdown["le_energy_mj"]
        metrics.p2p_energy_mj += energy_breakdown["p2p_energy_mj"]
        metrics.whc_active_energy_mj += energy_breakdown["whc_active_energy_mj"]
        metrics.whc_standby_energy_mj += energy_breakdown["whc_standby_energy_mj"]
        metrics.overlap_energy_mj += energy_breakdown["overlap_energy_mj"]
        if status.whc_prewarmed_steps > 0:
            metrics.whc_prewarm_time_ms += config.step_ms
        if status.active_link == "whc":
            metrics.whc_active_time_ms += config.step_ms
        if overlap:
            metrics.overlap_time_ms += config.step_ms
        if switch_step is not None and step <= switch_step + config.overlap_steps:
            switch_interruption_ms += audio.status.interruption_ms - interruption_before

    metrics.handovers = handover.status.handovers
    metrics.cold_switches = handover.status.cold_switches
    metrics.interruptions_ms = audio.status.interruption_ms
    metrics.underruns = audio.status.underruns
    metrics.delivered_packets = audio.status.delivered_packets
    metrics.lost_packets = audio.status.lost_packets
    metrics.average_latency_ms = total_latency / steps
    metrics.average_data_rate_mbps = total_data_rate_mbps / steps
    metrics.peak_data_rate_mbps = peak_data_rate_mbps
    metrics.min_active_rssi_dbm = min_rssi_dbm
    metrics.average_active_rssi_dbm = total_rssi_dbm / steps
    metrics.average_awake_ratio = total_awake_ratio / steps if steps else 1.0
    metrics.average_power_mw = metrics.energy_mj / config.duration_s if config.duration_s else 0.0
    if metrics.delivered_packets:
        metrics.energy_per_delivered_packet_uj = (metrics.energy_mj * 1000.0) / metrics.delivered_packets
    if switch_step is not None:
        # Switch time is the short bearer cutover window; transition time is the
        # longer XPAN migration interval from first prewarm to final commit.
        metrics.bearer_switch_time_ms = config.overlap_steps * config.step_ms if handover.status.cold_switches == 0 else config.step_ms
        if prewarm_start_step is not None:
            metrics.transition_time_ms = (switch_step - prewarm_start_step) * config.step_ms
    elif metrics.handovers > 0:
        metrics.bearer_switch_time_ms = config.step_ms
    metrics.gap_free = switch_interruption_ms <= 0.0 and handover.status.cold_switches == 0
    if prewarm_episode_steps > 0 and not prewarm_episode_committed:
        metrics.unnecessary_prewarm_events += 1
    if lead_times_ms:
        metrics.average_prediction_lead_time_ms = sum(lead_times_ms) / len(lead_times_ms)
    summary = metrics.summary()
    summary["profile"] = profile_name
    summary["scenario"] = scenario_name
    summary["power_strategy"] = power_strategy_name
    summary["service_type"] = active_service_type
    summary["phone_low_power"] = float(phone_low_power)
    summary["active_band"] = active.band
    summary["initial_link"] = initial_link
    summary["handover_target"] = handover_target
    summary["kpi_checks"] = _evaluate_kpis(config, summary)
    return summary


def main() -> None:
    print("XPAN Bearer Simulation")
    print("----------------------")
    for scenario in build_scenarios():
        print(f"{scenario.name}:")
        for profile_name in ("normal_buds", "xpan_reactive", "xpan_predictive", "xpan_service_aware"):
            strategy_names = ("always_on",) if profile_name == "normal_buds" else (
                "always_on",
                "static_twt",
                "adaptive_twt",
                "predictive_prewake",
            )
            for power_strategy_name in strategy_names:
                results = run_simulation(profile_name, scenario.name, power_strategy_name)
                print(f"  {profile_name} [{power_strategy_name}]:")
                for key, value in results.items():
                    if key == "kpi_checks":
                        print("    kpi_checks:")
                        for kpi_name, status in value.items():
                            print(f"      {kpi_name}: {status}")
                    else:
                        print(f"    {key}: {value}")


if __name__ == "__main__":
    main()
