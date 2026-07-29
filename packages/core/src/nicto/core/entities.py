from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Port:
    """A named Ethernet port belonging to a device."""

    name: str
    id: int | None = None


@dataclass
class Device:
    """An Ethernet device identified by its hostname."""

    hostname: str
    ports: list[Port] = field(default_factory=list)
    id: int | None = None


@dataclass
class Link:
    """An Ethernet connection between two persisted ports."""

    source_port: Port
    destination_port: Port
    speed: int
    propagation_delay: int
    id: int | None = None


@dataclass
class Allocation:
    """A stream transmission scheduled on a port within the hyperperiod."""

    port: Port
    start_slot: int
    id: int | None = None


@dataclass
class Stream:
    """A traffic stream and its scheduled path through the network."""

    src_mac: str
    dst_mac: str
    vlan_id: int
    priority: int
    max_frame_size: int
    max_num_frames: int
    measurement_interval: int
    deadline: int
    allocations: list[Allocation] = field(default_factory=list)
    id: int | None = None
    created_at: datetime | None = None
