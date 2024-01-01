"""This module defines the functions that can be used for the field
definitions and the corresponding classes that encapsulate the dataclass
metadata values.
"""

import cmath as _cmath
import dataclasses as _dataclasses
import sys as _sys
import warnings as _warnings

from dataclasses import dataclass as _dataclass, Field as _Field
from typing import Any as _Any, Callable as _Callable, ClassVar as _ClassVar, \
    Mapping as _Mapping, Optional as _Optional, Union as _Union

from . import _warning_types


_METADATA_KEY = object()
"""The object used as the key for the fields' metadata mapping."""


@_dataclass(frozen=True)
class FittingField:
    """Base class for the field metadata values."""
    pass


def get_special_fitting_field(f: _Field) -> _Union[FittingField, None]:
    """Get the `FittingField` instance associated with a dataclass
    `Field`.

    Args:
        f (Field): The dataclass field.

    Raises:
        AssertionError: If the `_METADATA_KEY` for a fitting field is
            not associated with a `FittingField` instance.

    Returns:
        FittingField | None: The found `FittingField` or None, if none
            was found.
    """
    md = f.metadata
    try:
        val = md[_METADATA_KEY]
    except KeyError:
        return None
    if not isinstance(val, FittingField):
        raise AssertionError(
            f"Found invalid object {val!r} where a FittingField was "
            f"expected. Dataclass field: {f.name!r}"
        ) from TypeError
    return val


_MISSING = _dataclasses.MISSING
"""The 'missing' values of the dataclasses module."""


_MissingType = type(_MISSING)
"""The type of `dataclasses.MISSING` and `_MISSING`."""


_FloatOrMissing = _Union[
    float, _MissingType  # type: ignore [valid-type]
]
"""The type representing a float or `dataclasses.MISSING`."""


@_dataclass(frozen=True)
class BoundedField(FittingField):

    __slots__ = ("min", "max")

    min: float
    """The min value."""

    max: float
    """The max value."""

    POS_INF: _ClassVar[float] = float("inf")
    """Positive infinity."""

    NEG_INF: _ClassVar[float] = float("-inf")
    """Negative infinity."""

    def __init__(self, min: _Optional[float], max: _Optional[float]):
        if max is None:
            max = self.POS_INF
        if min is None:
            min = self.NEG_INF
        if min > max:
            raise ValueError(
                "The provided max value was smaller than the provided "
                "min value."
            )
        object.__setattr__(self, "min", min)
        object.__setattr__(self, "max", max)

    @property
    def actually_bounded(self) -> bool:
        """Whether this instance actually imposes boundaries on the fit
        parameter. If both `min` and `max` are set to None, this is
        not the case.
        """
        return self.min_finite or self.max_finite

    @property
    def min_finite(self) -> bool:
        """Whether the min value is finite.

        Returns:
            bool: Whether the min value is finite.
        """
        return _cmath.isfinite(self.min)

    @property
    def max_finite(self) -> bool:
        """Whether the max value is finite.

        Returns:
            bool: Whether the max value is finite.
        """
        return _cmath.isfinite(self.max)

    def resolve_default(self, field_default: _FloatOrMissing) -> float:
        """Resolves the default value to be assigned to a field
        described by the `BoundedField` instance.

        Args:
            field_default (float or MISSING): The default value passed
                to the dataclass `Field` or the missing value, if none
                was passed.

        Returns:
            float: The default value for the field. This will be
                `field_default` if it was provided and is within the
                bounds described by this instance or the result of
                `get_bounds_default()` otherwise.
        """
        has_default = field_default is not _dataclasses.MISSING
        if (has_default and self.contains(field_default)):  # type: ignore
            return field_default
        return self.get_bounds_default()

    def get_bounds_default(self) -> float:
        """Compute a valid default value within the bounds.

        Returns:
            float: The computed default value. If both bounds are
                finite, this is their average value. If both are
                non-finite, the value is 0. If one bound is finite, the
                value lies with a distance of 1 to the finite bound
                within the bounded region.
        """
        min_fin = self.min_finite
        max_fin = self.max_finite
        if min_fin and max_fin:
            min = self.min
            max = self.max
            return 0.5 * (min + max)  # type: ignore [operator]
        if min_fin:
            return self.min + 1  # type: ignore [operator,return-value]
        elif max_fin:
            return self.max - 1  # type: ignore [operator,return-value]
        else:
            return 0.0  # type: ignore [return-value]

    def contains(self, value: float) -> bool:
        """Checks whether a given value lies in the bounded region
        described by this `BoundedField` instance.

        Args:
            value (float): The value to check.

        Returns:
            bool: Whether the value lies between the lower (self.min)
                and upper bound (self.max).
        """
        res = True
        if self.min_finite:
            res &= value >= self.min
        if self.max_finite:
            res &= value <= self.max
        return res


