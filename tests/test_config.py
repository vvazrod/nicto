import pytest

from nicto.config import Config

TOTAL_SLOTS = 10


def test_total_slots() -> None:
    """Test schedule slots are derived from the configured time values."""
    config = Config(hyperperiod=10_000, tick_granularity=1_000)

    assert config.total_slots == TOTAL_SLOTS


@pytest.mark.parametrize(
    ("hyperperiod", "tick_granularity", "message"),
    [
        (0, 1_000, "Hyperperiod must be positive"),
        (10_000, 0, "Tick granularity must be positive"),
        (10_000, 3_000, "Hyperperiod must be divisible"),
    ],
)
def test_rejects_invalid_schedule_dimensions(
    hyperperiod: int,
    tick_granularity: int,
    message: str,
) -> None:
    """Test schedule dimensions must define a positive integral slot count."""
    with pytest.raises(ValueError, match=message):
        Config(hyperperiod=hyperperiod, tick_granularity=tick_granularity)


def test_from_env_reads_database_url() -> None:
    """Test the database URL defaults to in-memory and can be overridden."""
    environment = {
        "NICTO_HYPERPERIOD": "10000",
        "NICTO_TICK_GRANULARITY": "1000",
        "NICTO_TOPOLOGY_PATH": "topology.json",
    }

    assert Config.from_env(environment).database_url == "sqlite+aiosqlite:///:memory:"
    environment["NICTO_DATABASE_URL"] = "sqlite+aiosqlite:///nicto.db"
    assert Config.from_env(environment).database_url == "sqlite+aiosqlite:///nicto.db"
