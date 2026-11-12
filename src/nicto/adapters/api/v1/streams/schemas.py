from pydantic import BaseModel, ConfigDict, Field
from pydantic_extra_types.mac_address import MacAddress

from nicto.domain.models import MAX_UNIQUE_ID, Stream, StreamID


class AllocationResponse(BaseModel):
    """A scheduled transmission of the stream on a port."""

    port_mac_address: MacAddress
    start_idx: int
    num_slots: int


class InsertStreamRequest(BaseModel):
    """Parameters of the stream to insert."""

    model_config = ConfigDict(extra="forbid")

    unique_id: int = Field(ge=0, le=MAX_UNIQUE_ID)
    src_mac_address: MacAddress
    dst_mac_address: MacAddress
    vlan: int | None = None
    priority: int | None = None
    max_frame_size: int
    max_interval_frames: int
    interval: int
    max_latency: int

    def to_domain(self) -> Stream:
        """Build the domain stream described by the request."""
        fields = self.model_dump(exclude={"unique_id"})
        return Stream(id=StreamID(mac_address=self.src_mac_address, unique_id=self.unique_id), **fields)


class InsertStreamResponse(BaseModel):
    """The inserted stream with its computed schedule."""

    id: str
    src_mac_address: MacAddress
    dst_mac_address: MacAddress
    vlan: int | None
    priority: int | None
    max_frame_size: int
    max_interval_frames: int
    interval: int
    max_latency: int
    allocations: list[AllocationResponse]

    @classmethod
    def from_domain(cls, stream: Stream) -> "InsertStreamResponse":
        """Build the response from a domain stream."""
        return cls.model_validate(stream.model_copy(update={"id": str(stream.id)}), from_attributes=True)
