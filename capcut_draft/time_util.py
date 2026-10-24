"""Timerange type and time-related helpers."""

from typing import Union
from typing import Dict

SEC = 1000000
"""One second = 1e6 microseconds."""

def tim(inp: Union[str, float]) -> int:
    """Convert a time string to microseconds; a number of microseconds is also accepted.

    Accepts forms such as "1h52m3s" or "0.15s", optionally signed for a negative offset.
    """
    if isinstance(inp, (int, float)):
        return int(round(inp))

    sign: int = 1
    inp = inp.strip().lower()
    if inp.startswith("-"):
        sign = -1
        inp = inp[1:]

    last_index: int = 0
    total_time: float = 0
    for unit, factor in zip(["h", "m", "s"], [3600 * SEC, 60 * SEC, SEC]):
        unit_index = inp.find(unit)
        if unit_index == -1: continue

        total_time += float(inp[last_index:unit_index]) * factor
        last_index = unit_index + 1

    return int(round(total_time) * sign)

class Timerange:
    """A time range: a start time and a duration."""
    start: int
    """Start time, in microseconds."""
    duration: int
    """Duration, in microseconds."""

    def __init__(self, start: int, duration: int):
        """Construct a time range.

        Args:
            start (int): start time, in microseconds
            duration (int): duration, in microseconds
        """

        self.start = start
        self.duration = duration

    @classmethod
    def import_json(cls, json_obj: Dict[str, str]) -> "Timerange":
        """Restore a Timerange from its JSON form."""
        return cls(int(json_obj["start"]), int(json_obj["duration"]))

    @property
    def end(self) -> int:
        """End time, in microseconds."""
        return self.start + self.duration

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Timerange):
            return False
        return self.start == other.start and self.duration == other.duration

    def overlaps(self, other: "Timerange") -> bool:
        """Whether two time ranges overlap."""
        return not (self.end <= other.start or other.end <= self.start)

    def __repr__(self) -> str:
        return f"Timerange(start={self.start}, duration={self.duration})"

    def __str__(self) -> str:
        return f"[start={self.start}, end={self.end}]"

    def export_json(self) -> Dict[str, int]:
        return {"start": self.start, "duration": self.duration}

def trange(start: Union[str, float], duration: Union[str, float]) -> Timerange:
    """Convenience constructor for Timerange, accepting strings or microseconds.

    Accepts forms such as "1h52m3s" or "0.15s".

    Args:
        start (Union[str, float]): start time
        duration (Union[str, float]): duration -- note this is **not** the end time
    """
    return Timerange(tim(start), tim(duration))

def srt_tstamp(srt_tstamp: str) -> int:
    """Parse an SRT timestamp string and return microseconds."""
    sec_str, ms_str = srt_tstamp.split(",")
    parts = sec_str.split(":") + [ms_str]

    total_time = 0
    for value, factor in zip(parts, [3600 * SEC, 60 * SEC, SEC, 1000]):
        total_time += int(value) * factor
    return total_time
