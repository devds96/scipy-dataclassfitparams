import networkx  # type: ignore [import]
import pytest

from dataclasses import dataclass
from hypothesis import assume, given, settings
from hypothesis.strategies import booleans, composite, DrawFn, floats, integers
from networkx import DiGraph
from typing import Sequence, Tuple

from scipy_dataclassfitparams._depgraph import DepGraph


@composite
def raw_digraphs(draw: DrawFn, N: int) -> DiGraph:
    """A hypothesis strategy for creating networkx `DiGraph`s.

    Args:
        N (int): The maximum number of nodes.
    """
    n = draw(integers(0, N))
    p = draw(floats(0, 1))
    seed = draw(integers())
    G: DiGraph = networkx.gnp_random_graph(n, p, seed, directed=True)
    G2 = DiGraph()
    for u, v in G.edges:
        G2.add_edge(f"_{u}", f"_{v}")
    return G2


@dataclass(frozen=True)
class DiGraphInfo:
    """Encapsulates a `DiGraph` with additional information."""

    graph: DiGraph
    """The graph."""

    acyclic: bool
    """Whether the graph is acyclic."""

    fields: Sequence[str]
    """The nodes appearing in the graph."""


def all_topological_sorts(graph: DiGraph) -> Tuple[Tuple[str, ...], ...]:
    """Create all topolitical sorts of a graph as a tuple of tuples.

    Args:
        graph (DiGraph): THe graphg for which to compute all
            topological sorts.

    Returns:
        Tuple[Tuple[str, ...], ...]: A tuple containing all
            topological sorts of `graph` as tuples.
    """
    all_sorts = networkx.all_topological_sorts(graph)
    return tuple(map(tuple, all_sorts))


@composite
def digraph_infos(draw: DrawFn, N: int) -> DiGraphInfo:
    """A hypothesis strategy for creating `DiGraphInfo` instances.

    Args:
        N (int): The maximum number of nodes.
    """
    require_acyclic = draw(booleans())
    if require_acyclic:
        G = draw(raw_digraphs(N))
        if not networkx.is_directed_acyclic_graph(G):
            G2 = DiGraph()
            for f, t in filter(lambda ft: ft[0] < ft[1], G.edges()):
                G2.add_edge(f, t)
            G = G2
            assume(networkx.is_directed_acyclic_graph(G))
    else:
        G = draw(
            raw_digraphs(N).filter(
                lambda g: not networkx.is_directed_acyclic_graph(g)
            )
        )
    return DiGraphInfo(
        G, require_acyclic, tuple(G.nodes)
    )


@given(graph_info=digraph_infos(10))
@settings(deadline=None)
def test_depgraph_many_examples(graph_info: DiGraphInfo):
    """Test a examples using hypothesis and networkx."""
    dg = DepGraph(graph_info.fields)
    if graph_info.acyclic:
        for t, f in graph_info.graph.edges():
            dg.add_dependency(f, t)
        assert not dg.has_closed_cycles()
        order = tuple(dg.get_init_order())
        all_topsorts = all_topological_sorts(graph_info.graph)
        assert order in all_topsorts
    else:
        test_G = DiGraph()
        for t, f in graph_info.graph.edges():
            try:
                dg.add_dependency(f, t)
            except ValueError:
                pass
            else:
                test_G.add_edge(t, f)
        if networkx.is_directed_acyclic_graph(test_G):
            assert not dg.has_closed_cycles()
            order = tuple(dg.get_init_order())
            all_topsorts = all_topological_sorts(test_G)
            assert order in all_topsorts
        else:
            assert dg.has_closed_cycles()
            with pytest.raises(ValueError, match=".*closed loops.*"):
                dg.get_init_order()


def test_depgraph_small_example():
    """Test a small example using 4 fields and 4 dependencies."""
    dg = DepGraph(('a', 'b', 'c', 'd'))
    dg.add_dependency('a', 'b')
    dg.add_dependency('b', 'd')
    dg.add_dependency('c', 'a')
    dg.add_dependency('c', 'd')
    assert not dg.has_closed_cycles()
    assert dg.dependency_count == 4
    init_order = dg.get_init_order()
    assert len(init_order) == 4
    assert tuple(init_order) == ('d', 'b', 'a', 'c')


def test_depgraph_empty():
    """Test an empty example without fields."""
    dg = DepGraph(())
    assert dg.dependency_count == 0
    assert not dg.has_closed_cycles()
    init_order = dg.get_init_order()
    assert len(init_order) == 0
    assert tuple(init_order) == ()


def test_duplicate_dependency():
    """Test that duplicate dependencies are reported by the return
    value.
    """
    dg = DepGraph(('a', 'b', 'c', 'd'))
    assert dg.add_dependency('a', 'b')
    assert not dg.add_dependency('a', 'b')


def test_immediate_circular_dependency_raises():
    """Test that an exception is raised if a direct circular dependence
    would be added to the graph.
    """
    dg = DepGraph(('a', 'b', 'c', 'd'))
    assert dg.add_dependency('a', 'b')
    with pytest.raises(ValueError, match=".*circular dependence.*"):
        dg.add_dependency('b', 'a')


@pytest.mark.parametrize("which", (('d', 'a'), ('b', 'c')))
def test_long_circular_dependence_raises(which: Tuple[str, str]):
    """Test that a non-direct circular dependence is found."""
    dg = DepGraph(('a', 'b', 'c', 'd'))
    dg.add_dependency('a', 'b')
    dg.add_dependency('b', 'd')
    dg.add_dependency('c', 'a')
    dg.add_dependency('c', 'd')

    dg.add_dependency(*which)

    assert dg.has_closed_cycles()

    with pytest.raises(ValueError, match=".*closed loops.*"):
        dg.get_init_order()


@pytest.mark.parametrize("which", (('d', 'a'), ('b', 'c')))
def test_self_circular_dependence_raises(which: Tuple[str, str]):
    """Test that an exception is raised if a field would depend on
    itself.
    """
    dg = DepGraph(('a', 'b'))

    with pytest.raises(ValueError, match=".*cannot depend on itself.*"):
        dg.add_dependency('b', 'b')