@_dataclass(frozen=True)
class ConstField(FittingField):

    __slots__ = ("value",)

    value: float
    """The value of the field."""


@_dataclass(frozen=True)
class SameAsField(FittingField):

    __slots__ = ("name",)

    name: str
    """The name of the field the field depends on."""


@_dataclass(frozen=True)
class RegularField(FittingField):

    _instance: _ClassVar[_Optional["RegularField"]] = None
    """An instance of this class."""

    @classmethod
    def get_instance(cls) -> "RegularField":  # pragma: no cover
        """Get a cached instance of this class.

        Returns:
            RegularField: A (possible cached) instance of the
                `RegularField` class.
        """
        instance = cls._instance
        if instance is None:
            instance = cls()
            cls._instance = instance
        return instance


_BoolOrMissing = _Union[bool, _MissingType]  # type: ignore [valid-type]
"""The type representing a `bool` or `dataclasses.MISSING`."""


_FloatDefaultFactoryOrMissing = _Union[
    _Callable[[], float], _MissingType  # type: ignore [valid-type]
]
"""The type of the default factory returning a float for dataclass
fields or `dataclasses.MISSING`."""


def _merge_medatada(
    field_metadata_instance: FittingField,
    provided: _Optional[_Mapping[_Any, _Any]]
) -> _Mapping[_Any, _Any]:
    """Merge the user-provided metadata with the metadata key for the
    fit description fields.

    Args:
        field_metadata_instance (FittingField): The field to add.
        provided (Mapping[Any, Any] | None): The user-provided metadata
            or None.

    Returns:
        Mapping[Any, Any]: The metadata to store in the field.
    """
    if provided is not None:  # pragma: no cover
        res = dict(provided)
        if _METADATA_KEY in provided:
            _warnings.warn(
                "The metadata key for the fit field definitions was "
                "already contained in the provided 'metadata' mapping. "
                "The corresponding value will be overwritten.",
                stacklevel=3,
                category=_warning_types.MetadataKeyOverwrittenWarning
            )
    else:
        res = dict()
    res[_METADATA_KEY] = field_metadata_instance
    return res


