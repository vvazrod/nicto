from uuid import UUID

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for ORM models."""


class NodeModel(Base):
    """Database representation of a node in the network."""

    __tablename__ = "nodes"

    hostname: Mapped[str] = mapped_column(String, primary_key=True)
    ports: Mapped[list["PortModel"]] = relationship(
        back_populates="node",
        cascade="all, delete-orphan",
    )


class PortModel(Base):
    """Database representation of an Ethernet port."""

    __tablename__ = "ports"

    __table_args__ = (UniqueConstraint("node_hostname", "name"),)

    mac_address: Mapped[str] = mapped_column(String(17), primary_key=True)
    node_hostname: Mapped[str] = mapped_column(
        ForeignKey("nodes.hostname"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String)
    node: Mapped["NodeModel"] = relationship(back_populates="ports")
    allocations: Mapped[list["AllocationModel"]] = relationship(back_populates="port")


class LinkModel(Base):
    """Database representation of a bidirectional Ethernet connection."""

    __tablename__ = "links"
    __table_args__ = (
        CheckConstraint("speed IN (10, 100, 1000)", name="valid_link_speed"),
        CheckConstraint("propagation_delay >= 0", name="nonnegative_propagation_delay"),
        CheckConstraint(
            "port_a_mac_address < port_b_mac_address",
            name="canonical_link_ports",
        ),
    )

    port_a_mac_address: Mapped[str] = mapped_column(
        ForeignKey("ports.mac_address"),
        primary_key=True,
    )
    port_b_mac_address: Mapped[str] = mapped_column(
        ForeignKey("ports.mac_address"),
        primary_key=True,
    )
    speed: Mapped[int] = mapped_column(Integer)
    propagation_delay: Mapped[int] = mapped_column(BigInteger)
    port_a: Mapped[PortModel] = relationship(
        foreign_keys=[port_a_mac_address],
    )
    port_b: Mapped[PortModel] = relationship(
        foreign_keys=[port_b_mac_address],
    )


class StreamModel(Base):
    """Database representation of a scheduling stream."""

    __tablename__ = "streams"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    src_mac_address: Mapped[str] = mapped_column(String(17), nullable=False)
    dst_mac_address: Mapped[str] = mapped_column(String(17), nullable=False)
    vlan: Mapped[int] = mapped_column(Integer)
    priority: Mapped[int] = mapped_column(Integer)
    max_frame_size: Mapped[int] = mapped_column(Integer)
    max_interval_frames: Mapped[int] = mapped_column(Integer)
    interval: Mapped[int] = mapped_column(BigInteger)
    max_latency: Mapped[int] = mapped_column(BigInteger)
    allocations: Mapped[list["AllocationModel"]] = relationship(
        back_populates="stream",
        cascade="all, delete-orphan",
    )


class AllocationModel(Base):
    """Database representation of a stream's port allocation."""

    __tablename__ = "allocations"
    __table_args__ = (
        CheckConstraint("start_idx >= 0", name="nonnegative_start_idx"),
        CheckConstraint("num_slots > 0", name="positive_num_slots"),
    )

    stream_id: Mapped[UUID] = mapped_column(
        ForeignKey("streams.id"),
        primary_key=True,
    )
    port_mac_address: Mapped[str] = mapped_column(
        ForeignKey("ports.mac_address"),
        primary_key=True,
    )
    start_idx: Mapped[int] = mapped_column(BigInteger)
    num_slots: Mapped[int] = mapped_column(BigInteger)
    stream: Mapped[StreamModel] = relationship(back_populates="allocations")
    port: Mapped[PortModel] = relationship(back_populates="allocations")
