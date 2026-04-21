from dataclasses import dataclass


@dataclass(frozen=True)
class KpiTargets:
    # These are the working KPI targets we want each simulated profile to meet.
    wifi_band: str = "5 GHz"
    e2e_latency_ms: float = 600.0
    max_data_rate_mbps: float = 2.1
    bearer_switch_time_ms: float = 600.0
    bearer_switch_quality: str = "Gap Free"
    xpan_transition_time_min_ms: float = 1500.0
    xpan_transition_time_max_ms: float = 2500.0
    min_rssi_dbm: float = -65.0


@dataclass(frozen=True)
class SimulationConfig:
    # The simulator runs as a coarse control loop rather than a packet-level
    # network simulator so we can iterate quickly on handover logic.
    duration_s: float = 30.0
    step_ms: int = 10
    packet_interval_ms: int = 10
    packet_deadline_ms: int = 60
    base_buffer_ms: int = 50
    prewarm_steps: int = 15
    overlap_steps: int = 10
    predictive_switch_hold_steps: int = 2
    p2p_switch_threshold: float = 0.24
    prewarm_threshold: float = 0.22
    le_base_power_mw: float = 28.0
    p2p_base_power_mw: float = 40.0
    whc_standby_power_mw: float = 70.0
    whc_active_power_mw: float = 220.0
    dual_overlap_extra_power_mw: float = 40.0
    kpis: KpiTargets = KpiTargets()
