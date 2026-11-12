import logging
from collections.abc import Iterable

from pydantic_extra_types.mac_address import MacAddress

from nicto.application.ports import FlexcurvePublisher, NetworkRepository
from nicto.config import Config
from nicto.domain.flexcurve import calculate_flexcurve
from nicto.domain.models import Port

logger = logging.getLogger(__name__)

MAX_FLEXCURVE_STREAM_SLOTS = 99


class PublishFlexcurveUseCase:
    """Compute and publish the flexcurve of the egress ports whose schedules changed.

    The flexcurve of a port gives, for each stream size from 1 to 99 slots, the number of start positions
    available in its schedule. The flexcurve of a path is the element-wise minimum of those of its ports.
    """

    def __init__(self, network_repository: NetworkRepository, publisher: FlexcurvePublisher, config: Config) -> None:
        self._network_repository = network_repository
        self._publisher = publisher
        self._config = config

    async def publish_ports(self, port_macs: Iterable[MacAddress]) -> None:
        """Publish the flexcurve of each given port, logging instead of raising on failure.

        A presentation failure must never fail a request whose changes are already committed.
        """
        try:
            for mac_address in dict.fromkeys(port_macs):
                port = await self._network_repository.get_port_by_mac(mac_address)
                if port is not None:
                    await self._publish(port)
        except Exception:
            logger.exception("Failed to publish the flexcurve of the changed ports")

    async def publish_all(self) -> None:
        """Publish the flexcurve of every port, logging instead of raising on failure."""
        try:
            nodes, _ = await self._network_repository.get_topology()
            for node in nodes:
                for port in node.ports:
                    await self._publish(port)
        except Exception:
            logger.exception("Failed to publish the flexcurves of all ports")

    async def _publish(self, port: Port) -> None:
        gaps = port.gaps(self._config.total_slots)
        flexcurve = [calculate_flexcurve(size, gaps) for size in range(1, MAX_FLEXCURVE_STREAM_SLOTS + 1)]
        await self._publisher.publish_flexcurve(port.mac_address, flexcurve)
