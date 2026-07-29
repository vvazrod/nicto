import logging

from grpclib.server import Server
from grpclib.utils import graceful_exit
from nicto.core.adapters.persistence.sqla import SqlaStreamRepository
from nicto.core.infra.db.session import Database
from nicto.core.infra.grpc.handlers import SchedulingGrpcHandler

logger = logging.getLogger(__name__)


async def serve() -> None:
    """Serve gRPC requests until shutdown."""
    db = Database()
    await db.create_schema()

    # Create the adapters
    repository = SqlaStreamRepository(db)

    # create the gRPC server and handlers
    server = Server([SchedulingGrpcHandler(repository)])
    try:
        with graceful_exit([server]):
            await server.start("127.0.0.1", 50051)
            logger.info("Listening on 127.0.0.1:50051")
            await server.wait_closed()
    finally:
        await db.dispose()
