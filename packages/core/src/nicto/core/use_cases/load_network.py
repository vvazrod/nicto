from nicto.core.ports.network import NetworkController
from nicto.core.ports.persistence import NetworkRepository


class LoadNetworkUseCase:
    """Load the controller topology into persistent storage."""

    def __init__(self, repository: NetworkRepository, controller: NetworkController) -> None:
        self._repository = repository
        self._controller = controller

    async def execute(self) -> None:
        """Persist all nodes and links returned by the network controller."""
        nodes, links = await self._controller.get_topology()

        for node in nodes:
            created_node = await self._repository.create_node(node)
            if created_node != node:
                msg = f"Failed to persist node {node.hostname}"
                raise RuntimeError(msg)

        for link in links:
            created_link = await self._repository.create_link(link)
            if created_link != link:
                msg = (
                    "Failed to persist link between "
                    f"{link.port_a_mac_address} and {link.port_b_mac_address}"
                )
                raise RuntimeError(msg)
