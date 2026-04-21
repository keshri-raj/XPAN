from dataclasses import dataclass

from sim.environment import EnvironmentState


@dataclass
class PowerAdjustments:
    active_power_scale: float = 1.0
    standby_power_scale: float = 1.0
    extra_latency_ms: float = 0.0
    extra_jitter_ms: float = 0.0
    delivery_margin_delta: float = 0.0
    awake_ratio: float = 1.0


class PowerStrategy:
    name: str = "always_on"

    def adjustments(
        self,
        active_link: str,
        prewarmed: bool,
        overlap: bool,
        env: EnvironmentState,
        buffered_ms: float,
    ) -> PowerAdjustments:
        raise NotImplementedError


class AlwaysOnStrategy(PowerStrategy):
    name = "always_on"

    def adjustments(
        self,
        active_link: str,
        prewarmed: bool,
        overlap: bool,
        env: EnvironmentState,
        buffered_ms: float,
    ) -> PowerAdjustments:
        del active_link, prewarmed, overlap, env, buffered_ms
        return PowerAdjustments()


class StaticTwtStrategy(PowerStrategy):
    name = "static_twt"

    def adjustments(
        self,
        active_link: str,
        prewarmed: bool,
        overlap: bool,
        env: EnvironmentState,
        buffered_ms: float,
    ) -> PowerAdjustments:
        del buffered_ms
        if active_link == "le":
            return PowerAdjustments()
        latency_penalty = 7.0 if active_link == "whc" else 5.0
        jitter_penalty = 3.5 if env.wifi_congestion > 0.35 else 2.0
        delivery_penalty = -0.05 if overlap else -0.03
        return PowerAdjustments(
            active_power_scale=0.78,
            standby_power_scale=0.6 if prewarmed else 0.78,
            extra_latency_ms=latency_penalty,
            extra_jitter_ms=jitter_penalty,
            delivery_margin_delta=delivery_penalty,
            awake_ratio=0.72,
        )


class AdaptiveTwtStrategy(PowerStrategy):
    name = "adaptive_twt"

    def adjustments(
        self,
        active_link: str,
        prewarmed: bool,
        overlap: bool,
        env: EnvironmentState,
        buffered_ms: float,
    ) -> PowerAdjustments:
        if active_link == "le":
            return PowerAdjustments()
        tight_mode = prewarmed or overlap or buffered_ms < 35.0 or env.wifi_congestion > 0.45
        if tight_mode:
            return PowerAdjustments(
                active_power_scale=0.9,
                standby_power_scale=0.85,
                extra_latency_ms=2.0,
                extra_jitter_ms=1.2,
                delivery_margin_delta=-0.01,
                awake_ratio=0.88,
            )
        return PowerAdjustments(
            active_power_scale=0.7,
            standby_power_scale=0.55,
            extra_latency_ms=4.0,
            extra_jitter_ms=1.8,
            delivery_margin_delta=-0.02,
            awake_ratio=0.68,
        )


class PredictivePrewakeStrategy(PowerStrategy):
    name = "predictive_prewake"

    def adjustments(
        self,
        active_link: str,
        prewarmed: bool,
        overlap: bool,
        env: EnvironmentState,
        buffered_ms: float,
    ) -> PowerAdjustments:
        if active_link == "le":
            return PowerAdjustments()
        prewake_mode = prewarmed or overlap or env.motion_away > 0.6 or buffered_ms < 45.0
        if prewake_mode:
            return PowerAdjustments(
                active_power_scale=0.94,
                standby_power_scale=0.92,
                extra_latency_ms=1.0,
                extra_jitter_ms=0.8,
                delivery_margin_delta=0.01,
                awake_ratio=0.93,
            )
        return PowerAdjustments(
            active_power_scale=0.66,
            standby_power_scale=0.48,
            extra_latency_ms=3.0,
            extra_jitter_ms=1.5,
            delivery_margin_delta=-0.01,
            awake_ratio=0.63,
        )


def build_power_strategies() -> dict[str, PowerStrategy]:
    strategies: list[PowerStrategy] = [
        AlwaysOnStrategy(),
        StaticTwtStrategy(),
        AdaptiveTwtStrategy(),
        PredictivePrewakeStrategy(),
    ]
    return {strategy.name: strategy for strategy in strategies}
