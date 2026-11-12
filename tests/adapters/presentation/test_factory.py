import pytest

from nicto.adapters.presentation.factory import create_flexcurve_publisher
from nicto.config import Config


def test_no_presentation_returns_no_publisher() -> None:
    """No publisher is created when presentation is disabled."""
    assert create_flexcurve_publisher(Config(hyperperiod=1000, tick_granularity=10)) is None


def test_unsupported_presentation_is_rejected() -> None:
    """An unknown presentation backend raises."""
    config = Config(hyperperiod=1000, tick_granularity=10, presentation="other")

    with pytest.raises(ValueError, match="Unsupported presentation"):
        create_flexcurve_publisher(config)
