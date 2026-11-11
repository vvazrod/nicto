import json
from pathlib import Path

from nicto.application.ports import NetworkController
from nicto.domain.models import Link, Node


class InMemoryNetworkController(NetworkController):
    """Provide a network controller backed by a topology JSON file."""

    def __init__(self, topology_path: Path) -> None:
        """Instantiate an in-memory network controller using a topology file."""
        self.nodes, self.links = self._load_topology_from_file(topology_path)

    async def get_topology(self) -> tuple[list[Node], list[Link]]:
        """Get the network topology from the in-memory network."""
        return self.nodes.copy(), self.links.copy()

    @staticmethod
    def _load_topology_from_file(
        topology_path: Path,
    ) -> tuple[list[Node], list[Link]]:
        with topology_path.open(encoding="utf-8") as topology_file:
            topology = json.load(topology_file)

        nodes = [Node.model_validate(node) for node in topology["nodes"]]
        links = [Link.model_validate(link) for link in topology["links"]]

        return nodes, links
