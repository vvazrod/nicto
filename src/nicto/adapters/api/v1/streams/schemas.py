import uuid

from pydantic import BaseModel, ConfigDict
from pydantic_extra_types.mac_address import MacAddress

from nicto.domain.models import Stream


class AllocationResponse(BaseModel):
    """A scheduled transmission of the stream on a port."""

    port_mac_address: MacAddress
    start_idx: int
    num_slots: int


class InsertStreamRequest(BaseModel):
    """Parameters of the stream to insert."""

    model_config = ConfigDict(extra="forbid")

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
        return Stream(**self.model_dump())


class InsertStreamResponse(BaseModel):
    """The inserted stream with its computed schedule."""

    id: uuid.UUID
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
        return cls.model_validate(stream, from_attributes=True)
