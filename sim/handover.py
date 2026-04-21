from dataclasses import dataclass

from sim.config import SimulationConfig
from sim.controller import ControllerDecision


@dataclass
class HandoverStatus:
    active_link: str
    whc_prewarmed_steps: int = 0
    overlap_steps_remaining: int = 0
    handovers: int = 0
    cold_switches: int = 0


class HandoverEngine:
    def __init__(self, config: SimulationConfig, initial_link: str) -> None:
        self.config = config
        self.status = HandoverStatus(active_link=initial_link)

    def update(self, decision: ControllerDecision) -> HandoverStatus:
        # Prewarm only applies while P2P is still the active bearer.
        if decision.prewarm_whc and self.status.active_link == "p2p":
            self.status.whc_prewarmed_steps = min(
                self.status.whc_prewarmed_steps + 1,
                self.config.prewarm_steps,
            )
        else:
            self.status.whc_prewarmed_steps = max(0, self.status.whc_prewarmed_steps - 1)

        target_link = decision.target_link
        if target_link == "whc" and self.status.active_link == "p2p":
            if self.status.whc_prewarmed_steps >= self.config.prewarm_steps:
                # Warm handover approximates make-before-break by allowing a
                # short overlap window between the two bearers.
                self.status.active_link = "whc"
                self.status.overlap_steps_remaining = self.config.overlap_steps
                self.status.handovers += 1
            elif not decision.prewarm_whc:
                # Cold handover jumps directly to WHC once P2P has degraded.
                self.status.active_link = "whc"
                self.status.overlap_steps_remaining = 0
                self.status.cold_switches += 1
                self.status.handovers += 1
        elif target_link in {"le", "p2p"} and target_link != self.status.active_link:
            self.status.active_link = target_link
            self.status.overlap_steps_remaining = 0
            self.status.handovers += 1

        if self.status.overlap_steps_remaining > 0:
            self.status.overlap_steps_remaining -= 1

        return self.status
