import dataclasses as _dataclasses
import numpy as _numpy
import sys as _sys

from abc import ABC as _ABC, abstractmethod as _abstractmethod
from dataclasses import dataclass as _dataclass
from numpy import dtype as _dtype, floating as _floating
from numpy.typing import NDArray as _NDArray
from typing import Any as _Any, Dict as _Dict, final as _final, \
    Generic as _Generic, List as _List, Mapping as _Mapping, \
    Sequence as _Sequence, Tuple as _Tuple, Type as _Type, \
    TypeVar as _TypeVar
from typing import Union as _Union

from . import _fields
from . import _depgraph

from ._fields import FittingField as _FittingField


_T = _TypeVar("_T")


def _is_dataclass(cls: _Type) -> bool:
    """Checks whether a class is a dataclass. This wraps
    `dataclasses.is_dataclass` and removes the TypeGuard since this
    currently causes issues with mypy.
    """
    return _dataclasses.is_dataclass(cls)


BoundsTuple = _Tuple[_NDArray[_floating], _NDArray[_floating]]
"""The type of a tuple definining the fit parameter bounds."""


@_dataclass(frozen=True)
class DependentFieldValueResolver(_ABC):
    """Base class for objects resolving values of dependent fields."""

    __slots__ = ("target",)

    target: str
    """The name of the field that 'depends'."""

    @_abstractmethod
    def get(self, others: _Dict[str, _Any]) -> _Any:
        pass


class DefaultResolver(_ABC):
    """Base class for objects resolving the default values of special
    fields.
    """

    @_abstractmethod
    def get(self, others: _Dict[str, _Any]) -> _Any:
        pass


@_final
class UnsetDefaultResolver(DefaultResolver):
    """A `DefaultResolver` for fields which do not have a default set
    and it is also not possible to otherwise determine a default.
    """

    def get(self, _: _Dict[str, _Any]) -> _Any:
        return 0.0


@_final
@_dataclass(frozen=True)
class FixedDefaultResolver(DefaultResolver):
    """A `DefaultResolver` with a fixed constant value."""

    __slots__ = ("value",)

    value: _Any
    """The fixed default value"""

    def get(self, _: _Dict[str, _Any]) -> _Any:
        return self.value


@_final
@_dataclass(frozen=True)
class DependentResolver(DependentFieldValueResolver, DefaultResolver):
    """A `DefaultResolver` indicating that the value is identical to the
    value of another field.
    """

    __slots__ = ("name",)

    name: str
    """The name of the field from which to obtain the default value."""

    def get(self, others: _Dict[str, _Any]) -> _Any:
        return others[self.name]


