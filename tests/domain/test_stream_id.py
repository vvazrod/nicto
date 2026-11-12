import pytest
from pydantic_extra_types.mac_address import MacAddress

from nicto.domain.models import Stream, StreamID

MAC = MacAddress("00:11:22:33:44:55")
OTHER_MAC = MacAddress("00:11:22:33:44:56")


def test_stream_id_round_trips_through_string() -> None:
    """Test the string form parses back to the same stream ID."""
    stream_id = StreamID(mac_address=MAC, unique_id=0xAB)

    assert str(stream_id) == "00:11:22:33:44:55-00ab"
    assert StreamID.parse(str(stream_id)) == stream_id


@pytest.mark.parametrize("value", ["00:11:22:33:44:55", "00:11:22:33:44:55-1", "00:11:22:33:44:55-zzzz"])
def test_stream_id_parse_rejects_malformed_values(value: str) -> None:
    """Test malformed stream IDs are rejected."""
    with pytest.raises(ValueError, match=r"Stream ID|unique_id|invalid"):
        StreamID.parse(value)


def test_stream_id_rejects_oversized_unique_id() -> None:
    """Test the unique ID is limited to 16 bits."""
    with pytest.raises(ValueError, match="less than or equal"):
        StreamID(mac_address=MAC, unique_id=0x10000)


def test_stream_id_must_match_source_mac() -> None:
    """Test a stream ID must be built from the stream's source MAC address."""
    with pytest.raises(ValueError, match="must match the source"):
        Stream(
            id=StreamID(mac_address=OTHER_MAC, unique_id=1),
            src_mac_address=MAC,
            dst_mac_address=OTHER_MAC,
            max_frame_size=100,
            max_interval_frames=1,
            interval=1_000,
            max_latency=10_000,
        )
