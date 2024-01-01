import math
import numpy
import pytest

from dataclasses import dataclass
from numpy import floating
from numpy.typing import NDArray
from typing import Any

from scipy_dataclassfitparams import bounded, const, make_fit, regular, \
    same_as


@pytest.mark.parametrize('a', (1, 2, 3, 4))
@pytest.mark.parametrize('b', (1, 2, 3, 4))
@pytest.mark.parametrize("set_p0", (True, False))
@pytest.mark.parametrize("full_output", (True, False, None))
def test_fit_simple_sine(
    a: float, b: float, set_p0: bool, full_output: bool
):
    """Test a simple fit of a sine function."""

    # It is not possible to use slots here directly because the slots
    # would conflict with class variable names.
    @dataclass
    class FitSpec:
        """The fit spec for the test."""

        a: float

        b: float = regular(default=1)

        c: float = same_as('a', default=5)

    def f(x: NDArray[floating], fs: FitSpec) -> NDArray[floating]:
        a = fs.a
        b = fs.b
        assert fs.c == a
        return a * numpy.sin(b * x)

    x = numpy.linspace(-numpy.pi / b, numpy.pi / b)
    target = FitSpec(a, b, a)
    y = f(x, target)

    kwargs: Any = dict()
    if set_p0:
        kwargs["p0"] = FitSpec(a, b)
    if full_output is not None:
        kwargs["full_output"] = full_output

    result = make_fit(FitSpec, x, y, f, **kwargs)

    instance = result.opt_instance
    assert math.isclose(instance.a, a, abs_tol=1e-5)
    assert math.isclose(instance.b, b, abs_tol=1e-5)

    covmat = result.cov

    assert covmat.get_index('a') == 0
    assert covmat.get_index('b') == 1
    with pytest.raises(KeyError, match='c'):
        covmat.get_index('c')


INF = numpy.inf
"""The positive infinity float."""


@pytest.mark.parametrize("lb", (0, -INF))
@pytest.mark.parametrize("ub", (1, INF))
@pytest.mark.parametrize('a', (1, 0.5, 0.25))
@pytest.mark.parametrize("set_p0", (True, False))
def test_fit_parameter_types(
    lb: float, ub: float, a: float, set_p0: bool
):
    """Test a simple fit of an exponential function with all field types
    involved.
    """

    # It is not possible to use slots here directly because the slots
    # would conflict with class variable names.
    @dataclass
    class FitSpec:
        """The fit spec for the test."""

        a: float = bounded(lb, ub)

        b: float = const(1)

    def f(x: NDArray[floating], fs: FitSpec) -> NDArray[floating]:
        a = fs.a
        b = fs.b
        assert b == 1
        return b * numpy.exp(-a * x)

    x = numpy.linspace(-numpy.pi, numpy.pi)
    target = FitSpec(a)
    y = f(x, target)

    kwargs: Any = dict()
    if set_p0:
        kwargs["p0"] = FitSpec(a, 1)

    result = make_fit(FitSpec, x, y, f, **kwargs)

    instance = result.opt_instance
    assert math.isclose(instance.a, a, abs_tol=1e-5)
    assert instance.b == 1

    covmat = result.cov

    assert covmat.get_index('a') == 0
    with pytest.raises(KeyError, match='b'):
        covmat.get_index('b')


def test_fit_many_bounds() -> None:
    """Test a simple fit of a mixed function with many bounded
    parameters to ensure that they are ordered correctly.
    """

    # It is not possible to use slots here directly because the slots
    # would conflict with class variable names.
    @dataclass
    class FitSpec:
        """The fit spec for the test."""

        a: float = bounded(-1, 0)

        b: float = bounded(0, 1)

        c: float = bounded(1, 2)

        d: float = bounded(3, 4)

    def f(x: NDArray[floating], fs: FitSpec) -> NDArray[floating]:
        a = fs.a
        assert -1 <= a <= 0
        b = fs.b
        assert 0 <= b <= 1
        c = fs.c
        assert 1 <= c <= 2
        d = fs.d
        assert 3 <= d <= 4
        return c * numpy.exp(-b * x) * numpy.sin(d * x + a)

    x = numpy.linspace(-numpy.pi, numpy.pi)
    target = FitSpec(-0.9, 0.8, 1.2, 3.7)
    y = f(x, target)

    result = make_fit(FitSpec, x, y, f)

    instance = result.opt_instance

    for v in ('a', 'b', 'c', 'd'):
        assert math.isclose(
            getattr(instance, v),
            getattr(target, v)
        )