@_dataclass(frozen=True)
class FitSpecBase:
    """The base class for a class containing info about a class defining
    a fit.
    """

    __slots__ = (
        "special_param_count",
        "init_order",
        "fitting_param_count",
        "fitting_params",
        "fitting_fields",
        "default_resolvers",
        "lower_bounds",
        "upper_bounds",
        "bounds",
        "dep_resolvers"
    )

    special_param_count: int
    """The number of fitting parameters, including dependent and const
    parameters."""

    init_order: _Sequence[str]
    """The order in which the special parameters will be initialized."""

    fitting_param_count: int
    """The number of actual fitting parameters."""

    fitting_params: _Sequence[str]
    """The actual parameters that are part of the fitting procedure."""

    fitting_fields: _Mapping[str, _Union[_FittingField, None]]
    """A dict mapping field names to the descriptors for the fitting
    fields or None, if it is a regular field."""

    default_resolvers: _Sequence[DefaultResolver]
    """The resolvers for the default values of the fields."""

    lower_bounds: _Union[_NDArray[_floating], None]
    """The lower bounds or None, if they do not need to be set."""

    upper_bounds: _Union[_NDArray[_floating], None]
    """The upper bounds or None, if they do not need to be set."""

    bounds: BoundsTuple
    """The bounds tuple."""

    dep_resolvers: _Sequence[DependentResolver]
    """The resolvers for the dependent fields."""

    @classmethod
    def _process_bounds(
        cls,
        set_bounds: _Dict[int, float],
        num_params: int,
        default: float
    ) -> _Union[_NDArray[_floating], None]:
        if len(set_bounds) == 0:
            return None
        result = _numpy.full((num_params,), default)
        for k, v in set_bounds.items():
            result[k] = v
        result.flags.writeable = False
        return result

    @classmethod
    def generate(cls, t: _Type[_T]):
        """Generate the `FitSpecBase` or a derived class for a type.

        Args:
            t (Type[T]): The type/dataclass for which to generate the
                `FitSpecBase`.

        Raises:
            TypeError: If the provided type `t` is not a dataclass.
            NotImplementedError: If an unkown fitting field description
                (FittingField subclass) is encountered.
            ValueError: _description_

        Returns:
            FitSpecBase or subclass: The generated `FitSpecBase`.
        """
        if not _is_dataclass(t):
            raise TypeError(  # pragma: no cover
                f"The type {t.__qualname__!r} is not a dataclass."
            )

        all_fields_ordered = _dataclasses.fields(t)  # type: ignore [arg-type]

        depgraph = _depgraph.DepGraph((f.name for f in all_fields_ordered))

        field_descriptors: _Dict[str, _Union[_FittingField, None]] = dict()

        set_lower_bounds: _Dict[int, float] = dict()
        set_upper_bounds: _Dict[int, float] = dict()
        default_resolvers: _List[DefaultResolver] = list()

        special_fields: _List[str] = list()
        fitting_fields: _List[str] = list()

        dep_resolver_map: _Dict[str, DependentResolver] = dict()

        init_fields = (f for f in all_fields_ordered if f.init)
        for i, field in enumerate(init_fields):
            field_name = field.name
            special_fields.append(field_name)

            info = _fields.get_special_fitting_field(field)
            field_descriptors[field_name] = info

            def_res: DefaultResolver
            if (info is None) or isinstance(info, _fields.RegularField):
                field_default = field.default
                if field_default is _dataclasses.MISSING:
                    def_res = UnsetDefaultResolver()
                else:
                    def_res = FixedDefaultResolver(field_default)
                fitting_fields.append(field_name)
            else:
                if isinstance(info, _fields.BoundedField):
                    if info.min_finite:
                        v_min: _Any = info.min
                        set_lower_bounds[i] = v_min
                    if info.max_finite:
                        v_max: _Any = info.max
                        set_upper_bounds[i] = v_max
                    df_val = info.resolve_default(field.default)
                    def_res = FixedDefaultResolver(df_val)
                    fitting_fields.append(field_name)
                elif isinstance(info, _fields.ConstField):
                    def_res = FixedDefaultResolver(info.value)
                elif isinstance(info, _fields.SameAsField):
                    dep_name = info.name
                    field_name = field_name  # Name of the depending one
                    depgraph.add_dependency(field_name, dep_name)
                    def_res = DependentResolver(field_name, dep_name)
                    dep_resolver_map[field_name] = def_res
                else:
                    raise NotImplementedError(
                        f"Unknown FittingField encountered: {info!r}"
                    )
            default_resolvers.append(def_res)

        num_special_params = len(special_fields)

        t_def_res = tuple(default_resolvers)
        if len(t_def_res) != num_special_params:
            raise AssertionError

        if depgraph.dependency_count > 0:
            if depgraph.has_closed_cycles():
                raise ValueError(
                    "There are circular dependencies in the field "
                    "dependencies meaning that some fields cannot be "
                    "initialized."
                )
            init_order = depgraph.get_init_order()
            ssf = set(special_fields)
            init_order = tuple((f for f in init_order if f in ssf))
            if len(init_order) != num_special_params:
                raise AssertionError

            def get_dep_resolvers(ordered_fields: _Sequence[str]):
                """Yield the `DependentResolver`s for the dependent
                fields in construction order.

                Args:
                    ordered_fields (Sequence[str]): The fields in the
                        order of construction.

                Yields:
                    DependentResolver: The resolvers for the fields.
                """
                for f in ordered_fields:
                    try:
                        yield dep_resolver_map[f]
                    except KeyError:
                        pass

            dep_resolvers_seq = tuple(get_dep_resolvers(init_order))
        else:
            init_order = tuple(special_fields)
            dep_resolvers_seq = ()

        num_fitting_params = len(fitting_fields)

        lower_bounds = cls._process_bounds(
            set_lower_bounds, num_fitting_params, -_numpy.inf
        )
        upper_bounds = cls._process_bounds(
            set_upper_bounds, num_fitting_params, _numpy.inf
        )

        lb = lower_bounds
        if lb is None:
            lb = _numpy.array(-_numpy.inf)
            lb.flags.writeable = False
        ub = upper_bounds
        if ub is None:
            ub = _numpy.array(_numpy.inf)
            ub.flags.writeable = False
        bounds = (lb, ub)

        return cls(
            num_special_params,
            init_order,
            num_fitting_params,
            tuple(fitting_fields),
            field_descriptors,
            t_def_res,
            lower_bounds,
            upper_bounds,
            bounds,
            dep_resolvers_seq
        )


if _sys.version_info < (3, 9):
    DTypeLikeFloat = _Union[  # type: ignore [misc]
        _Type[float],
        _Type[_floating]
    ]
else:
    DTypeLikeFloat = _Union[  # type: ignore [misc]
        _Type[float],
        _Type[_floating],
        _dtype[_floating],
    ]


@_dataclass(frozen=True)
class FitSpec(FitSpecBase, _Generic[_T]):
    """The specification for a fit class."""

    __slots__ = ("clss",)

    clss: _Type[_T]  # Note: cannot be named cls in python < 3.9
    """The type for which this instance specifies information."""

    def create_default_fit_instance(self) -> _T:
        """Get the default instance for the fit.

        Returns:
            T: The instance.
        """
        init_order = self.init_order
        def_res = self.default_resolvers

        params: _Dict[str, _Any] = dict()

        for fname, resolver in zip(init_order, def_res):
            value = resolver.get(params)
            params[fname] = value

        return self.clss(**params)

    def new_empty_array(self, dtype: DTypeLikeFloat) -> _NDArray[_floating]:
        return _numpy.empty((self.fitting_param_count,), dtype)

    def instance_to_array(
        self,
        instance: _T,
        out: _NDArray[_floating]
    ):
        num_params = self.fitting_param_count
        given_shape = out.shape
        expected_shape = (num_params,)
        if given_shape != expected_shape:
            raise ValueError(  # pragma: no cover
                f"The provided array has an invalid shape: {given_shape}."
                f"Expected: {expected_shape}."
            )

        for i, field in enumerate(self.fitting_params):
            out[i] = getattr(instance, field)

    def array_to_instance(
        self,
        array: _Sequence[float]
    ) -> _T:
        num_params = self.fitting_param_count
        array_len = len(array)
        if array_len != num_params:
            raise ValueError(  # pragma: no cover
                f"Unexpected number of parameters: {array_len}. "
                f"Expected {num_params}."
            )

        kwargs: _Dict[str, _Any] = dict()
        for i, field in enumerate(self.fitting_params):
            kwargs[field] = array[i]

        # Resolve dependent fields
        for resolver in self.dep_resolvers:
            kwargs[resolver.target] = resolver.get(kwargs)

        return self.clss(**kwargs)
