import heapq
from collections import defaultdict

from nicto.application.ports import PathSolver
from nicto.application.use_cases.insert_stream import StreamUnfeasibleError
from nicto.config import Config
from nicto.domain.flexcurve import calculate_flexcurve
from nicto.domain.models import BITS_PER_BYTE, NANOSECONDS_PER_MEGABIT_PER_SECOND, Hop, Link, Node, Stream

Edge = tuple[str, int, float, Link | None]
Label = tuple[float, int, int]


class DijkstraPathSolver(PathSolver):
    """Find the most schedulable path, preferring lower delay when tied."""

    def __init__(self, config: Config) -> None:
        self._config = config

    def find_path(self, stream: Stream, nodes: list[Node], links: list[Link]) -> list[Hop]:
        """Find the path with the highest flexcurve between the stream endpoints.

        A path's flexcurve is the minimum flexcurve value of its egress ports for the stream's transmission
        size. Paths with a higher value are preferred; delay breaks ties. Forwarding between ports of the same
        node is free and does not affect the flexcurve.
        """
        src = str(stream.src_mac_address)
        dst = str(stream.dst_mac_address)
        graph = self._build_graph(stream, nodes, links)

        labels: dict[str, list[Label]] = defaultdict(list)
        previous: dict[int, tuple[int, str, Link | None]] = {}
        active = {0}
        labels[src].append((float("inf"), 0, 0))
        queue = [(float("-inf"), 0, 0, src)]
        destination_label: int | None = None
        while queue:
            neg_flexcurve, delay, label_id, vertex = heapq.heappop(queue)
            if label_id not in active:
                continue
            flexcurve = -neg_flexcurve
            if vertex == dst:
                destination_label = label_id
                break
            for neighbor, cost, edge_flexcurve, link in graph[vertex]:
                candidate = (min(flexcurve, edge_flexcurve), delay + cost, len(previous) + 1)
                neighbor_labels = labels[neighbor]
                if any(
                    existing_flexcurve >= candidate[0] and existing_delay <= candidate[1]
                    for existing_flexcurve, existing_delay, _ in neighbor_labels
                ):
                    continue
                for dominated in [
                    label
                    for label in neighbor_labels
                    if candidate[0] >= label[0] and candidate[1] <= label[1]
                ]:
                    neighbor_labels.remove(dominated)
                    active.remove(dominated[2])
                neighbor_labels.append(candidate)
                active.add(candidate[2])
                previous[candidate[2]] = (label_id, vertex, link)
                heapq.heappush(queue, (-candidate[0], candidate[1], candidate[2], neighbor))

        if destination_label is None:
            msg = "No path exists between the stream source and destination"
            raise StreamUnfeasibleError(msg)

        ports = {str(port.mac_address): port for node in nodes for port in node.ports}
        path: list[Hop] = []
        label_id = destination_label
        while label_id != 0:
            label_id, port_mac_address, link = previous[label_id]
            if link is not None:
                path.append(Hop(port=ports[port_mac_address], link=link))
        path.reverse()
        return path

    def _build_graph(self, stream: Stream, nodes: list[Node], links: list[Link]) -> dict[str, list[Edge]]:
        """Build an adjacency list whose vertices are the MAC addresses of ports."""
        graph: dict[str, list[Edge]] = defaultdict(list)
        ports = {str(port.mac_address): port for node in nodes for port in node.ports}

        for node in nodes:
            macs = [str(port.mac_address) for port in node.ports]
            for mac in macs:
                graph[mac].extend((other, 0, float("inf"), None) for other in macs if other != mac)

        transmission_bits = stream.max_frame_size * BITS_PER_BYTE * NANOSECONDS_PER_MEGABIT_PER_SECOND
        for link in links:
            transmission_time = (transmission_bits + link.speed - 1) // link.speed
            cost = link.propagation_delay + transmission_time
            stream_size = stream.slots(link.speed, self._config.tick_granularity)
            port_a = str(link.port_a_mac_address)
            port_b = str(link.port_b_mac_address)
            flexcurve_a = calculate_flexcurve(stream_size, ports[port_a].gaps(self._config.total_slots))
            flexcurve_b = calculate_flexcurve(stream_size, ports[port_b].gaps(self._config.total_slots))
            graph[port_a].append((port_b, cost, flexcurve_a, link))
            graph[port_b].append((port_a, cost, flexcurve_b, link))

        return graph
