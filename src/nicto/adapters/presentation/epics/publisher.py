import asyncio
from collections.abc import Sequence

import numpy as np
from p4p.client.thread import Context
from pydantic_extra_types.mac_address import MacAddress

from nicto.application.ports import FlexcurvePublisher

DEFAULT_PUT_TIMEOUT = 5.0
NICTO_PV_PREFIX = "NICTO"
FLEXCURVE_PV_PREFIX = f"{NICTO_PV_PREFIX}:FLEXCURVE"


class EpicsFlexcurvePublisher(FlexcurvePublisher):
    """Publish port flexcurves to EPICS PVs, named ``NICTO:FLEXCURVE:<port MAC>``, through PVAccess (p4p)."""

    def __init__(self, timeout: float = DEFAULT_PUT_TIMEOUT) -> None:
        self._timeout = timeout
        self._context = Context("pva")

    async def publish_flexcurve(self, port_mac_address: MacAddress, flexcurve: Sequence[int]) -> None:
        """Put the flexcurve into the PV of the port without blocking the event loop."""
        pv_name = f"{FLEXCURVE_PV_PREFIX}:{str(port_mac_address).replace(':', '-')}"
        array = np.asarray(flexcurve, dtype=np.int32)
        await asyncio.to_thread(self._context.put, pv_name, array, timeout=self._timeout)

    async def close(self) -> None:
        """Close the PVAccess client context."""
        await asyncio.to_thread(self._context.close)
