import pytest

from dataclasses import dataclass

from scipy_dataclassfitparams import same_as
from scipy_dataclassfitparams._fit_spec import FitSpecBase


def test_short_circular_same_as_dependence_raises() -> None:
    """Test that a circular dependence with `same_as` parameters leads
    to an exception when the fit spec is generated.
    """

    @dataclass
    class FitSpec:

        a: float = same_as('b')

        b: float = same_as('a')

    with pytest.raises(ValueError, match=".*circular dependence.*"):
        FitSpecBase.generate(FitSpec)


def test_circular_same_as_dependence_raises() -> None:
    """Test that a circular dependence with `same_as` parameters leads
    to an exception when the fit spec is generated.
    """

    @dataclass
    class FitSpec:

        a: float = same_as('b')

        b: float = same_as('c')

        c: float = same_as('a')

    with pytest.raises(ValueError, match=".*circular dependencies.*"):
        FitSpecBase.generate(FitSpec)
