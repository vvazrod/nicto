import pytest
from pydantic_extra_types.mac_address import MacAddress
from sqlalchemy.ext.asyncio import AsyncSession

from nicto.adapters.persistence.repositories import SqlaNetworkRepository
from nicto.adapters.persistence.unit_of_work import SqlaUnitOfWork
from nicto.application.use_cases.load_network import LoadNetworkUseCase
from nicto.domain.models import Link, Node, Port
from tests.application.use_cases.conftest import MockNetworkController, MockNetworkRepository, MockUnitOfWork

NODES = [
    Node(
        hostname="switch-a",
        ports=[Port(mac_address=MacAddress("00:11:22:33:44:55"), name="eth0")],
    ),
    Node(
        hostname="switch-b",
        ports=[Port(mac_address=MacAddress("00:11:22:33:44:56"), name="eth0")],
    ),
]
LINKS = [
    Link(
        port_a_mac_address=MacAddress("00:11:22:33:44:55"),
        port_b_mac_address=MacAddress("00:11:22:33:44:56"),
        speed=1000,
        propagation_delay=10,
    ),
]


async def test_execute_persists_topology_and_commits(
    network_repository: MockNetworkRepository,
    network_controller: MockNetworkController,
    unit_of_work: MockUnitOfWork,
) -> None:
    """Test the controller topology is stored in the repository and committed."""
    network_controller.nodes, network_controller.links = NODES, LINKS
    use_case = LoadNetworkUseCase(network_repository, network_controller, unit_of_work)

    await use_case.execute()

    assert network_repository.nodes == NODES
    assert network_repository.links == LINKS
    assert unit_of_work.commits == 1


async def test_execute_persists_topology_in_database(
    db_session: AsyncSession,
    network_controller: MockNetworkController,
) -> None:
    """Test loading the topology through the SQLAlchemy adapters."""
    network_controller.nodes, network_controller.links = NODES, LINKS
    repository = SqlaNetworkRepository(db_session)
    use_case = LoadNetworkUseCase(repository, network_controller, SqlaUnitOfWork(db_session))

    await use_case.execute()

    for node in NODES:
        assert await repository.get_port_by_mac(node.ports[0].mac_address) == node.ports[0]


async def test_execute_raises_when_node_persistence_fails(
    network_repository: MockNetworkRepository,
    network_controller: MockNetworkController,
    unit_of_work: MockUnitOfWork,
) -> None:
    """Test node persistence failures are surfaced and nothing is committed."""
    network_controller.nodes, network_controller.links = NODES, LINKS
    network_repository.fail_node = True
    use_case = LoadNetworkUseCase(network_repository, network_controller, unit_of_work)

    with pytest.raises(RuntimeError, match="Failed to persist node switch-a"):
        await use_case.execute()

    assert unit_of_work.commits == 0


async def test_execute_raises_when_link_persistence_fails(
    network_repository: MockNetworkRepository,
    network_controller: MockNetworkController,
    unit_of_work: MockUnitOfWork,
) -> None:
    """Test link persistence failures are surfaced and nothing is committed."""
    network_controller.nodes, network_controller.links = NODES, LINKS
    network_repository.fail_link = True
    use_case = LoadNetworkUseCase(network_repository, network_controller, unit_of_work)

    with pytest.raises(RuntimeError, match="Failed to persist link"):
        await use_case.execute()

    assert unit_of_work.commits == 0
