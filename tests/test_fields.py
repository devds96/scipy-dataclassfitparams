import dataclasses
import numpy
import pytest

from dataclasses import dataclass
from typing import Literal, Optional, Union

from scipy_dataclassfitparams._fields import BoundedField, \
    get_special_fitting_field
from scipy_dataclassfitparams import bounded


@dataclass(frozen=True)
class BoundedFieldParamsCaseBase:
    """Defines a test case for a bounded field."""

    __slots__ = ("min", "max")

    min: Optional[float]
    """The min value or None, meaning minus infinity."""

    max: Optional[float]
    """The max value or None, meaning plus infinity."""


INF = numpy.inf
"""The positive infinity float."""


MISSING = dataclasses.MISSING
"""The dataclasses 'missing' value."""


@pytest.mark.parametrize("alternative", (2, -2, MISSING))
@pytest.mark.parametrize("case", (
    BoundedFieldParamsCaseBase(0, 1),
    BoundedFieldParamsCaseBase(0, INF),
    BoundedFieldParamsCaseBase(-INF, 1),
    BoundedFieldParamsCaseBase(-INF, INF)
))
def test_bounded_default_contained(
    case: BoundedFieldParamsCaseBase,
    alternative: Union[float, Literal[MISSING]]  # type: ignore
):
    """Test that the initial value for a bounded field is contained in
    the bounds.
    """
    dc_field = bounded(case.min, case.max)
    field = get_special_fitting_field(dc_field)
    assert isinstance(field, BoundedField)

    default = field.resolve_default(alternative)
    assert field.contains(default)

    min = case.min
    if min is None:
        min = -INF

    max = case.max
    if max is None:
        max = INF

    if (alternative is not MISSING) and (min <= alternative <= max):
        assert default == alternative


@dataclass(frozen=True)
class BoundedFieldParamsCase(BoundedFieldParamsCaseBase):
    """Defines a test case for a bounded field with additional
    information regarding whether a parameter is actually bounded.
    """

    __slots__ = ("actually_bounded", "min_finite", "max_finite")

    actually_bounded: bool
    """Whether the parameter is actually bounded."""

    min_finite: bool
    """Whether the min value is finite."""

    max_finite: bool
    """Whether the max value is finite."""


@pytest.mark.parametrize("case", (
    BoundedFieldParamsCase(0, 1, True, True, True),
    BoundedFieldParamsCase(0, INF, True, True, False),
    BoundedFieldParamsCase(-INF, 1, True, False, True),
    BoundedFieldParamsCase(-INF, INF, False, False, False),
    BoundedFieldParamsCase(0, None, True, True, False),
    BoundedFieldParamsCase(None, 1, True, False, True),
    BoundedFieldParamsCase(None, None, False, False, False)
))
def test_bounded_actually_bounded(
    case: BoundedFieldParamsCase
):
    """Test the values of the `actually_bounded`, `min_finite` and
    `max_finite` fields.
    """
    dc_field = bounded(case.min, case.max)
    field = get_special_fitting_field(dc_field)
    assert isinstance(field, BoundedField)

    assert field.actually_bounded == case.actually_bounded
    assert field.min_finite == case.min_finite
    assert field.max_finite == case.max_finite


@pytest.mark.parametrize("case", (
    BoundedFieldParamsCaseBase(1, 0),
    BoundedFieldParamsCaseBase(INF, 0),
    BoundedFieldParamsCaseBase(0, -INF),
    BoundedFieldParamsCaseBase(INF, -INF)
))
def test_invalid_bounds_order_raises(case: BoundedFieldParamsCaseBase):
    """Test that an exception is raised if the bounds of a bounded field
    are ordered incorrectly.
    """
    msg = ".*max value was smaller than.*min value.*"
    with pytest.raises(ValueError, match=msg):
        bounded(case.min, case.max)