if _sys.version_info >= (3, 10):

    def bounded(
        min: _Optional[float] = None,
        max: _Optional[float] = None,
        *,
        default: _FloatOrMissing = _MISSING,
        default_factory: _FloatDefaultFactoryOrMissing = _MISSING,
        repr: bool = True,
        hash: _Optional[bool] = None,
        compare: bool = True,
        metadata: _Optional[_Mapping[_Any, _Any]] = None,
        kw_only: _BoolOrMissing = _MISSING
    ) -> _Any:
        """Define a fit parameter as bounded. Either one, two or no
        boundaries may be provided. The remaining unset boundaries are
        interpreted to be -inf for the lower and +inf for the upper
        boundary.

        Args:
            min (float, optional): The lower bound. Defaults to -inf.
            max (float, optional): The upper bound. Defaults to +inf.
            default (float, optional): The default (initial) value for
                the field. Defaults to the default value used by the fit
                function for a bounded field.
            default_factory (Callable[[], float], optional): A function
                to be called to produce the fields default value. If
                unset, the `default` will be used instead.
            repr (bool, optional): Whether the field should be included
                in the object's repr(). Defaults to True.
            hash (bool, optional): Whether the field should be included
                in the object's hash(). Defaults to None.
            compare (bool, optional): Whether the field should be used
                in comparison function. Defaults to True.
            metadata (Mapping[Any, Any], optional): Metadata to add to
                the field. Defaults to None.
            kw_only (bool, optional): Whether the field will become a
                keyword-only parameter to __init__(). Defaults to False.

        Returns:
            The dataclass field.
        """
        m = BoundedField(min, max)
        metadata = _merge_medatada(m, metadata)
        return _dataclasses.field(  # type: ignore [call-overload]
            default=default,
            default_factory=default_factory,
            repr=repr,
            hash=hash,
            compare=compare,
            metadata=metadata,
            kw_only=kw_only
        )

    def const(
        value: float,
        *,
        repr: bool = True,
        hash: _Optional[bool] = None,
        compare: bool = True,
        metadata: _Optional[_Mapping[_Any, _Any]] = None,
        kw_only: _BoolOrMissing = _MISSING
    ) -> float:
        """Define a fit parameter as constant. The parameter is fixed
        and will not be fitted against. The value will also be set as
        the default value for the field at the constructor.

        Args:
            value (float): The value of the field.
            repr (bool, optional): Whether the field should be included
                in the object's repr(). Defaults to True.
            hash (bool, optional): Whether the field should be included
                in the object's hash(). Defaults to None.
            compare (bool, optional): Whether the field should be used
                in comparison function. Defaults to True.
            metadata (Mapping[Any, Any], optional): Metadata to add to
                the field. Defaults to None.
            kw_only (bool, optional): Whether the field will become a
                keyword-only parameter to __init__(). Defaults to False.

        Returns:
            The dataclass field.
        """
        m = ConstField(value)
        metadata = _merge_medatada(m, metadata)
        return _dataclasses.field(  # type: ignore [call-overload]
            default=value,
            repr=repr,
            hash=hash,
            compare=compare,
            metadata=metadata,
            kw_only=kw_only
        )

    def same_as(
        name: str,
        *,
        default: _FloatOrMissing = _MISSING,
        default_factory: _FloatDefaultFactoryOrMissing = _MISSING,
        repr: bool = True,
        hash: _Optional[bool] = None,
        compare: bool = True,
        metadata: _Optional[_Mapping[_Any, _Any]] = None,
        kw_only: _BoolOrMissing = _MISSING
    ) -> _Any:
        """Define a fit parameter as identical to another parameter. It
        is still possible to set a `default` or `default_factory` for
        the field. This will be used when calling the constructor
        without providing a value for this field.

        Args:
            name (str): The name of the parameter this one is identical
                to.
            default (float, optional): The default (initial) value for
                the field. Defaults to the default value used by the fit
                function for a bounded field.
            default_factory (Callable[[], float], optional): A function
                to be called to produce the fields default value. If
                unset, the `default` will be used instead.
            repr (bool, optional): Whether the field should be included
                in the object's repr(). Defaults to True.
            hash (bool, optional): Whether the field should be included
                in the object's hash(). Defaults to None.
            compare (bool, optional): Whether the field should be used
                in comparison function. Defaults to True.
            metadata (Mapping[Any, Any], optional): Metadata to add to
                the field. Defaults to None.
            kw_only (bool, optional): Whether the field will become a
                keyword-only parameter to __init__(). Defaults to False.

        Returns:
            The dataclass field.
        """
        m = SameAsField(name)
        metadata = _merge_medatada(m, metadata)
        return _dataclasses.field(  # type: ignore [call-overload]
            default=default,
            default_factory=default_factory,
            repr=repr,
            hash=hash,
            compare=compare,
            metadata=metadata,
            kw_only=kw_only
        )

    def regular(
        *,
        default: _FloatOrMissing = _MISSING,
        default_factory: _FloatDefaultFactoryOrMissing = _MISSING,
        repr: bool = True,
        hash: _Optional[bool] = None,
        compare: bool = True,
        metadata: _Optional[_Mapping[_Any, _Any]] = None,
        kw_only: _BoolOrMissing = _MISSING
    ) -> _Any:
        """Define regular fit parameter. The value must be provided at
        __init__ when constructing instances of the dataclass.

        Args:
            default (float, optional): The default (initial) value for
                the field. Defaults to the default value used by the fit
                function for a bounded field.
            default_factory (Callable[[], float], optional): A function
                to be called to produce the fields default value. If
                unset, the `default` will be used instead.
            repr (bool, optional): Whether the field should be included
                in the object's repr(). Defaults to True.
            hash (bool, optional): Whether the field should be included
                in the object's hash(). Defaults to None.
            compare (bool, optional): Whether the field should be used
                in comparison function. Defaults to True.
            metadata (Mapping[Any, Any], optional): Metadata to add to
                the field. Defaults to None.
            kw_only (bool, optional): Whether the field will become a
                keyword-only parameter to __init__(). Defaults to False.

        Returns:
            The dataclass field.
        """
        m = RegularField.get_instance()
        metadata = _merge_medatada(m, metadata)
        return _dataclasses.field(  # type: ignore [call-overload]
            default=default,
            default_factory=default_factory,
            repr=repr,
            hash=hash,
            compare=compare,
            metadata=metadata,
            kw_only=kw_only
        )

