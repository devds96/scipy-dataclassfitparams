"""This module contains the caching mechanism for the `FitSpec`s."""

import dataclasses as _dataclasses
import sys as _sys
import weakref as _weakref

from dataclasses import dataclass as _dataclass
from typing import Generic as _Generic, Type as _Type, TypeVar as _TypeVar

from ._fit_spec import FitSpec as _FitSpec, FitSpecBase as _FitSpecBase


_T = _TypeVar("_T")


@_dataclass(frozen=True)
class _StoredFitSpec(_FitSpecBase, _Generic[_T]):
    """A `_FitSpecBase` stored in the registry. No reference to the
    actual type defining the fit is stored.
    """

    def pin(self, cls: _Type[_T]) -> "_FitSpec[_T]":
        """Pin the actual type of the dataclass defining the fit and
        return a `FitSpec` instance containing the type.

        Args:
            cls (Type[T]): The class defining the fit.

        Returns:
            FitSpec[T]: The constructed `FitSpec` instance.
        """
        # Copy over the fields
        keys = (f.name for f in _dataclasses.fields(_FitSpecBase))
        kwargs = {k: getattr(self, k) for k in keys}
        return _FitSpec(clss=cls, **kwargs)


if _sys.version_info < (3, 9):
    from typing import Dict as _Dict

    _reg: _Dict[type, _StoredFitSpec]
    _reg = _weakref.WeakKeyDictionary()  # type: ignore [assignment]
else:
    _reg = _weakref.WeakKeyDictionary[  # type: ignore [assignment]
        type, _StoredFitSpec
    ]()


_REGISTRY = _reg
"""The registry mapping the classes defining fits to the corresponding
`_StoredFitSpec`."""


def get_fit_spec(t: _Type[_T]) -> _FitSpec[_T]:
    """Get the fit spec for a class defining a fit.

    Args:
        t (Type[T]): The class for which to get the fit spec.

    Returns:
        FitSpec[T]: The additional information for the dataclass
            defining the fit.
    """
    try:
        fs = _REGISTRY[t]
    except KeyError:
        fs = _StoredFitSpec.generate(t)
        _REGISTRY[t] = fs
    result = fs.pin(t)
    return result


def clear_cache() -> int:  # pragma: no cover
    """Clear the cached fit specifications. It is recommended to perform
    a garbage collection afterwards.

    Returns:
        int: The number of cached specs that have been released.
    """
    num_entries = len(_REGISTRY)
    _REGISTRY.clear()
    return num_entries
