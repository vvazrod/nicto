import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

DEFAULT_GRPC_SERVER_ADDRESS = "127.0.0.1"
DEFAULT_GRPC_SERVER_PORT = 50051
DEFAULT_NETWORK = "simulated"
MIN_GRPC_SERVER_PORT = 1
MAX_GRPC_SERVER_PORT = 65535


@dataclass(frozen=True, slots=True)
class Config:
    """Application configuration."""

    hyperperiod: int
    tick_granularity: int
    grpc_server_address: str = DEFAULT_GRPC_SERVER_ADDRESS
    grpc_server_port: int = DEFAULT_GRPC_SERVER_PORT
    network: str = DEFAULT_NETWORK
    topology_path: Path | None = None

    def __post_init__(self) -> None:
        """Validate schedule dimensions and derive an integral slot count."""
        if self.hyperperiod <= 0:
            msg = "Hyperperiod must be positive"
            raise ValueError(msg)
        if self.tick_granularity <= 0:
            msg = "Tick granularity must be positive"
            raise ValueError(msg)
        if self.hyperperiod % self.tick_granularity != 0:
            msg = "Hyperperiod must be divisible by tick granularity"
            raise ValueError(msg)

    @property
    def total_slots(self) -> int:
        """Return the number of discrete slots in one hyperperiod."""
        return self.hyperperiod // self.tick_granularity

    @classmethod
    def from_env(cls, environment: Mapping[str, str] | None = None) -> "Config":
        """Build configuration from environment variables."""
        environment = os.environ if environment is None else environment
        hyperperiod = _read_hyperperiod(environment)
        tick_granularity = _read_tick_granularity(environment)
        grpc_address = _read_grpc_address(environment)
        grpc_port = _read_grpc_port(environment)
        network = _read_network(environment)

        return cls(
            hyperperiod=hyperperiod,
            tick_granularity=tick_granularity,
            grpc_server_address=grpc_address,
            grpc_server_port=grpc_port,
            network=network,
            topology_path=_read_topology_path(environment),
        )


def _read_hyperperiod(environment: Mapping[str, str]) -> int:
    hyperperiod_value = environment.get("NICTO_HYPERPERIOD")
    if not hyperperiod_value:
        msg = "NICTO_HYPERPERIOD must be set"
        raise ValueError(msg)
    try:
        hyperperiod = int(hyperperiod_value)
    except ValueError as error:
        msg = "NICTO_HYPERPERIOD must be an integer"
        raise ValueError(msg) from error

    return hyperperiod


def _read_tick_granularity(environment: Mapping[str, str]) -> int:
    tick_value = environment.get("NICTO_TICK_GRANULARITY")
    if not tick_value:
        msg = "NICTO_TICK_GRANULARITY must be set"
        raise ValueError(msg)
    try:
        tick = int(tick_value)
    except ValueError as error:
        msg = "NICTO_TICK_GRANULARITY must be an integer"
        raise ValueError(msg) from error

    return tick


def _read_grpc_address(environment: Mapping[str, str]) -> str:
    address = environment.get("NICTO_GRPC_SERVER_ADDRESS", DEFAULT_GRPC_SERVER_ADDRESS).strip()
    if not address:
        msg = "NICTO_GRPC_SERVER_ADDRESS must not be empty"
        raise ValueError(msg)
    return address


def _read_grpc_port(environment: Mapping[str, str]) -> int:
    port_value = environment.get("NICTO_GRPC_SERVER_PORT", str(DEFAULT_GRPC_SERVER_PORT)).strip()
    if not port_value:
        msg = "NICTO_GRPC_SERVER_PORT must be set when using the timon network controller"
        raise ValueError(msg)
    try:
        port = int(port_value)
    except ValueError as error:
        msg = "NICTO_GRPC_SERVER_PORT must be an integer"
        raise ValueError(msg) from error

    if not MIN_GRPC_SERVER_PORT <= port <= MAX_GRPC_SERVER_PORT:
        msg = "NICTO_GRPC_SERVER_PORT must be between 1 and 65535"
        raise ValueError(msg)
    return port


def _read_network(environment: Mapping[str, str]) -> str:
    controller = environment.get("NICTO_NETWORK_CONTROLLER", DEFAULT_NETWORK).strip()
    if controller not in {"simulated", "safran"}:
        msg = "NICTO_NETWORK must be either 'simulated' or 'safran'"
        raise ValueError(msg)
    return controller


def _read_topology_path(environment: Mapping[str, str]) -> Path:
    topology_path = environment.get("NICTO_TOPOLOGY_PATH", "").strip()
    if not topology_path:
        msg = "NICTO_TOPOLOGY_PATH must be set"
        raise ValueError(msg)
    return Path(topology_path)
