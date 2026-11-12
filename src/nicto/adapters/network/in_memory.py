import json
from pathlib import Path

import aiofiles

from nicto.application.ports import NetworkController
from nicto.domain.models import Link, Node


class InMemoryNetworkController(NetworkController):
    """Provide a network controller backed by a topology JSON file."""

    def __init__(self, topology_path: Path) -> None:
        """Instantiate an in-memory network controller using a topology file."""
        self._topology_path = topology_path
        self._nodes: list[Node] | None = None
        self._links: list[Link] | None = None

    async def get_topology(self) -> tuple[list[Node], list[Link]]:
        """Get the network topology from the in-memory network."""
        if self._nodes is None or self._links is None:
            self._nodes, self._links = await self._load_topology_from_file(self._topology_path)
        return self._nodes.copy(), self._links.copy()

    @staticmethod
    async def _load_topology_from_file(
        topology_path: Path,
    ) -> tuple[list[Node], list[Link]]:
        async with aiofiles.open(topology_path, encoding="utf-8") as topology_file:
            contents = await topology_file.read()
            topology = json.loads(contents)

        nodes = [Node.model_validate(node) for node in topology["nodes"]]
        links = [Link.model_validate(link) for link in topology["links"]]

        return nodes, links
