import asyncio

from nicto.core.infra.grpc.app import serve


def main() -> None:
    """Run the application."""
    asyncio.run(serve())
