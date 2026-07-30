import asyncio

from nicto.core.config import Config
from nicto.core.infra.grpc.server import serve


def main() -> None:
    """Run the application."""
    asyncio.run(serve(Config.from_env()))
