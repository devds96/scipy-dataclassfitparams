"""This module contains the function which wraps scipy for the fitting
procedure.
"""

import numpy as _numpy
import scipy.optimize as _optimize  # type: ignore [import]
import scipy.version as _scipy_version  # type: ignore [import]

from dataclasses import dataclass as _dataclass
from numpy import floating as _floating
from numpy.typing import NDArray as _NDArray
from typing import Any as _Any, Callable as _Callable, Dict as _Dict, \
    Generic as _Generic, Literal as _Literal, Mapping as _Mapping, \
    Optional as _Optional, overload as _overload, Sequence as _Sequence, \
    Type as _Type, TypeVar as _TypeVar, Union as _Union

from . import _spec_registry


_TFitParams = _TypeVar("_TFitParams")
"""The type of the fit parameter definition class."""


_FitFunc = _Callable[[_Any, _TFitParams], _NDArray[_floating]]
"""The type of the fit function."""


_Method = _Literal["lm", "trf", "dogbox"]  # noqa: F821
"""The fitting method."""


_NaNPolicy = _Literal["raise", "omit"]  # noqa: F821, F722
"""The NaN policy values."""


@_dataclass(frozen=True)
class CovMatrix:
    """Encapsulate the covariance matrix for the fit parameters."""

    __slots__ = ("fields", "cov", "_mapping")

    fields: _Sequence[str]
    """The fields corresponding to the rows and columns."""

    cov: _NDArray[_floating]
    """The covariance matrix."""

    _mapping: _Mapping[str, int]
    """The mapping of the field names to their index. Basically the
    inverse of `fields`."""

    # Must be defined because "_mapping" cannot be a init=False field.
    def __init__(self, fields: _Sequence[str], cov: _NDArray[_floating]):
        """Construct a new `CovMatrix`.

        Args:
            fields (Sequence[str]): The fields corresponding to the rows
                and columns of the covariance matrix.
            cov (NDArray[floating]): The covariance matrix.
        """
        object.__setattr__(self, "fields", fields)
        object.__setattr__(self, "cov", cov)
        m = {x: i for i, x in enumerate(fields)}
        object.__setattr__(self, "_mapping", m)

    def get_index(self, field: str) -> int:
        """Map a field name to the corresponding index.

        Args:
            field (str): The field name.

        Raises:
            KeyError: If `field` is not a valid field name.

        Returns:
            int: The index in the covariance matrix belonging to
                `field`.
        """
        return self._mapping[field]

    def __getitem__(
        self,
        key: _Any
    ) -> _NDArray[_floating]:  # pragma: no cover
        """Indexes the covariance matrix directly. This is equivalent
        to `self.cov[key]`.

        Args:
            key (Any): The indexing object.

        Returns:
            NDArray[floating]: The result of indexing the cov matrix.
        """
        return self.cov[key]


@_dataclass(frozen=True)
class FitResult(_Generic[_TFitParams]):
    """Encapsulates the simple fit result."""

    __slots__ = ("opt_instance", "cov", "sigma", "p0")

    opt_instance: _TFitParams
    """The optimizing instance found via the fit."""

    cov: CovMatrix
    """The covariance matrix."""

    sigma: _Union[_NDArray[_floating], None]
    """The sigma values."""

    p0: _Union[_TFitParams, None]
    """The initial value used for the fit or None, if none was
    provided."""


@_dataclass(frozen=True)
class FullFitResult(FitResult[_TFitParams]):
    """Encapsulates the extended fit result. See also the doc of the
    return value of `scipy.optimize.curve_fit` with full_output=True for
    more info.
    """

    __slots__ = ("info_dict", "mesg", "ierr")

    info_dict: _Dict[str, _Any]
    """The info dict for the full result."""

    mesg: str
    """The message containing information about the solution."""

    ierr: int
    """An integer flag showing the status."""


def _check_has_nan_policy_arg() -> bool:
    """Determine if `scipy.optimize.curve_fit` has the 'nan_policy'
    argument.

    Returns:
        bool: Whether `scipy.optimize.curve_fit` has the 'nan_policy'
            argument.
    """
    maj, min, *_ = _scipy_version.short_version.split('.')
    imaj = int(maj)
    imin = int(min)
    # scipy version must be above or equal to 1.11.
    return (imaj > 1) or ((imaj == 1) and (imin >= 11))


_CURVE_FIT_HAS_NAN_POLICY = _check_has_nan_policy_arg()
"""Whether `scipy.optimize.curve_fit` has the 'nan_policy' argument."""


# There seemst to be no way to remove the nan_policy argument from
# the signature if it is not supported.

@_overload
def make_fit(
    fitparams_dc: _Type[_TFitParams],
    xdata: _NDArray[_floating],
    ydata: _NDArray[_floating],
    f: _FitFunc[_TFitParams],
    *,
    p0: _Optional[_TFitParams] = None,
    sigma: _Optional[_NDArray[_floating]] = None,
    absolute_sigma: bool = False,
    check_finite: _Optional[bool] = None,
    method: _Optional[_Method] = None,
    full_output: _Literal[False] = False,
    nan_policy: _Optional[_NaNPolicy] = None,
    **kwargs
) -> FitResult[_TFitParams]:
    pass


