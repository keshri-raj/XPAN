from collections import deque
from dataclasses import dataclass

from sim.environment import EnvironmentState
from sim.link_models import LinkQuality


@dataclass
class ControllerDecision:
    prewarm_whc: bool = False
    target_link: str | None = None
    force_switch: bool = False


class XpanReactiveController:
    def decide(
        self,
        current_link: str,
        le: LinkQuality,
        p2p: LinkQuality,
        whc: LinkQuality,
        env: EnvironmentState,
    ) -> ControllerDecision:
        del current_link, le
        del env
        # Reactive switching waits until the current bearer already looks bad,
        # which is why it tends to model cold handovers.
        return ControllerDecision(
            prewarm_whc=False,
            target_link="whc"
            if (p2p.success_prob < 0.9 or p2p.latency_ms + p2p.jitter_ms > 26.0)
            and whc.success_prob > p2p.success_prob
            else None,
        )


class XpanPredictiveController:
    def __init__(
        self,
        prewarm_threshold: float,
        switch_threshold: float,
        hold_steps: int,
        return_hold_steps: int,
        predictive_horizon_steps: int,
        predictive_gain_threshold: float,
        predictive_prewarm_gain_threshold: float,
        p2p_return_success_threshold: float,
        p2p_return_distance_m: float,
        whc_return_hysteresis_margin: float,
    ) -> None:
        self.prewarm_threshold = prewarm_threshold
        self.switch_threshold = switch_threshold
        self.hold_steps = hold_steps
        self.return_hold_steps = return_hold_steps
        self.predictive_horizon_steps = predictive_horizon_steps
        self.predictive_gain_threshold = predictive_gain_threshold
        self.predictive_prewarm_gain_threshold = predictive_prewarm_gain_threshold
        self.p2p_return_success_threshold = p2p_return_success_threshold
        self.p2p_return_distance_m = p2p_return_distance_m
        self.whc_return_hysteresis_margin = whc_return_hysteresis_margin
        self.rssi_window: deque[float] = deque(maxlen=6)
        self.retry_window: deque[float] = deque(maxlen=6)
        self.latency_window: deque[float] = deque(maxlen=6)
        self.high_risk_steps = 0
        self.high_gain_steps = 0
        self.p2p_recovery_steps = 0

    def _trend(self, values: deque[float]) -> float:
        if len(values) < 2:
            return 0.0
        return values[0] - values[-1]

    def _project_future_quality(
        self,
        p2p: LinkQuality,
        whc: LinkQuality,
        env: EnvironmentState,
    ) -> tuple[float, float]:
        horizon_scale = self.predictive_horizon_steps / 30.0
        rssi_drop = max(0.0, self._trend(self.rssi_window))
        retry_rise = max(0.0, self.retry_window[-1] - self.retry_window[0]) if len(self.retry_window) > 1 else 0.0
        latency_rise = max(0.0, self.latency_window[-1] - self.latency_window[0]) if len(self.latency_window) > 1 else 0.0

        projected_p2p = p2p.success_prob
        projected_p2p -= 0.18 * rssi_drop * horizon_scale
        projected_p2p -= 0.12 * retry_rise * horizon_scale
        projected_p2p -= 0.06 * env.motion_away * horizon_scale
        projected_p2p -= 0.05 * env.wifi_congestion * horizon_scale
        projected_p2p -= 0.03 * min(1.0, latency_rise / 8.0) * horizon_scale

        projected_whc = whc.success_prob
        projected_whc += 0.03 * max(0.0, env.ap_quality - 0.8) * horizon_scale
        projected_whc -= 0.05 * env.wifi_congestion * horizon_scale
        projected_whc -= 0.06 * env.backhaul_load * horizon_scale

        return (
            max(0.0, min(1.0, projected_p2p)),
            max(0.0, min(1.0, projected_whc)),
        )

    def decide(
        self,
        current_link: str,
        le: LinkQuality,
        p2p: LinkQuality,
        whc: LinkQuality,
        env: EnvironmentState,
    ) -> ControllerDecision:
        del le
        self.rssi_window.append(p2p.rssi_like)
        self.retry_window.append(p2p.retry_rate)
        self.latency_window.append(p2p.latency_ms + p2p.jitter_ms)
        rssi_drop = self._trend(self.rssi_window)
        retry_rise = max(0.0, self.retry_window[-1] - self.retry_window[0]) if len(self.retry_window) > 1 else 0.0
        projected_p2p_success, projected_whc_success = self._project_future_quality(p2p, whc, env)
        # This predictive score estimates whether the direct path is heading
        # toward trouble over the next short horizon rather than reacting only
        # to the current instant.
        risk = (
            0.25 * (1.0 - p2p.rssi_like)
            + 0.18 * rssi_drop
            + 0.16 * retry_rise
            + 0.1 * env.motion_away
            + 0.18 * max(0.0, projected_whc_success - projected_p2p_success)
            + 0.13 * max(0.0, 0.92 - projected_p2p_success)
        )
        risk = max(0.0, min(1.0, risk))
        expected_switch_gain = (
            0.7 * (projected_whc_success - projected_p2p_success)
            + 0.2 * (whc.success_prob - p2p.success_prob)
            + 0.1 * (0.5 if whc.latency_ms + whc.jitter_ms <= p2p.latency_ms + p2p.jitter_ms + 4.0 else -0.5)
        )
        if risk >= self.switch_threshold:
            self.high_risk_steps += 1
        else:
            self.high_risk_steps = 0
        if expected_switch_gain >= self.predictive_gain_threshold:
            self.high_gain_steps += 1
        else:
            self.high_gain_steps = 0
        p2p_clearly_better = (
            p2p.success_prob >= self.p2p_return_success_threshold
            and p2p.success_prob >= whc.success_prob + self.whc_return_hysteresis_margin
            and p2p.latency_ms + p2p.jitter_ms <= whc.latency_ms + whc.jitter_ms + 3.0
            and env.distance_m <= self.p2p_return_distance_m
            and env.motion_away < 0.45
        )
        if p2p_clearly_better:
            self.p2p_recovery_steps += 1
        else:
            self.p2p_recovery_steps = 0

        if current_link == "whc":
            return ControllerDecision(
                prewarm_whc=False,
                target_link="p2p" if self.p2p_recovery_steps >= self.return_hold_steps else None,
            )

        return ControllerDecision(
            # Prewarming means the WHC bearer is being prepared before the
            # active P2P bearer has completely failed.
            prewarm_whc=current_link == "p2p"
            and (
                risk >= self.prewarm_threshold
                or expected_switch_gain >= self.predictive_prewarm_gain_threshold
            ),
            target_link="whc"
            if current_link == "p2p"
            and self.high_risk_steps >= self.hold_steps
            and self.high_gain_steps >= self.hold_steps
            and whc.success_prob >= p2p.success_prob
            else None,
        )


