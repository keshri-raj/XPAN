from collections import deque
from dataclasses import dataclass

from sim.environment import EnvironmentState
from sim.link_models import LinkQuality


@dataclass
class ControllerDecision:
    prewarm_whc: bool = False
    target_link: str | None = None


class XpanReactiveController:
    def decide(self, p2p: LinkQuality, whc: LinkQuality, env: EnvironmentState) -> ControllerDecision:
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
    def __init__(self, prewarm_threshold: float, switch_threshold: float, hold_steps: int) -> None:
        self.prewarm_threshold = prewarm_threshold
        self.switch_threshold = switch_threshold
        self.hold_steps = hold_steps
        self.rssi_window: deque[float] = deque(maxlen=6)
        self.retry_window: deque[float] = deque(maxlen=6)
        self.high_risk_steps = 0

    def _trend(self, values: deque[float]) -> float:
        if len(values) < 2:
            return 0.0
        return values[0] - values[-1]

    def decide(self, p2p: LinkQuality, whc: LinkQuality, env: EnvironmentState) -> ControllerDecision:
        self.rssi_window.append(p2p.rssi_like)
        self.retry_window.append(p2p.retry_rate)
        rssi_drop = self._trend(self.rssi_window)
        retry_rise = max(0.0, self.retry_window[-1] - self.retry_window[0]) if len(self.retry_window) > 1 else 0.0
        # This risk score is the current stand-in for predictive intelligence:
        # combine radio degradation trends, user motion, and WHC readiness.
        risk = (
            0.35 * (1.0 - p2p.rssi_like)
            + 0.25 * rssi_drop
            + 0.2 * retry_rise
            + 0.1 * env.motion_away
            + 0.1 * (1.0 if whc.success_prob > 0.9 else 0.0)
        )
        risk = max(0.0, min(1.0, risk))
        if risk >= self.switch_threshold:
            self.high_risk_steps += 1
        else:
            self.high_risk_steps = 0
        return ControllerDecision(
            # Prewarming means the WHC bearer is being prepared before the
            # active P2P bearer has completely failed.
            prewarm_whc=risk >= self.prewarm_threshold,
            target_link="whc"
            if self.high_risk_steps >= self.hold_steps and whc.success_prob >= p2p.success_prob
            else None,
        )


class ServiceAwareController:
    def __init__(self, prewarm_threshold: float, switch_threshold: float, hold_steps: int) -> None:
        self.predictive = XpanPredictiveController(prewarm_threshold, switch_threshold, hold_steps)

    def decide(
        self,
        current_link: str,
        le: LinkQuality,
        p2p: LinkQuality,
        whc: LinkQuality,
        env: EnvironmentState,
    ) -> ControllerDecision:
        if env.phone_low_power or env.service_type == "voice_call":
            return ControllerDecision(prewarm_whc=False, target_link="le")

        if env.service_type == "music":
            if p2p.success_prob >= 0.9 and p2p.latency_ms + p2p.jitter_ms <= 24.0 and not env.phone_low_power:
                return ControllerDecision(prewarm_whc=False, target_link="p2p")
            predictive = self.predictive.decide(p2p, whc, env)
            if predictive.target_link == "whc" and whc.success_prob >= 0.88:
                return predictive
            if p2p.success_prob < 0.78 or env.distance_m > 6.5:
                return ControllerDecision(prewarm_whc=False, target_link="le")
            if current_link == "le" and p2p.success_prob >= 0.88:
                return ControllerDecision(prewarm_whc=False, target_link="p2p")

        return ControllerDecision(prewarm_whc=False, target_link=current_link)
