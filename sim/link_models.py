from dataclasses import dataclass

from sim.environment import EnvironmentState


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


@dataclass
class LinkQuality:
    # rssi_like is normalized to [0, 1] so the controller can fuse bearer
    # quality trends without using a separate dBm threshold per bearer type.
    name: str
    success_prob: float
    latency_ms: float
    jitter_ms: float
    rssi_like: float
    retry_rate: float
    data_rate_mbps: float
    band: str


class LELinkModel:
    def quality(self, env: EnvironmentState) -> LinkQuality:
        # LE represents normal buds: lowest power, lowest rate, shortest reach.
        attenuation = max(0.0, env.distance_m - 1.0) * 0.065 + env.body_blockage_db * 0.018
        success_prob = _clamp(0.992 - attenuation, 0.35, 0.992)
        retry_rate = _clamp((1.0 - success_prob) * 2.6, 0.0, 0.98)
        latency_ms = 18.0 + retry_rate * 24.0
        jitter_ms = 3.0 + retry_rate * 12.0
        rssi_like = _clamp(1.0 - attenuation * 1.95, 0.0, 1.0)
        data_rate_mbps = 0.85 * success_prob
        return LinkQuality("le", success_prob, latency_ms, jitter_ms, rssi_like, retry_rate, data_rate_mbps, "2.4 GHz")


class P2PLinkModel:
    def quality(self, env: EnvironmentState) -> LinkQuality:
        # P2P is the preferred XPAN bearer when the phone is nearby enough to
        # support direct low-latency transport.
        attenuation = max(0.0, env.distance_m - 1.0) * 0.05 + env.body_blockage_db * 0.012 + env.wifi_congestion * 0.05
        success_prob = _clamp(0.997 - attenuation, 0.42, 0.997)
        retry_rate = _clamp((1.0 - success_prob) * 2.0, 0.0, 0.95)
        latency_ms = 10.0 + retry_rate * 18.0 + env.wifi_congestion * 6.0
        jitter_ms = 1.8 + retry_rate * 7.0
        rssi_like = _clamp(1.0 - attenuation * 1.5, 0.0, 1.0)
        data_rate_mbps = 2.35 * success_prob
        return LinkQuality("p2p", success_prob, latency_ms, jitter_ms, rssi_like, retry_rate, data_rate_mbps, "5 GHz")


class WHCLinkModel:
    def quality(self, env: EnvironmentState) -> LinkQuality:
        # WHC is the AP-assisted whole-home path, so infrastructure health
        # matters more than direct phone distance.
        attenuation = (
            max(0.0, env.distance_m - 1.0) * 0.01
            + env.wifi_congestion * 0.18
            + (1.0 - env.ap_quality) * 0.22
            + env.backhaul_load * 0.12
        )
        success_prob = _clamp(0.998 - attenuation, 0.62, 0.998)
        retry_rate = _clamp((1.0 - success_prob) * 1.8, 0.0, 0.95)
        latency_ms = 15.0 + env.wifi_congestion * 24.0 + env.backhaul_load * 16.0 + retry_rate * 10.0
        jitter_ms = 2.0 + env.wifi_congestion * 8.0 + env.backhaul_load * 5.0
        rssi_like = _clamp(env.ap_quality - env.wifi_congestion * 0.15, 0.0, 1.0)
        data_rate_mbps = 2.6 * success_prob
        return LinkQuality("whc", success_prob, latency_ms, jitter_ms, rssi_like, retry_rate, data_rate_mbps, "5 GHz")
