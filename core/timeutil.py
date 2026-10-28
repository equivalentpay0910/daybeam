"""Tiny helpers so everyone converts times the same way."""

def to_min(t: str) -> int:
    """'09:30' -> 570 (minutes after midnight)."""
    h, m = t.split(":")
    return int(h) * 60 + int(m)


def to_hhmm(minutes: float) -> str:
    """570 -> '09:30'."""
    minutes = int(round(minutes))
    return f"{minutes // 60:02d}:{minutes % 60:02d}"
