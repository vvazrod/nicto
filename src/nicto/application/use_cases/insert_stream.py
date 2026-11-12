from nicto.application.ports import (
    NetworkRepository,
    PathSolver,
    ScheduleSolver,
    StreamRepository,
    UnitOfWork,
)
from nicto.application.use_cases.publish_flexcurve import PublishFlexcurveUseCase
from nicto.config import Config
from nicto.domain.models import Stream


class PortNotFoundError(Exception):
    """Raised when a stream endpoint does not match a known port."""


class PortNotConnectedError(Exception):
    """Raised when a stream endpoint is not connected to a network link."""


class StreamUnfeasibleError(Exception):
    """Raised when a stream cannot fit in the configured schedule."""


class InsertStreamUseCase:
    """Validate stream endpoint ports and persist requested streams."""

    def __init__(  # noqa: PLR0913, PLR0917
        self,
        network_repository: NetworkRepository,
        stream_repository: StreamRepository,
        unit_of_work: UnitOfWork,
        path_solver: PathSolver,
        schedule_solver: ScheduleSolver,
        config: Config,
        flexcurve_publication: PublishFlexcurveUseCase | None = None,
    ) -> None:
        self._network_repository = network_repository
        self._stream_repository = stream_repository
        self._unit_of_work = unit_of_work
        self._path_solver = path_solver
        self._schedule_solver = schedule_solver
        self._config = config
        self._flexcurve_publication = flexcurve_publication

    async def execute(self, stream: Stream) -> Stream:
        """Retrieve both endpoint ports before persisting the stream."""
        src_port = await self._network_repository.get_port_by_mac(stream.src_mac_address)
        dst_port = await self._network_repository.get_port_by_mac(stream.dst_mac_address)

        if src_port is None or dst_port is None:
            msg = "The stream source or destination port was not found"
            raise PortNotFoundError(msg)

        self._validate_schedule_alignment(stream)

        nodes, links = await self._network_repository.get_topology()
        path = self._path_solver.find_path(stream, nodes, links)
        allocations = self._schedule_solver.find_schedule(stream, path, self._config)
        scheduled_stream = stream.model_copy(update={"allocations": allocations})

        created_stream = await self._stream_repository.create_stream(scheduled_stream)
        await self._unit_of_work.commit()
        if self._flexcurve_publication is not None:
            await self._flexcurve_publication.publish_ports(
                allocation.port_mac_address for allocation in created_stream.allocations
            )
        return created_stream

    def _validate_schedule_alignment(self, stream: Stream) -> None:
        """Ensure the stream can be represented by the configured schedule."""
        if stream.interval <= 0:
            msg = "Stream interval must be positive"
            raise StreamUnfeasibleError(msg)
        if stream.max_interval_frames <= 0:
            msg = "Stream max interval frames must be positive"
            raise StreamUnfeasibleError(msg)
        if stream.interval % self._config.tick_granularity != 0:
            msg = "Stream interval must align with the configured tick granularity"
            raise StreamUnfeasibleError(msg)
        if self._config.hyperperiod % stream.interval != 0:
            msg = "Stream interval must divide the configured hyperperiod"
            raise StreamUnfeasibleError(msg)
