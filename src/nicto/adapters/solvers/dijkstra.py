import heapq
from collections import defaultdict

from nicto.application.ports import PathSolver
from nicto.application.use_cases.insert_stream import StreamUnfeasibleError
from nicto.domain.models import BITS_PER_BYTE, NANOSECONDS_PER_MEGABIT_PER_SECOND, Hop, Link, Node, Stream

Edge = tuple[str, int, Link | None]


class DijkstraPathSolver(PathSolver):
    """Find the path with the lowest end-to-end delay using Dijkstra's algorithm."""

    def find_path(self, stream: Stream, nodes: list[Node], links: list[Link]) -> list[Hop]:
        """Find the lowest-delay path between the stream endpoints.

        Each link costs its propagation delay plus the transmission time of the stream's maximum frame.
        Forwarding between ports of the same node is free.
        """
        src = str(stream.src_mac_address)
        dst = str(stream.dst_mac_address)
        graph = self._build_graph(stream, nodes, links)

        distances = {src: 0}
        previous: dict[str, tuple[str, Link | None]] = {}
        queue = [(0, src)]
        while queue:
            distance, vertex = heapq.heappop(queue)
            if vertex == dst:
                break
            if distance > distances.get(vertex, distance):
                continue
            for neighbor, cost, link in graph[vertex]:
                candidate = distance + cost
                if candidate < distances.get(neighbor, candidate + 1):
                    distances[neighbor] = candidate
                    previous[neighbor] = (vertex, link)
                    heapq.heappush(queue, (candidate, neighbor))

        if dst not in distances:
            msg = "No path exists between the stream source and destination"
            raise StreamUnfeasibleError(msg)

        ports = {str(port.mac_address): port for node in nodes for port in node.ports}
        path: list[Hop] = []
        vertex = dst
        while vertex != src:
            vertex, link = previous[vertex]
            if link is not None:
                path.append(Hop(port=ports[vertex], link=link))
        path.reverse()
        return path

    @staticmethod
    def _build_graph(stream: Stream, nodes: list[Node], links: list[Link]) -> dict[str, list[Edge]]:
        """Build an adjacency list whose vertices are the MAC addresses of ports."""
        graph: dict[str, list[Edge]] = defaultdict(list)

        for node in nodes:
            macs = [str(port.mac_address) for port in node.ports]
            for mac in macs:
                graph[mac].extend((other, 0, None) for other in macs if other != mac)

        transmission_bits = stream.max_frame_size * BITS_PER_BYTE * NANOSECONDS_PER_MEGABIT_PER_SECOND
        for link in links:
            cost = link.propagation_delay + (transmission_bits + link.speed - 1) // link.speed
            port_a = str(link.port_a_mac_address)
            port_b = str(link.port_b_mac_address)
            graph[port_a].append((port_b, cost, link))
            graph[port_b].append((port_a, cost, link))

        return graph
