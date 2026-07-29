import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for ORM models."""


class DeviceModel(Base):
    """Database representation of an Ethernet device."""

    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(primary_key=True)
    hostname: Mapped[str] = mapped_column(String, unique=True)
    ports: Mapped[list["PortModel"]] = relationship(
        back_populates="device",
        cascade="all, delete-orphan",
    )


class PortModel(Base):
    """Database representation of an Ethernet port."""

    __tablename__ = "ports"

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"), nullable=False)
    name: Mapped[str] = mapped_column(String)
    device: Mapped[DeviceModel] = relationship(back_populates="ports")
    source_links: Mapped[list["LinkModel"]] = relationship(
        back_populates="source_port",
        foreign_keys="LinkModel.source_port_id",
    )
    destination_links: Mapped[list["LinkModel"]] = relationship(
        back_populates="destination_port",
        foreign_keys="LinkModel.destination_port_id",
    )
    allocations: Mapped[list["AllocationModel"]] = relationship(back_populates="port")


class LinkModel(Base):
    """Database representation of an Ethernet connection."""

    __tablename__ = "links"
    __table_args__ = (
        CheckConstraint("speed IN (10, 100, 1000)", name="valid_link_speed"),
        CheckConstraint("propagation_delay >= 0", name="nonnegative_propagation_delay"),
        CheckConstraint("source_port_id <> destination_port_id", name="distinct_link_ports"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source_port_id: Mapped[int] = mapped_column(ForeignKey("ports.id"), nullable=False)
    destination_port_id: Mapped[int] = mapped_column(ForeignKey("ports.id"), nullable=False)
    speed: Mapped[int] = mapped_column(Integer)
    propagation_delay: Mapped[int] = mapped_column(BigInteger)
    source_port: Mapped[PortModel] = relationship(
        back_populates="source_links",
        foreign_keys=[source_port_id],
    )
    destination_port: Mapped[PortModel] = relationship(
        back_populates="destination_links",
        foreign_keys=[destination_port_id],
    )


class StreamModel(Base):
    """Database representation of a scheduling stream."""

    __tablename__ = "streams"

    id: Mapped[int] = mapped_column(primary_key=True)
    src_mac: Mapped[str] = mapped_column(String(17))
    dst_mac: Mapped[str] = mapped_column(String(17))
    vlan_id: Mapped[int] = mapped_column(Integer)
    priority: Mapped[int] = mapped_column(Integer)
    max_frame_size: Mapped[int] = mapped_column(Integer)
    max_num_frames: Mapped[int] = mapped_column(Integer)
    measurement_interval: Mapped[int] = mapped_column(Integer)
    deadline: Mapped[int] = mapped_column(BigInteger)
    allocations: Mapped[list["AllocationModel"]] = relationship(
        back_populates="stream",
        cascade="all, delete-orphan",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )


class AllocationModel(Base):
    """Database representation of a stream's port allocation."""

    __tablename__ = "allocations"
    __table_args__ = (CheckConstraint("start_slot >= 0", name="nonnegative_start_slot"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    stream_id: Mapped[int] = mapped_column(ForeignKey("streams.id"), nullable=False)
    port_id: Mapped[int] = mapped_column(ForeignKey("ports.id"), nullable=False)
    start_slot: Mapped[int] = mapped_column(BigInteger)
    stream: Mapped[StreamModel] = relationship(back_populates="allocations")
    port: Mapped[PortModel] = relationship(back_populates="allocations")
