from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic_extra_types.mac_address import MacAddress

BITS_PER_BYTE = 8
NANOSECONDS_PER_MEGABIT_PER_SECOND = 1_000
MAX_UNIQUE_ID = 0xFFFF
UNIQUE_ID_HEX_DIGITS = 4


class StreamID(BaseModel):
    """Stream identifier: the 48-bit source MAC address plus a 16-bit unique ID."""

    model_config = ConfigDict(frozen=True)

    mac_address: MacAddress
    unique_id: int = Field(ge=0, le=MAX_UNIQUE_ID)

    @classmethod
    def parse(cls, value: str) -> Self:
        """Build a stream ID from its ``<mac>-<unique id in hex>`` string form."""
        mac_address, separator, unique_id = value.rpartition("-")
        if not separator or len(unique_id) != UNIQUE_ID_HEX_DIGITS:
            msg = "Stream ID must have the form <mac address>-<4 hex digit unique ID>"
            raise ValueError(msg)
        return cls(mac_address=MacAddress(mac_address), unique_id=int(unique_id, 16))

    def __str__(self) -> str:
        """Return the ``<mac>-<unique id in hex>`` string form."""
        return f"{self.mac_address}-{self.unique_id:0{UNIQUE_ID_HEX_DIGITS}x}"


class Port(BaseModel):
    """A port belonging to a node."""

    mac_address: MacAddress
    name: str
    allocations: list["Allocation"] = Field(default_factory=list)

    def gaps(self, total_slots: int) -> list["Gap"]:
        """Return the unallocated ranges in a schedule with ``total_slots`` slots."""
        if total_slots <= 0:
            msg = "Total schedule slots must be positive"
            raise ValueError(msg)

        gaps: list[Gap] = []
        next_available_idx = 0
        for allocation in sorted(self.allocations, key=lambda allocation: allocation.start_idx):
            allocation_end_idx = allocation.start_idx + allocation.num_slots
            if allocation.start_idx < next_available_idx:
                msg = "Port allocations must not overlap"
                raise ValueError(msg)
            if allocation_end_idx > total_slots:
                msg = "Port allocation exceeds the schedule"
                raise ValueError(msg)
            if allocation.start_idx > next_available_idx:
                gaps.append(
                    Gap(
                        start_idx=next_available_idx,
                        num_slots=allocation.start_idx - next_available_idx,
                    ),
                )
            next_available_idx = allocation_end_idx

        if next_available_idx < total_slots:
            gaps.append(Gap(start_idx=next_available_idx, num_slots=total_slots - next_available_idx))

        return gaps


class Node(BaseModel):
    """A node in the network."""

    hostname: str
    ports: list[Port] = Field(default_factory=list)


class Link(BaseModel):
    """A bidirectional connection recorded once for a canonical pair of ports."""

    port_a_mac_address: MacAddress
    port_b_mac_address: MacAddress
    speed: int
    propagation_delay: int

    @model_validator(mode="after")
    def canonicalize_ports(self) -> Self:
        """Store endpoints in a stable order for a direction-independent link."""
        if self.port_a_mac_address == self.port_b_mac_address:
            msg = "A link must connect two distinct ports"
            raise ValueError(msg)
        if str(self.port_a_mac_address) > str(self.port_b_mac_address):
            self.port_a_mac_address, self.port_b_mac_address = (
                self.port_b_mac_address,
                self.port_a_mac_address,
            )
        return self


class Stream(BaseModel):
    """A scheduled data stream."""

    id: StreamID
    src_mac_address: MacAddress
    dst_mac_address: MacAddress
    vlan: int | None = None
    priority: int | None = None
    max_frame_size: int
    max_interval_frames: int
    interval: int
    max_latency: int
    allocations: list["Allocation"] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_id_source(self) -> Self:
        """Ensure the stream ID is built from the source MAC address."""
        if self.id.mac_address != self.src_mac_address:
            msg = "Stream ID MAC address must match the source MAC address"
            raise ValueError(msg)
        return self

    def slots(self, speed: int, tick_granularity: int) -> int:
        """Return slots needed to transmit the maximum interval frame payload."""
        payload_size = self.max_frame_size * self.max_interval_frames
        transmission_time = payload_size * BITS_PER_BYTE * NANOSECONDS_PER_MEGABIT_PER_SECOND
        return (transmission_time + (speed * tick_granularity) - 1) // (speed * tick_granularity)


class Allocation(BaseModel):
    """An allocated stream transmission on a port."""

    stream_id: StreamID
    port_mac_address: MacAddress
    start_idx: int = Field(ge=0)
    num_slots: int = Field(gt=0)


class Gap(BaseModel):
    """A non-persistent contiguous range of free schedule slots on a port."""

    start_idx: int = Field(ge=0)
    num_slots: int = Field(gt=0)


class Hop(BaseModel):
    """A step of a path: the port that transmits a stream and the link it transmits on."""

    port: Port
    link: Link
