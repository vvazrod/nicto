from nicto.adapters.solvers.dijkstra import DijkstraPathSolver
from nicto.adapters.solvers.flexcurve import FlexcurveSolver
from nicto.application.ports import PathSolver, ScheduleSolver
from nicto.config import Config


def create_path_solver(config: Config) -> PathSolver:
    """Create the path solver selected by the runtime configuration."""
    if config.path_solver == "dijkstra":
        return DijkstraPathSolver(config)

    msg = f"Unsupported path solver: {config.path_solver}"
    raise ValueError(msg)


def create_schedule_solver(config: Config) -> ScheduleSolver:
    """Create the schedule solver selected by the runtime configuration."""
    if config.schedule_solver == "flexcurve":
        return FlexcurveSolver(profile=config.schedule_profile)

    msg = f"Unsupported schedule solver: {config.schedule_solver}"
    raise ValueError(msg)
