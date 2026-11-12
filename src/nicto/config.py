import os
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

DEFAULT_GRPC_SERVER_ADDRESS = "127.0.0.1"
DEFAULT_GRPC_SERVER_PORT = 50051
DEFAULT_API_HOST = "0.0.0.0"  # noqa: S104
DEFAULT_API_PORT = 8000
DEFAULT_NETWORK = "simulated"
DEFAULT_DATABASE_URL = "sqlite+aiosqlite:///:memory:"
DEFAULT_PATH_SOLVER = "dijkstra"
DEFAULT_SCHEDULE_SOLVER = "flexcurve"
SUPPORTED_PATH_SOLVERS = frozenset({DEFAULT_PATH_SOLVER})
SUPPORTED_SCHEDULE_SOLVERS = frozenset({DEFAULT_SCHEDULE_SOLVER})
DEFAULT_PRESENTATION = "none"
SUPPORTED_PRESENTATIONS = frozenset({DEFAULT_PRESENTATION, "epics"})


class FlexcurveSolverProfile(StrEnum):
    """Allocation strategy followed by the Flexcurve schedule solver."""

    MAX_THROUGHPUT = "max_throughput"
    MIN_LATENCY = "min_latency"


DEFAULT_FLEXCURVE_SOLVER_PROFILE = FlexcurveSolverProfile.MAX_THROUGHPUT


@dataclass(frozen=True, slots=True)
class Config:
    """Application configuration."""

    hyperperiod: int
    tick_granularity: int
    api_host: str = DEFAULT_API_HOST
    api_port: int = DEFAULT_API_PORT
    network: str = DEFAULT_NETWORK
    topology_path: Path | None = None
    database_url: str = DEFAULT_DATABASE_URL
    path_solver: str = DEFAULT_PATH_SOLVER
    schedule_solver: str = DEFAULT_SCHEDULE_SOLVER
    schedule_profile: FlexcurveSolverProfile = DEFAULT_FLEXCURVE_SOLVER_PROFILE
    presentation: str = DEFAULT_PRESENTATION

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
        network = _read_network(environment)
        presentation = _read_choice(environment, "NICTO_PRESENTATION", DEFAULT_PRESENTATION, SUPPORTED_PRESENTATIONS)

        return cls(
            hyperperiod=hyperperiod,
            tick_granularity=tick_granularity,
            api_host=_read_api_host(environment),
            api_port=_read_api_port(environment),
            network=network,
            topology_path=_read_topology_path(environment),
            database_url=_read_database_url(environment),
            path_solver=_read_choice(environment, "NICTO_PATH_SOLVER", DEFAULT_PATH_SOLVER, SUPPORTED_PATH_SOLVERS),
            schedule_solver=_read_choice(
                environment,
                "NICTO_SCHEDULE_SOLVER",
                DEFAULT_SCHEDULE_SOLVER,
                SUPPORTED_SCHEDULE_SOLVERS,
            ),
            schedule_profile=_read_schedule_profile(environment),
            presentation=presentation,
        )


def _read_database_url(environment: Mapping[str, str]) -> str:
    database_url = environment.get("NICTO_DATABASE_URL", DEFAULT_DATABASE_URL).strip()
    if not database_url:
        msg = "NICTO_DATABASE_URL must not be empty"
        raise ValueError(msg)
    return database_url


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


def _read_api_host(environment: Mapping[str, str]) -> str:
    host = environment.get("NICTO_API_HOST", DEFAULT_API_HOST).strip()
    if not host:
        msg = "NICTO_API_HOST must not be empty"
        raise ValueError(msg)
    return host


def _read_api_port(environment: Mapping[str, str]) -> int:
    port_value = environment.get("NICTO_API_PORT", DEFAULT_API_PORT)
    if not port_value:
        msg = "NICTO_API_PORT must be set"
        raise ValueError(msg)
    try:
        port = int(port_value)
    except ValueError as error:
        msg = "NICTO_API_PORT must be an integer"
        raise ValueError(msg) from error

    return port


def _read_network(environment: Mapping[str, str]) -> str:
    controller = environment.get("NICTO_NETWORK_CONTROLLER", DEFAULT_NETWORK).strip()
    if controller != "simulated":
        msg = "NICTO_NETWORK must be 'simulated'"
        raise ValueError(msg)
    return controller


def _read_topology_path(environment: Mapping[str, str]) -> Path:
    topology_path = environment.get("NICTO_TOPOLOGY_PATH", "").strip()
    if not topology_path:
        msg = "NICTO_TOPOLOGY_PATH must be set"
        raise ValueError(msg)
    return Path(topology_path)


def _read_choice(environment: Mapping[str, str], name: str, default: str, choices: frozenset[str]) -> str:
    value = environment.get(name, default).strip()
    if value not in choices:
        msg = f"{name} must be one of: {', '.join(sorted(choices))}"
        raise ValueError(msg)
    return value


def _read_schedule_profile(environment: Mapping[str, str]) -> FlexcurveSolverProfile:
    value = environment.get("NICTO_SCHEDULE_PROFILE", DEFAULT_FLEXCURVE_SOLVER_PROFILE.value).strip()
    try:
        return FlexcurveSolverProfile(value)
    except ValueError as error:
        choices = ", ".join(profile.value for profile in FlexcurveSolverProfile)
        msg = f"NICTO_SCHEDULE_PROFILE must be one of: {choices}"
        raise ValueError(msg) from error