class ServiceAwareController:
    def __init__(
        self,
        prewarm_threshold: float,
        switch_threshold: float,
        hold_steps: int,
        return_hold_steps: int,
        predictive_horizon_steps: int,
        predictive_gain_threshold: float,
        predictive_prewarm_gain_threshold: float,
        p2p_return_success_threshold: float,
        p2p_return_distance_m: float,
        whc_return_hysteresis_margin: float,
    ) -> None:
        self.predictive = XpanPredictiveController(
            prewarm_threshold,
            switch_threshold,
            hold_steps,
            return_hold_steps,
            predictive_horizon_steps,
            predictive_gain_threshold,
            predictive_prewarm_gain_threshold,
            p2p_return_success_threshold,
            p2p_return_distance_m,
            whc_return_hysteresis_margin,
        )
        self.p2p_preference_steps = 0
        self.le_fallback_steps = 0

    def _track_steps(self, condition: bool, current_steps: int) -> int:
        return current_steps + 1 if condition else 0

    def decide(
        self,
        current_link: str,
        le: LinkQuality,
        p2p: LinkQuality,
        whc: LinkQuality,
        env: EnvironmentState,
    ) -> ControllerDecision:
        if env.phone_low_power or env.service_type == "voice_call":
            self.p2p_preference_steps = 0
            self.le_fallback_steps = 0
            return ControllerDecision(prewarm_whc=False, target_link="le", force_switch=True)

        if env.service_type == "music":
            p2p_preferred = p2p.success_prob >= 0.9 and p2p.latency_ms + p2p.jitter_ms <= 24.0
            weak_direct_path = p2p.success_prob < 0.78 or env.distance_m > 6.5
            self.p2p_preference_steps = self._track_steps(p2p_preferred, self.p2p_preference_steps)
            self.le_fallback_steps = self._track_steps(weak_direct_path, self.le_fallback_steps)

            if current_link == "le" and self.p2p_preference_steps >= 3:
                return ControllerDecision(prewarm_whc=False, target_link="p2p")

            predictive = self.predictive.decide(current_link, le, p2p, whc, env)
            if predictive.target_link == "whc" and whc.success_prob >= 0.88:
                return predictive
            if current_link == "whc" and predictive.target_link == "p2p":
                return predictive
            if self.le_fallback_steps >= 3 and whc.success_prob < p2p.success_prob + 0.08:
                return ControllerDecision(prewarm_whc=False, target_link="le")
            if current_link != "p2p" and self.p2p_preference_steps >= 3:
                return ControllerDecision(prewarm_whc=False, target_link="p2p")

        return ControllerDecision(prewarm_whc=False, target_link=current_link)
