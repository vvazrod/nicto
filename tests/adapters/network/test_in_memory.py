import asyncio
import json
import pathlib
from pathlib import Path
from typing import Any

import pytest

from nicto.adapters.network.in_memory import InMemoryNetworkController

TOPOLOGY: dict[str, list[dict[str, Any]]] = {
    "nodes": [
        {
            "hostname": "switch-a",
            "ports": [
                {"mac_address": "00:11:22:33:44:55", "name": "eth0"},
                {"mac_address": "00:11:22:33:44:56", "name": "eth1"},
            ],
        },
        {
            "hostname": "switch-b",
            "ports": [
                {"mac_address": "00:11:22:33:45:55", "name": "eth0"},
                {"mac_address": "00:11:22:33:45:56", "name": "eth1"},
            ],
        },
        {
            "hostname": "endnode-a",
            "ports": [
                {"mac_address": "00:11:22:33:46:55", "name": "eth0"},
            ],
        },
        {
            "hostname": "endnode-b",
            "ports": [
                {"mac_address": "00:11:22:33:47:55", "name": "eth0"},
            ],
        },
    ],
    "links": [
        {
            "port_a_mac_address": "00:11:22:33:46:55",
            "port_b_mac_address": "00:11:22:33:44:55",
            "speed": 1000,
            "propagation_delay": 10,
        },
        {
            "port_a_mac_address": "00:11:22:33:44:56",
            "port_b_mac_address": "00:11:22:33:45:55",
            "speed": 1000,
            "propagation_delay": 10,
        },
        {
            "port_a_mac_address": "00:11:22:33:45:56",
            "port_b_mac_address": "00:11:22:33:47:55",
            "speed": 1000,
            "propagation_delay": 10,
        },
    ],
}


@pytest.fixture
def controller(tmp_path: pathlib.Path) -> InMemoryNetworkController:
    """In-memory network controller fixture."""
    topology_path = Path(tmp_path) / "topology.json"
    topology_path.write_text(json.dumps(TOPOLOGY), encoding="utf-8")
    return InMemoryNetworkController(topology_path=topology_path)


def test_get_topology(controller: InMemoryNetworkController) -> None:
    """Test the topology getter method."""
    nodes, links = asyncio.run(controller.get_topology())

    assert len(nodes) == len(TOPOLOGY["nodes"])
    assert len(links) == len(TOPOLOGY["links"])
    assert len(nodes[0].ports) != 0