@_overload
def make_fit(
    fitparams_dc: _Type[_TFitParams],
    xdata: _NDArray[_floating],
    ydata: _NDArray[_floating],
    f: _FitFunc[_TFitParams],
    *,
    p0: _Optional[_TFitParams] = None,
    sigma: _Optional[_NDArray[_floating]] = None,
    absolute_sigma: bool = False,
    check_finite: _Optional[bool] = None,
    method: _Optional[_Method] = None,
    full_output: _Literal[True],
    nan_policy: _Optional[_NaNPolicy] = None,
    **kwargs
) -> FullFitResult[_TFitParams]:
    pass


def make_fit(
    fitparams_dc: _Type[_TFitParams],
    xdata: _NDArray[_floating],
    ydata: _NDArray[_floating],
    f: _FitFunc[_TFitParams],
    *,
    p0: _Optional[_TFitParams] = None,
    sigma: _Optional[_NDArray[_floating]] = None,
    absolute_sigma: bool = False,
    check_finite: _Optional[bool] = None,
    method: _Optional[_Method] = None,
    full_output: bool = False,
    nan_policy: _Optional[_NaNPolicy] = None,
    **kwargs
) -> _Union[FitResult[_TFitParams], FullFitResult[_TFitParams]]:
    """Perform the fit. For more information on some of the parameters
    of this function see `scipy.optimize.curve_fit` which is used
    internally by this function to perform the fit.

    Args:
        fitparams_dc (type[TFitParams]): The dataclass defining the
            parameters.
        xdata (NDArray[floating]): The x-values.
        ydata (NDArray[floating]): The y-values to fit against.
        f (FitFunc[TFitParams]): The fit func accepting the value of the
            `xdata` parameter, followed by an instance of `fitparams_dc`
            which represents the current set of parameters. The return
            value should be the current y-values obtained from the given
            set of parameters.
        p0 (TFitParams, optional): The initial instance. Defaults to
            None which constructs the instance using default values.
        sigma (NDArray[floating], optional): The uncertainties for the
            `ydata`. Defaults to None.
        absolute_sigma (bool, optional): If True, `sigma` are
            interpreted as absolute values. Defaults to False, which
            means only their relative values matter. This will affect
            the meaning of the returned covariance matrix.
        check_finite (bool, optional): Whether to check that the input
            arrays do not contain NaN values. Defaults to True if
            `nan_policy` is unspecify and False, otherwise.
        method (Method, optional): The method to use for the fit.
            Defaults to "lm" if no bounds are provided and "trf"
            otherwise.
        full_output (bool, optional): Whether to return an object with
            additional information. Defaults to False.
        nan_policy (NaNPolicy, optional): How to handle NaN values.
            Defaults to None. This argument is only available in
            scipy >= 1.11 and must be None (unset) otherwise.

    Raises:
        NotImplementedError: If `nan_policy` is not None and the scipy
            version is below 1.11.

    Returns:
        FitResult[TFitParams] or FullFitResult[TFitParams]: _description_
    """

    spec = _spec_registry.get_fit_spec(fitparams_dc)

    if p0 is None:
        p0_res = None
        p0 = spec.create_default_fit_instance()
    else:
        p0_res = p0

    p0_array = spec.new_empty_array(float)
    spec.instance_to_array(p0, p0_array)

    bounds = spec.bounds

    def wrapper(
        x: _NDArray[_floating],
        *params: float
    ) -> _NDArray[_floating]:
        instance = spec.array_to_instance(params)
        return f(x, instance)

    # "nan_policy" should never be in the kwargs.
    ver_kwargs = dict()
    if _CURVE_FIT_HAS_NAN_POLICY:
        ver_kwargs["nan_policy"] = nan_policy
    elif nan_policy is not None:
        raise NotImplementedError(
            "nan_policy must be None if the argument is not supported "
            "by scipy."
        )

    result = _optimize.curve_fit(
        wrapper,
        xdata,
        ydata,
        p0=p0_array,
        bounds=bounds,
        sigma=sigma,
        absolute_sigma=absolute_sigma,
        check_finite=check_finite,
        method=method,
        full_output=True,  # The method computes the extras anyway
        **ver_kwargs,
        **kwargs
    )

    pcov: _NDArray
    popt, pcov, info_dict, msg, ec = result

    res_instance = spec.array_to_instance(popt)

    pcov.flags.writeable = False
    cov_mat = CovMatrix(tuple(spec.fitting_params), pcov)

    if sigma is not None:  # pragma: no cover
        sigma = _numpy.copy(sigma)
        sigma.flags.writeable = False

    if not full_output:
        return FitResult(res_instance, cov_mat, sigma, p0_res)

    return FullFitResult(
        res_instance, cov_mat, sigma, p0_res, info_dict, msg, ec
    )
