from nicto.domain.models import Gap


def calculate_flexcurve(stream_size: int, gaps: list[Gap]) -> int:
    """Return the number of start positions of a stream of ``stream_size`` slots within the gaps."""
    return sum(gap.num_slots - stream_size + 1 for gap in gaps if gap.num_slots >= stream_size)
