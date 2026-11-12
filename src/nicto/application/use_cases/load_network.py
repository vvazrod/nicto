from nicto.application.ports import NetworkController, NetworkRepository, UnitOfWork


class LoadNetworkUseCase:
    """Load the controller topology into persistent storage."""

    def __init__(
        self,
        repository: NetworkRepository,
        controller: NetworkController,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._repository = repository
        self._unit_of_work = unit_of_work
        self._controller = controller

    async def execute(self) -> None:
        """Persist all nodes and links returned by the network controller."""
        nodes, links = await self._controller.get_topology()

        for node in nodes:
            await self._repository.create_node(node)

        for link in links:
            await self._repository.create_link(link)

        await self._unit_of_work.commit()
