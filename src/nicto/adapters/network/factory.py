from nicto.adapters.network.in_memory import InMemoryNetworkController
from nicto.application.ports import NetworkController
from nicto.config import Config


def create_network_controller(config: Config) -> NetworkController:
    """Create the network controller selected by the runtime configuration."""
    if config.network == "simulated":
        if config.topology_path is None:
            msg = "In-memory network controller requires a topology path"
            raise ValueError(msg)
        return InMemoryNetworkController(topology_path=config.topology_path)

    msg = f"Unsupported network: {config.network}"
    raise ValueError(msg)
