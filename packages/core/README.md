# Nicto core

`nicto-core` runs the scheduling gRPC service. Its in-memory SQLite database is
owned by `Database`, which creates the ORM schema at startup and releases the
engine at shutdown.

- `models.py` defines framework-independent domain objects, including Ethernet
  devices, ports, links, and stream port allocations.
- `orm_models.py` contains the private SQLAlchemy table mappings.
- `repositories.py` owns transactions and translates between domain and ORM
  models.
- `serialization.py` translates protobuf messages to and from domain models.
- `server.py` coordinates gRPC requests through these layers.