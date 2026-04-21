from dataclasses import dataclass


@dataclass
class SimulationMetrics:
    handovers: int = 0
    cold_switches: int = 0
    interruptions_ms: float = 0.0
    underruns: int = 0
    delivered_packets: int = 0
    lost_packets: int = 0
    average_latency_ms: float = 0.0
    energy_mj: float = 0.0
    average_power_mw: float = 0.0
    energy_per_delivered_packet_uj: float = 0.0
    le_energy_mj: float = 0.0
    p2p_energy_mj: float = 0.0
    whc_active_energy_mj: float = 0.0
    whc_standby_energy_mj: float = 0.0
    overlap_energy_mj: float = 0.0
    whc_prewarm_time_ms: float = 0.0
    whc_active_time_ms: float = 0.0
    overlap_time_ms: float = 0.0
    average_awake_ratio: float = 1.0
    average_data_rate_mbps: float = 0.0
    peak_data_rate_mbps: float = 0.0
    min_active_rssi_dbm: float = 0.0
    average_active_rssi_dbm: float = 0.0
    bearer_switch_time_ms: float = 0.0
    transition_time_ms: float = 0.0
    gap_free: bool = False
    early_switches: int = 0
    late_switches: int = 0
    unnecessary_prewarm_events: int = 0
    ping_pong_count: int = 0
    average_prediction_lead_time_ms: float = 0.0

    def summary(self) -> dict[str, float]:
        total_packets = self.delivered_packets + self.lost_packets
        loss_rate = self.lost_packets / total_packets if total_packets else 0.0
        return {
            "handovers": float(self.handovers),
            "cold_switches": float(self.cold_switches),
            "interruptions_ms": round(self.interruptions_ms, 2),
            "underruns": float(self.underruns),
            "packet_loss_rate": round(loss_rate, 4),
            "average_latency_ms": round(self.average_latency_ms, 2),
            "average_data_rate_mbps": round(self.average_data_rate_mbps, 3),
            "peak_data_rate_mbps": round(self.peak_data_rate_mbps, 3),
            "min_active_rssi_dbm": round(self.min_active_rssi_dbm, 2),
            "average_active_rssi_dbm": round(self.average_active_rssi_dbm, 2),
            "bearer_switch_time_ms": round(self.bearer_switch_time_ms, 2),
            "transition_time_ms": round(self.transition_time_ms, 2),
            "gap_free": float(self.gap_free),
            "early_switches": float(self.early_switches),
            "late_switches": float(self.late_switches),
            "unnecessary_prewarm_events": float(self.unnecessary_prewarm_events),
            "ping_pong_count": float(self.ping_pong_count),
            "average_prediction_lead_time_ms": round(self.average_prediction_lead_time_ms, 2),
            "energy_mj": round(self.energy_mj, 2),
            "average_power_mw": round(self.average_power_mw, 2),
            "energy_per_delivered_packet_uj": round(self.energy_per_delivered_packet_uj, 2),
            "le_energy_mj": round(self.le_energy_mj, 2),
            "p2p_energy_mj": round(self.p2p_energy_mj, 2),
            "whc_active_energy_mj": round(self.whc_active_energy_mj, 2),
            "whc_standby_energy_mj": round(self.whc_standby_energy_mj, 2),
            "overlap_energy_mj": round(self.overlap_energy_mj, 2),
            "whc_prewarm_time_ms": round(self.whc_prewarm_time_ms, 2),
            "whc_active_time_ms": round(self.whc_active_time_ms, 2),
            "overlap_time_ms": round(self.overlap_time_ms, 2),
            "average_awake_ratio": round(self.average_awake_ratio, 3),
        }
