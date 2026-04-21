from dataclasses import dataclass


@dataclass
class EnvironmentState:
    time_s: float
    distance_m: float
    body_blockage_db: float
    wifi_congestion: float
    motion_away: float
    ap_quality: float
    backhaul_load: float
    service_type: str = "music"
    phone_low_power: bool = False


class Scenario:
    name: str

    def state_at(self, time_s: float) -> EnvironmentState:
        raise NotImplementedError


class WalkAwayScenario:
    """User gradually moves away from the phone with periodic Wi-Fi congestion."""
    name = "walk_away"

    def state_at(self, time_s: float) -> EnvironmentState:
        # Distance and body loss mainly hurt direct P2P/LE bearers, while
        # congestion/AP quality/backhaul load shape the WHC path quality.
        distance_m = 1.0 + 0.45 * time_s
        body_blockage_db = 8.0 if 10.0 <= time_s <= 14.0 else 0.0
        wifi_congestion = 0.55 if 18.0 <= time_s <= 22.0 else 0.15
        motion_away = 1.0 if time_s <= 20.0 else 0.2
        ap_quality = 0.92 if time_s < 22.0 else 0.82
        backhaul_load = 0.22 if time_s < 18.0 else 0.38
        return EnvironmentState(
            time_s=time_s,
            distance_m=distance_m,
            body_blockage_db=body_blockage_db,
            wifi_congestion=wifi_congestion,
            motion_away=motion_away,
            ap_quality=ap_quality,
            backhaul_load=backhaul_load,
            service_type="music",
            phone_low_power=False,
        )


class BodyBlockageScenario:
    """Phone stays nearby, but repeated body and pocket blockage hurts direct paths."""
    name = "body_blockage"

    def state_at(self, time_s: float) -> EnvironmentState:
        distance_m = 2.8 + 0.05 * (time_s % 6.0)
        if 6.0 <= time_s <= 11.0 or 17.0 <= time_s <= 21.0:
            body_blockage_db = 15.0
        elif 11.0 < time_s <= 13.5:
            body_blockage_db = 10.0
        else:
            body_blockage_db = 3.0
        wifi_congestion = 0.2 if time_s < 20.0 else 0.3
        motion_away = 0.45
        ap_quality = 0.94
        backhaul_load = 0.18
        return EnvironmentState(
            time_s=time_s,
            distance_m=distance_m,
            body_blockage_db=body_blockage_db,
            wifi_congestion=wifi_congestion,
            motion_away=motion_away,
            ap_quality=ap_quality,
            backhaul_load=backhaul_load,
            service_type="music",
            phone_low_power=False,
        )


class MeshBackhaulStressScenario:
    """Whole-home coverage is available, but AP and backhaul quality fluctuate."""
    name = "mesh_backhaul_stress"

    def state_at(self, time_s: float) -> EnvironmentState:
        distance_m = 6.0 + 0.08 * time_s
        body_blockage_db = 4.0 if 12.0 <= time_s <= 15.0 else 1.5
        wifi_congestion = 0.28 if time_s < 10.0 else 0.62 if time_s < 21.0 else 0.36
        motion_away = 0.75 if time_s < 14.0 else 0.25
        ap_quality = 0.88 if time_s < 10.0 else 0.76 if time_s < 21.0 else 0.84
        backhaul_load = 0.25 if time_s < 10.0 else 0.58 if time_s < 21.0 else 0.33
        return EnvironmentState(
            time_s=time_s,
            distance_m=distance_m,
            body_blockage_db=body_blockage_db,
            wifi_congestion=wifi_congestion,
            motion_away=motion_away,
            ap_quality=ap_quality,
            backhaul_load=backhaul_load,
            service_type="music",
            phone_low_power=False,
        )


class ServiceAwareUseCaseScenario:
    """Service-driven XPAN use cases covering voice, music, distance, and phone power mode."""
    name = "service_aware_use_cases"

    def state_at(self, time_s: float) -> EnvironmentState:
        if time_s < 8.0:
            return EnvironmentState(
                time_s=time_s,
                distance_m=1.5,
                body_blockage_db=1.5,
                wifi_congestion=0.1,
                motion_away=0.1,
                ap_quality=0.94,
                backhaul_load=0.18,
                service_type="voice_call",
                phone_low_power=False,
            )
        if time_s < 16.0:
            return EnvironmentState(
                time_s=time_s,
                distance_m=1.8,
                body_blockage_db=1.0,
                wifi_congestion=0.12,
                motion_away=0.15,
                ap_quality=0.94,
                backhaul_load=0.18,
                service_type="music",
                phone_low_power=False,
            )
        if time_s < 23.0:
            return EnvironmentState(
                time_s=time_s,
                distance_m=5.0 + 0.25 * (time_s - 16.0),
                body_blockage_db=4.0,
                wifi_congestion=0.15,
                motion_away=0.9,
                ap_quality=0.9,
                backhaul_load=0.22,
                service_type="music",
                phone_low_power=False,
            )
        return EnvironmentState(
            time_s=time_s,
            distance_m=2.2,
            body_blockage_db=1.0,
            wifi_congestion=0.12,
            motion_away=0.1,
            ap_quality=0.94,
            backhaul_load=0.18,
            service_type="music",
            phone_low_power=True,
        )


def build_scenarios() -> list[Scenario]:
    return [
        WalkAwayScenario(),
        BodyBlockageScenario(),
        MeshBackhaulStressScenario(),
        ServiceAwareUseCaseScenario(),
    ]
