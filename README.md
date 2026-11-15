# Nicto

`nicto` runs the scheduling API. Persistence uses SQLAlchemy repositories that
receive a session factory. The factory helpers in `database.py` are reserved for
the top-level application container and unit tests.

## Configuration

The gRPC server reads these environment variables when `nicto` starts:

| Variable | Default | Notes |
| --- | --- | --- |
| `NICTO_HYPERPERIOD` | — | Required schedule duration, in nanoseconds. Must be divisible by the tick granularity. |
| `NICTO_TICK_GRANULARITY` | — | Required duration of a single schedule slot, in nanoseconds. |
| `NICTO_API_HOST` | `0.0.0.0` | Address the HTTP API binds to. |
| `NICTO_API_PORT` | `8000` | Port the HTTP API listens on. |
| `NICTO_NETWORK_CONTROLLER` | `in-memory` | |
| `NICTO_DATABASE_URL` | `sqlite+aiosqlite:///:memory:` | SQLAlchemy async database URL, e.g. `sqlite+aiosqlite:///nicto.db` for a file. |
| `NICTO_PATH_SOLVER` | `dijkstra` | Path solver. Dijkstra selects the path with the highest flexcurve for the stream, then the lowest delay. |
| `NICTO_SCHEDULE_SOLVER` | `flexcurve` | Schedule solver. |
| `NICTO_SCHEDULE_PROFILE` | `max_throughput` | `max_throughput` takes the first feasible gaps; `min_latency` searches for the lowest end-to-end latency. |
| `NICTO_IN_MEMORY_TOPOLOGY_PATH` | — | Required when `NICTO_NETWORK_CONTROLLER=in-memory`. |
| `NICTO_PRESENTATION` | `none` | Presentation backend: `none` or `epics` (requires the `nicto[epics]` extra). With `epics`, the flexcurve of each port is put to the PV `NICTO:FLEXCURVE:<port MAC with dashes>`, at startup and, for the ports of the stream, after every insert or removal. The flexcurve of a path is the element-wise minimum of those of its ports. |

## Docker

```sh
docker build -t nicto .
docker run -p 8000:8000 -v nicto-data:/data -v ./topology.json:/config/topology.json:ro \
  -e NICTO_HYPERPERIOD=1000000 -e NICTO_TICK_GRANULARITY=1000 \
  -e NICTO_TOPOLOGY_PATH=/config/topology.json nicto
```

In the container `NICTO_DATABASE_URL` defaults to `sqlite+aiosqlite:////data/nicto.db`,
so mount a volume at `/data` to keep the database file outside the container.
Note that the schema is currently recreated on every startup.

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
