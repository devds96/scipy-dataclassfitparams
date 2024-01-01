import math
import pytest

from dataclasses import dataclass
from typing import Any, Optional, Union

from scipy_dataclassfitparams import bounded, const, dump_result, \
    FitResult, same_as

from scipy_dataclassfitparams._dump_result import PrintBounds, \
    _PrintBoundsArg


@dataclass
class FitSpec:

    a: float

    b0: float = bounded(-float("inf"), float("inf"))

    b1: float = bounded(-float("inf"), 0)

    b2: float = bounded(0, float("inf"))

    b3: float = bounded(0, 1)

    b1x: float = bounded(max=0)

    b2x: float = bounded(min=0)

    c: float = same_as('a', default=5)

    d: float = const(7)


@pytest.mark.parametrize(
    "print_header", (True, False, None)
)
@pytest.mark.parametrize(
    "print_extra_params", (True, False, None)
)
@pytest.mark.parametrize(
    "print_bounds",
    (
        PrintBounds.always, PrintBounds.bounded, PrintBounds.never,
        "always", "bounded", "never",
        None
    )
)
@pytest.mark.parametrize(
    "print_initial_values", (True, False, None)
)
@pytest.mark.parametrize(
    "linesep", ('\n', "\r\n", '\r', None)
)
@pytest.mark.parametrize(
    "use_fitresult", (True, False)
)
@pytest.mark.parametrize(
    "provide_p0", (True, False)
)
def test_dump_result(
    print_header: Optional[bool],
    print_extra_params: Optional[bool],
    print_bounds: Optional[_PrintBoundsArg],
    print_initial_values: Optional[bool],
    linesep: Optional[str],
    use_fitresult: bool,
    provide_p0: bool
):

    instance: Union[FitSpec, FitResult[FitSpec]]

    instance = FitSpec(
        math.pi,
        0,
        -1,
        1,
        0.5,
        -1,
        1,
        8,
        7
    )

    p0 = instance if provide_p0 else None

    if use_fitresult:
        p0 = instance if provide_p0 else None
        instance = FitResult(
            instance,
            None,  # type: ignore
            None,
            p0
        )
        # p0 is now set on the FitResult and must not be passed to
        # dump_result
        p0 = None

    dump_result(
        instance,
        print_header=print_header,
        print_extra_params=print_extra_params,
        print_bounds=print_bounds,
        print_initial_values=print_initial_values,
        linesep=linesep,
        p0=p0
    )


def test_dump_result_raises_p0_and_fitresult_provided():
    """Test that an exception is raised if a `FitResult` and `p0` are
    both passed to `dump_result`.
    """

    fs = FitSpec(
        math.pi,
        0,
        -1,
        1,
        0.5,
        -1,
        1,
        8,
        7
    )

    instance = FitResult(
        fs,
        None,  # type: ignore
        None,
        fs
    )

    with pytest.raises(ValueError, match="p0 must not be provided.*"):
        dump_result(instance, p0=fs)


@pytest.mark.parametrize(
    "value", ("alwayS", "Never", "BOunded", 1, object())
)
def test_PrintBounds_sanitize_raises(value: Any):
    """Test that an exception is raised if `PrintBounds.sanitize`
    receives an invalid object.
    """
    type = ValueError if isinstance(value, str) else TypeError
    with pytest.raises(type, match="Invalid 'PrintBounds' value.*"):
        PrintBounds.sanitize(value)
