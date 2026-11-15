# nicto

**Nifty controller for TAS operation.** `nicto` is a web service for automatic stream scheduling in networks that
use the IEEE 802.1Qbv Time-Aware Shaper (TAS).

Given a network topology and a set of time-sensitive streams, `nicto`:

1. finds a path between the source and destination of each stream,
2. computes a conflict-free transmission schedule (gate slots on each port along the path) inside a repeating
   *hyperperiod*, and
3. keeps the schedule consistent as streams are inserted and removed at runtime.

Schedules are computed with the *flexcurve* algorithm, which tracks the free gaps of every port, and can be
optimised either for throughput or for end-to-end latency. State is stored in a SQL database, and the per-port
flexcurves can optionally be published to EPICS process variables.

Typical uses: runtime admission control and scheduling of deterministic traffic in industrial, scientific
(e.g. control systems at large facilities) and automotive TSN networks; research on TAS scheduling algorithms.

## Docker

Build the image:

```sh
docker build -t nicto .
```

Create a topology file (see [Topology file](#topology-file)) and run the container:

```sh
docker run -p 8000:8000 \
  -v nicto-data:/data \
  -v ./topology.json:/config/topology.json:ro \
  -e NICTO_HYPERPERIOD=1000000 \
  -e NICTO_TICK_GRANULARITY=1000 \
  -e NICTO_TOPOLOGY_PATH=/config/topology.json \
  nicto
```

The API is then available at `http://localhost:8000` (interactive docs at `/docs`). In the container,
`NICTO_DATABASE_URL` defaults to `sqlite+aiosqlite:////data/nicto.db`, so mounting a volume at `/data` keeps the
database file outside the container. Note that the schema is currently recreated on every startup.

### API

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/api/v1/streams` | Insert a stream; returns `201` with its path/schedule allocations, `404` if a port is unknown, `422` if unfeasible. |
| `DELETE` | `/api/v1/streams/{stream_id}` | Remove a stream (`<source MAC>-<4 hex digit unique ID>`); returns `204`. |

Example:

```sh
curl -X POST localhost:8000/api/v1/streams -H 'Content-Type: application/json' -d '{
  "unique_id": 1,
  "src_mac_address": "00:11:22:33:44:55",
  "dst_mac_address": "00:11:22:33:44:66",
  "max_frame_size": 64,
  "max_interval_frames": 1,
  "interval": 100000,
  "max_latency": 500000
}'
```

`vlan` and `priority` are optional.

### Topology file

The topology is a JSON file with `nodes` and `links`. Each node has a hostname and ports; each port has a MAC
address and a name. Links join two ports by MAC address, with `speed` in Mbps and `propagation_delay` in ns:

```json
{
  "nodes": [
    {"hostname": "switch-a", "ports": [
      {"mac_address": "00:11:22:33:44:01", "name": "eth0"},
      {"mac_address": "00:11:22:33:44:02", "name": "eth1"}
    ]},
    {"hostname": "switch-b", "ports": [
      {"mac_address": "00:11:22:33:44:03", "name": "eth0"}
    ]}
  ],
  "links": [
    {
      "port_a_mac_address": "00:11:22:33:44:01",
      "port_b_mac_address": "00:11:22:33:44:03",
      "speed": 1000,
      "propagation_delay": 10
    }
  ]
}
```

## Benchmarks

Benchmarks live in `benchmarks/` and need [uv](https://docs.astral.sh/uv/) and the development dependencies:

```sh
uv sync
```

| Benchmark | Description |
| --- | --- |
| `flexcurve_line_incremental.py` | Inserts 100 streams sequentially over a four-node line network, timing each insertion for both Flexcurve profiles. |
| `flexcurve_spine_leaf_churn.py` | Inserts 100 and removes 50 random streams on a spine-leaf network, for both profiles; also records unfeasible insertions. |

Run them (results are written as CSV files to `benchmarks/results/` unless `--output-dir` is given):

```sh
uv run python benchmarks/flexcurve_line_incremental.py [--iterations N] [--output-dir DIR]
uv run python benchmarks/flexcurve_spine_leaf_churn.py [--iterations N] [--seed S] [--output-dir DIR]
```

| Option | Description |
| --- | --- |
| `--iterations` | Runs per profile. |
| `--output-dir` | Directory for the CSV files. |
| `--seed` | Base seed of the random workloads (spine-leaf benchmark only). |

Plots are [marimo](https://marimo.io) notebooks in `benchmarks/notebooks/`. Open one interactively or run it
headless to regenerate the figures in `benchmarks/results/figures/`:

```sh
uv run marimo edit benchmarks/notebooks/flexcurve_line_incremental.py
uv run python benchmarks/notebooks/flexcurve_line_incremental.py
```

## Configuration

`nicto` is configured through environment variables, read at startup.

| Variable | Default | Description and values |
| --- | --- | --- |
| `NICTO_HYPERPERIOD` | — (required) | Schedule duration in nanoseconds. Positive integer, divisible by `NICTO_TICK_GRANULARITY`. |
| `NICTO_TICK_GRANULARITY` | — (required) | Duration of one schedule slot in nanoseconds. Positive integer. |
| `NICTO_TOPOLOGY_PATH` | — (required) | Path to the JSON topology file. |
| `NICTO_API_HOST` | `0.0.0.0` | Address the HTTP API binds to. Non-empty string. |
| `NICTO_API_PORT` | `8000` | Port the HTTP API listens on. Integer. |
| `NICTO_NETWORK_CONTROLLER` | `simulated` | Source of the network topology. Only `simulated` (loads the topology file) is supported. |
| `NICTO_DATABASE_URL` | `sqlite+aiosqlite:///:memory:` (`sqlite+aiosqlite:////data/nicto.db` in Docker) | SQLAlchemy async database URL, e.g. `sqlite+aiosqlite:///nicto.db`. |
| `NICTO_PATH_SOLVER` | `dijkstra` | Path solver. Only `dijkstra` is supported: it picks the path with the highest flexcurve for the stream, then the lowest delay. |
| `NICTO_SCHEDULE_SOLVER` | `flexcurve` | Schedule solver. Only `flexcurve` is supported. |
| `NICTO_SCHEDULE_PROFILE` | `max_throughput` | `max_throughput` takes the first feasible gaps; `min_latency` searches for the lowest end-to-end latency. |
| `NICTO_PRESENTATION` | `none` | `none` or `epics`. `epics` requires the `nicto[epics]` extra (not installed in the Docker image by default) and puts the flexcurve of each port to the PV `NICTO:FLEXCURVE:<port MAC with dashes>` at startup and after every insert or removal affecting the port. The flexcurve of a path is the element-wise minimum of those of its ports. |

## Development

```sh
uv sync
uv run pytest
uv run ruff check && uv run mypy .
```
