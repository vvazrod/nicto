from nicto.core.entities import Link, Node, Port
from nicto.core.ports.persistence import NetworkRepository, StreamRepository
from pydantic_extra_types.mac_address import MacAddress


class InMemoryNetworkRepository(NetworkRepository):
    """Store network data in memory."""

    def __init__(self) -> None:
        self.nodes: list[Node] = []
        self.links: list[Link] = []

    async def create_link(self, link: Link) -> Link:
        """Persist a network link."""
        self.links.append(link)
        return link

    async def create_node(self, node: Node) -> Node:
        """Persist a network node."""
        self.nodes.append(node)
        return node

    async def get_port_by_mac(self, mac_address: MacAddress) -> Port | None:
        """Retrieve a network port identified by its MAC address."""
        for node in self.nodes:
            for port in node.ports:
                if port.mac_address == mac_address:
                    return port

        return None


class InMemoryStreamRepository(StreamRepository):
    """Store stream data in memory."""
