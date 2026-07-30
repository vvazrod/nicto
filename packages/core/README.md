# Nicto core

`nicto-core` runs the scheduling gRPC service. Its in-memory SQLite database is
owned by `Database`, which creates the ORM schema at startup and releases the
engine at shutdown.

## Configuration

The gRPC server reads these environment variables when `nicto` starts:

| Variable | Default | Notes |
| --- | --- | --- |
| `NICTO_HYPERPERIOD` | — | Required schedule duration, in nanoseconds. Must be divisible by the tick granularity. |
| `NICTO_TICK_GRANULARITY` | — | Required duration of a single schedule slot, in nanoseconds. |
| `NICTO_GRPC_SERVER_ADDRESS` | `127.0.0.1` | |
| `NICTO_GRPC_SERVER_PORT` | `50051` | |
| `NICTO_NETWORK_CONTROLLER` | `in-memory` | Set to `in-memory` or `timon`. |
| `NICTO_IN_MEMORY_TOPOLOGY_PATH` | — | Required when `NICTO_NETWORK_CONTROLLER=in-memory`. |
| `NICTO_TIMON_ADDRESS` | — | Required when `NICTO_NETWORK_CONTROLLER=timon`. |
| `NICTO_TIMON_PORT` | — | Required when `NICTO_NETWORK_CONTROLLER=timon`. |

The in-memory topology file contains `bridges`, `nodes`, and `links` arrays.
Bridges define a hostname and ports. Nodes define a MAC address and attach to
exactly one bridge port. Links reference bridge ports and define their
characteristics:

```json
{
  "bridges": [
    {"hostname": "switch-a", "ports": [{"name": "eth0"}, {"name": "eth1"}]},
    {"hostname": "switch-b", "ports": [{"name": "eth0"}]}
  ],
  "nodes": [
    {
      "mac_address": "00:11:22:33:44:55",
      "bridge": "switch-a",
      "port": "eth1"
    }
  ],
  "links": [
    {
      "source": {"bridge": "switch-a", "port": "eth0"},
      "destination": {"bridge": "switch-b", "port": "eth0"},
      "speed": 1000,
      "propagation_delay": 10
    }
  ]
}
```

- `models.py` defines framework-independent domain objects, including Ethernet
  bridges, nodes, ports, links, and stream port allocations.
- `orm_models.py` contains the private SQLAlchemy table mappings.
- `repositories.py` owns transactions and translates between domain and ORM
  models.
- `serialization.py` translates protobuf messages to and from domain models.
- `server.py` coordinates gRPC requests through these layers.
