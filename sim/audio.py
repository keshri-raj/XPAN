from dataclasses import dataclass


@dataclass
class AudioStatus:
    buffered_ms: float
    underruns: int = 0
    interruption_ms: float = 0.0
    delivered_packets: int = 0
    lost_packets: int = 0


class AudioStream:
    def __init__(self, base_buffer_ms: int, packet_interval_ms: int) -> None:
        self.packet_interval_ms = packet_interval_ms
        self.status = AudioStatus(buffered_ms=float(base_buffer_ms))

    def tick(self, delivered_on_time: bool, step_ms: int) -> None:
        if delivered_on_time:
            self.status.buffered_ms += self.packet_interval_ms
            self.status.delivered_packets += 1
        else:
            self.status.lost_packets += 1

        self.status.buffered_ms -= step_ms
        if self.status.buffered_ms < 0:
            self.status.underruns += 1
            self.status.interruption_ms += abs(self.status.buffered_ms)
            self.status.buffered_ms = 0.0
