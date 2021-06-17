# Copyright 2014-2016 OpenMarket Ltd
# Copyright 2020 The Matrix.org Foundation C.I.C.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import heapq
from itertools import islice
from typing import (
    Collection,
    Dict,
    Generator,
    Iterable,
    Iterator,
    Mapping,
    Sequence,
    Set,
    Tuple,
    TypeVar,
)

T = TypeVar("T")


def batch_iter(iterable: Iterable[T], size: int) -> Iterator[Tuple[T, ...]]:
    """batch an iterable up into tuples with a maximum size

    Args:
        iterable: the iterable to slice
        size: the maximum batch size

    Returns:
        an iterator over the chunks
    """
    # make sure we can deal with iterables like lists too
    sourceiter = iter(iterable)
    # call islice until it returns an empty tuple
    return iter(lambda: tuple(islice(sourceiter, size)), ())


def chunk_seq(iseq: Sequence[T], maxlen: int) -> Iterable[Sequence[T]]:
    """Split the given sequence into chunks of the given size

    The last chunk may be shorter than the given size.

    If the input is empty, no chunks are returned.
    """
    return (iseq[i : i + maxlen] for i in range(0, len(iseq), maxlen))


def sorted_topologically(
    nodes: Iterable[T],
    graph: Mapping[T, Collection[T]],
) -> Generator[T, None, None]:
    """Given a set of nodes and a graph, yield the nodes in toplogical order.

    For example `sorted_topologically([1, 2], {1: [2]})` will yield `2, 1`.
    """

    # This is implemented by Kahn's algorithm.

    degree_map = {node: 0 for node in nodes}
    reverse_graph = {}  # type: Dict[T, Set[T]]

    for node, edges in graph.items():
        if node not in degree_map:
            continue

        for edge in set(edges):
            if edge in degree_map:
                degree_map[node] += 1

            reverse_graph.setdefault(edge, set()).add(node)
        reverse_graph.setdefault(node, set())

    zero_degree = [node for node, degree in degree_map.items() if degree == 0]
    heapq.heapify(zero_degree)

    while zero_degree:
        node = heapq.heappop(zero_degree)
        yield node

        for edge in reverse_graph.get(node, []):
            if edge in degree_map:
                degree_map[edge] -= 1
                if degree_map[edge] == 0:
                    heapq.heappush(zero_degree, edge)