else:

    # The "type: ignore [misc]" markers below prevent mypy from
    # complaining about differing signatures of the conditional
    # function defintions.

    def bounded(  # type: ignore [misc]
        min: _Optional[float] = None,
        max: _Optional[float] = None,
        *,
        default: _FloatOrMissing = _MISSING,
        default_factory: _FloatDefaultFactoryOrMissing = _MISSING,
        repr: bool = True,
        hash: _Optional[bool] = None,
        compare: bool = True,
        metadata: _Optional[_Mapping[_Any, _Any]] = None
    ) -> _Any:
        """Define a fit parameter as bounded. Either one, two or no
        boundaries may be provided. The remaining unset boundaries are
        interpreted to be -inf for the lower and +inf for the upper
        boundary.

        Args:
            min (float, optional): The lower bound. Defaults to -inf.
            max (float, optional): The upper bound. Defaults to +inf.
            default (float, optional): The default (initial) value for
                the field. Defaults to the default value used by the fit
                function for a bounded field.
            default_factory (Callable[[], float], optional): A function
                to be called to produce the fields default value. If
                unset, the `default` will be used instead.
            repr (bool, optional): Whether the field should be included
                in the object's repr(). Defaults to True.
            hash (bool, optional): Whether the field should be included
                in the object's hash(). Defaults to None.
            compare (bool, optional): Whether the field should be used
                in comparison function. Defaults to True.
            metadata (Mapping[Any, Any], optional): Metadata to add to
                the field. Defaults to None.

        Returns:
            The dataclass field.
        """
        m = BoundedField(min, max)
        metadata = _merge_medatada(m, metadata)
        return _dataclasses.field(  # type: ignore [call-overload]
            default=default,
            default_factory=default_factory,
            repr=repr,
            hash=hash,
            compare=compare,
            metadata=metadata
        )

    def const(  # type: ignore [misc]
        value: float,
        *,
        repr: bool = True,
        hash: _Optional[bool] = None,
        compare: bool = True,
        metadata: _Optional[_Mapping[_Any, _Any]] = None
    ) -> float:
        """Define a fit parameter as constant. The parameter is fixed
        and will not be fitted against. The value will also be set as
        the default value for the field at the constructor.

        Args:
            value (float): The value of the field.
            repr (bool, optional): Whether the field should be included
                in the object's repr(). Defaults to True.
            hash (bool, optional): Whether the field should be included
                in the object's hash(). Defaults to None.
            compare (bool, optional): Whether the field should be used
                in comparison function. Defaults to True.
            metadata (Mapping[Any, Any], optional): Metadata to add to
                the field. Defaults to None.

        Returns:
            The dataclass field.
        """
        m = ConstField(value)
        metadata = _merge_medatada(m, metadata)
        return _dataclasses.field(  # type: ignore [call-overload]
            default=value,
            repr=repr,
            hash=hash,
            compare=compare,
            metadata=metadata
        )

    def same_as(  # type: ignore [misc]
        name: str,
        *,
        default: _FloatOrMissing = _MISSING,
        default_factory: _FloatDefaultFactoryOrMissing = _MISSING,
        repr: bool = True,
        hash: _Optional[bool] = None,
        compare: bool = True,
        metadata: _Optional[_Mapping[_Any, _Any]] = None
    ) -> _Any:
        """Define a fit parameter as identical to another parameter. It
        is still possible to set a `default` or `default_factory` for
        the field. This will be used when calling the constructor
        without providing a value for this field.

        Args:
            name (str): The name of the parameter this one is identical
                to.
            default (float, optional): The default (initial) value for
                the field. Defaults to the default value used by the fit
                function for a bounded field.
            default_factory (Callable[[], float], optional): A function
                to be called to produce the fields default value. If
                unset, the `default` will be used instead.
            repr (bool, optional): Whether the field should be included
                in the object's repr(). Defaults to True.
            hash (bool, optional): Whether the field should be included
                in the object's hash(). Defaults to None.
            compare (bool, optional): Whether the field should be used
                in comparison function. Defaults to True.
            metadata (Mapping[Any, Any], optional): Metadata to add to
                the field. Defaults to None.
            kw_only (bool, optional): Whether the field will become a
                keyword-only parameter to __init__(). Defaults to False.

        Returns:
            The dataclass field.
        """
        m = SameAsField(name)
        metadata = _merge_medatada(m, metadata)
        return _dataclasses.field(  # type: ignore [call-overload]
            default=default,
            default_factory=default_factory,
            repr=repr,
            hash=hash,
            compare=compare,
            metadata=metadata
        )

    def regular(  # type: ignore [misc]
        *,
        default: _FloatOrMissing = _MISSING,
        default_factory: _FloatDefaultFactoryOrMissing = _MISSING,
        repr: bool = True,
        hash: _Optional[bool] = None,
        compare: bool = True,
        metadata: _Optional[_Mapping[_Any, _Any]] = None
    ) -> _Any:
        """Define regular fit parameter. The value must be provided at
        __init__ when constructing instances of the dataclass.

        Args:
            default (float, optional): The default (initial) value for
                the field. Defaults to the default value used by the fit
                function for a bounded field.
            default_factory (Callable[[], float], optional): A function
                to be called to produce the fields default value. If
                unset, the `default` will be used instead.
            repr (bool, optional): Whether the field should be included
                in the object's repr(). Defaults to True.
            hash (bool, optional): Whether the field should be included
                in the object's hash(). Defaults to None.
            compare (bool, optional): Whether the field should be used
                in comparison function. Defaults to True.
            metadata (Mapping[Any, Any], optional): Metadata to add to
                the field. Defaults to None.

        Returns:
            The dataclass field.
        """
        m = RegularField.get_instance()
        metadata = _merge_medatada(m, metadata)
        return _dataclasses.field(  # type: ignore [call-overload]
            default=default,
            default_factory=default_factory,
            repr=repr,
            hash=hash,
            compare=compare,
            metadata=metadata
        )
