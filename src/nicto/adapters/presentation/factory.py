from nicto.application.ports import FlexcurvePublisher
from nicto.config import Config


def create_flexcurve_publisher(config: Config) -> FlexcurvePublisher | None:
    """Create the flexcurve publisher selected by the runtime configuration, if any."""
    if config.presentation == "none":
        return None

    if config.presentation == "epics":
        try:
            from nicto.adapters.presentation.epics.publisher import EpicsFlexcurvePublisher  # noqa: PLC0415
        except ImportError as error:
            msg = "The 'epics' presentation requires the optional dependencies: pip install 'nicto[epics]'"
            raise RuntimeError(msg) from error
        return EpicsFlexcurvePublisher()

    msg = f"Unsupported presentation: {config.presentation}"
    raise ValueError(msg)
