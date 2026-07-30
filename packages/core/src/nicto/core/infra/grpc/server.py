import logging

from grpclib.server import Server
from grpclib.utils import graceful_exit
from nicto.core.adapters.network import create_network_controller
from nicto.core.adapters.persistence.sqla import SqlaNetworkRepository, SqlaStreamRepository
from nicto.core.config import Config
from nicto.core.infra.db.session import Database
from nicto.core.infra.grpc.services import SchedulingService
from nicto.core.use_cases.load_network import LoadNetworkUseCase

logger = logging.getLogger(__name__)


async def serve(config: Config) -> None:
    """Serve gRPC requests until shutdown."""
    db = Database()
    await db.create_schema()

    # Create the adapters
    network_repo = SqlaNetworkRepository(db)
    stream_repo = SqlaStreamRepository(db)
    controller = create_network_controller(config)

    use_case = LoadNetworkUseCase(repository=network_repo, controller=controller)
    try:
        await use_case.execute()

        # Create the gRPC server and its services
        server = Server([SchedulingService(network_repo, stream_repo, config)])
        with graceful_exit([server]):
            await server.start(config.grpc_server_address, config.grpc_server_port)
            logger.info("Listening on %s:%d", config.grpc_server_address, config.grpc_server_port)
            await server.wait_closed()
    finally:
        await db.dispose()
