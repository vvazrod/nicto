from nicto.core.entities import Stream
from nicto.core.infra.db.models import AllocationModel, StreamModel
from nicto.core.infra.db.session import Database
from nicto.core.ports.persistence import StreamRepository
from sqlalchemy import select
from sqlalchemy.orm import selectinload


class SqlaStreamRepository(StreamRepository):
    def __init__(self, database: Database) -> None:
        self._database = database

    async def create_stream(self, stream: Stream) -> Stream:
        model = StreamModel(
            src_mac=stream.src_mac,
            dst_mac=stream.dst_mac,
            vlan_id=stream.vlan_id,
            priority=stream.priority,
            max_frame_size=stream.max_frame_size,
            max_num_frames=stream.max_num_frames,
            measurement_interval=stream.measurement_interval,
            deadline=stream.deadline,
        )

        async with self._database.session() as session:
            session.add(model)
            await session.commit()
            response = (
                await session.scalars(
                    select(StreamModel)
                    .options(selectinload(StreamModel.allocations).selectinload(AllocationModel.port))
                    .where(StreamModel.id == model.id),
                )
            ).one()

        return Stream(
            id=response.id,
            src_mac=response.src_mac,
            dst_mac=response.dst_mac,
            vlan_id=response.vlan_id,
            priority=response.priority,
            max_frame_size=response.max_frame_size,
            max_num_frames=response.max_num_frames,
            measurement_interval=response.measurement_interval,
            deadline=response.deadline,
            created_at=response.created_at,
        )
