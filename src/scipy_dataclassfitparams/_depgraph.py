"""This module contains the `DepGraph` class which is a helper class for
keeping track of the dependencies between fitting fields.
"""

from scipy import sparse as _sparse  # type: ignore [import]
from scipy.sparse import csgraph as _csgraph  # type: ignore [import]

from dataclasses import dataclass as _dataclass
from typing import Iterable as _Iterable, List as _List, Mapping as _Mapping, \
    Sequence as _Sequence, Set as _Set


@_dataclass(order=False, frozen=True)
class DepGraph:

    __slots__ = ("N", "_graph", "fields", "_key_map", "_num_deps")

    N: int
    """The number of elements in the graph."""

    _graph: _sparse.lil_matrix
    """The actual graph used for computations stored as a sparse
    matrix."""

    fields: _Sequence[str]
    """The fields."""

    _key_map: _Mapping[str, int]
    """The mapping from the field names to their index in the graph
    matrix."""

    _num_deps: int
    """The number of dependencies."""

    # It is not possible to use a __post_init__ here since _graph would
    # have to be init=False. But assigning to the field means it is a
    # class variable with the same name as a __slots__ variable, which
    # is not allowed.
    def __init__(self, fields: _Iterable[str]):
        """Construct a new `DepGraph`.

        Args:
            fields (Iterable[str]): The fields for which to track
                dependencies.
        """
        fields = tuple(fields)
        N = len(fields)
        object.__setattr__(self, 'N', N)
        g = _sparse.lil_matrix((N, N), dtype=int)
        object.__setattr__(self, "_graph", g)
        km = {s: i for i, s in enumerate(fields)}
        object.__setattr__(self, "_key_map", km)
        object.__setattr__(self, "fields", fields)
        object.__setattr__(self, "_num_deps", 0)

    def add_dependency(self, which: str, source: str) -> bool:
        """Add a dependency to the graph.

        Args:
            which (str): The name of the field that "depends".
            source (str): The name of the field on which it depends.

        Raises:
            ValueError: If a dependency in the opposite direction was
                already set.

        Returns:
            bool: True, if the dependency was added and False, if it
                was already present.
        """
        if which == source:
            raise ValueError(f"The field {which!r} cannot depend on itself.")
        km = self._key_map
        wi = km[which]
        si = km[source]
        g = self._graph
        v = g[wi, si]
        change = v != -1
        if change:
            if g[si, wi] != 0:
                raise ValueError(
                    f"The dependence of {which!r} on {source!r} is "
                    "invalid since this creates a direct circular "
                    f"dependence ({source!r} already depends directly "
                    f"on {which!r})."
                )
            g[wi, si] = -1
            object.__setattr__(self, "_num_deps", 1 + self._num_deps)
        return change

    @property
    def dependency_count(self) -> int:
        """The number of dependencies ("edges" in the graph)."""
        return self._num_deps

    def has_closed_cycles(self) -> bool:
        """Whether the dependency graph contains closed cycles,
        indicating circular dependencies.

        Returns:
            bool: True, if the dependency graph contains closed loops,
                otherwise False.
        """
        try:
            _csgraph.floyd_warshall(self._graph, directed=True)
            return False
        except _csgraph.NegativeCycleError:
            return True

    def get_init_order(self) -> _Sequence[str]:
        """Construct the order in which arguments must be initialized in
        order to be compatible with the dependencies defined by the
        graph. Note that this order is not necessarily unique, but for
        fields that may be in arbitrary order, the order will follow
        the `fields` __init__ parameter/field.

        Raises:
            ValueError: If the dependency graph contains closed cycles,
                indicating circular dependencies.

        Returns:
            Sequence[str]: The order in which the fields have to be
                initialized so that their dependencies can be satisfied.
        """
        if self.has_closed_cycles():
            raise ValueError("The dependency graph contained closed loops.")

        g = self._graph

        idx_in_tree: _Set[int] = set(range(self.N))
        idx_resolved: _List[int] = list()

        # Keep track of how many fields depend on a certain field given
        # by the index. We are working with opposite signs here.
        nnum_deps = g.sum(axis=1)

        while len(idx_in_tree) > 0:

            # coverage.py is looking for a branch back to the while loop
            # above, which is of course impossible.
            for idx in idx_in_tree:  # pragma: no branch
                if nnum_deps[idx, 0] != 0:
                    continue
                # There are no futher fields in the tree depending
                # on idx.

                # Decrement dependencies
                for i in idx_in_tree:
                    if g[i, idx] == 0:
                        continue
                    # We are working with opposite signs
                    nnum_deps[i, 0] += 1

                # Removeindex from tree
                idx_in_tree.remove(idx)
                idx_resolved.append(idx)

                # The tree has been modified
                break

        fields = self.fields
        field_names = (fields[i] for i in idx_resolved)
        return tuple(field_names)
