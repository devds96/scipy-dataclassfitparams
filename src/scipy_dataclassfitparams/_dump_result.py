import io as _io
import math as _math
import os as _os

from dataclasses import dataclass as _dataclass
from enum import Enum as _Enum, unique as _unique
from io import TextIOBase as _TextIOBase
from typing import Generic as _Generic, List as _List, Literal as _Literal, \
    Optional as _Optional, overload as _overload, \
    SupportsFloat as _SupportsFloat, Type as _Type, TypeVar as _TypeVar, \
    Union as _Union

from . import _spec_registry as _spec_registry

from ._make_fit import FitResult as _FitResult
from ._fit_spec import FitSpec as _FitSpec
from ._fields import BoundedField as _BoundedField, \
    ConstField as _ConstField, FittingField as _FittingField, \
    RegularField as _RegularField, SameAsField as _SameAsField


_T = _TypeVar("_T")


@_unique
class WhichFloat(_Enum):
    """Determines which float is to be formatted."""

    FieldValue = 1
    """The value of a field should be formatted."""

    LowerBound = 2
    """The lower bound for a field should be formatted."""

    UpperBound = 3
    """The upper bound for a field should be formatted."""

    InitialValue = 4
    """The initial value for a field should be formatted."""


@_unique
class PrintBounds(_Enum):
    """The mode for printing information about the bounds of a fitting
    field.
    """

    always = "always"
    """Always print bounds."""

    never = "never"
    """Suppress all bounds."""

    bounded = "bounded"
    """Only print bounds for `BoundedField`s."""

    @classmethod
    def sanitize(cls, value: "_PrintBoundsArg") -> "PrintBounds":
        """Sanitize a `_PrintBoundsArg` value to be a `PrintBounds`
        value.

        Args:
            value (_PrintBoundsArg): The value to sanitize.

        Raises:
            TypeError: If `value` is not a valid `_PrintBoundsArg`
                value and not a str.
            ValueError: If `value` is not a valid `_PrintBoundsArg`
                value, but a str, and therefore does not correspond to a
                `PrintBounds` instance.

        Returns:
            PrintBounds: The `PrintBounds` instance.
        """
        if isinstance(value, PrintBounds):
            return value
        inner_exc = None
        exception: _Type[Exception]
        exception = TypeError
        if isinstance(value, str):
            try:
                return cls[value]
            except KeyError as e:
                inner_exc = e
                exception = ValueError
        raise exception(
            f"Invalid 'PrintBounds' value {value!r}."
        ) from inner_exc


_PrintBoundsLiteral = _Literal["always", "never", "bounded"]  # noqa: F821
"""The values for the `PrintBounds` enumeration as `str` values."""

_PrintBoundsArg = _Union[PrintBounds, _PrintBoundsLiteral]
"""Either a value of the `PrintBounds` enumeration or its `str`
value."""


@_dataclass(frozen=True)
class InstanceFormatter(_Generic[_T]):

    __slots__ = (
        "instance",
        "print_header",
        "print_extra_params",
        "linesep",
        "print_bounds",
        "print_initial_values",
        "clss",
        "fitspec",
        "initial_instance",
        "p0_provided"
    )

    instance: _T
    """The instance to format."""

    print_header: bool
    """Whether to print the header indicating the class name. Defaults
    to True."""

    print_extra_params: bool
    """Whether to print parameters that did not partake in the fitting
    procedure, such as dependent fields. Defaults to True."""

    linesep: str
    """The line separator. Defaults to `os.linesep`."""

    print_bounds: PrintBounds
    """The mode for printing information about the bounds of a fitting
    field. Defaults to 'always'."""

    print_initial_values: bool
    """Whether to print initial values for regular and bound fields.
    Defaults to True."""

    clss: _Type[_T]
    """The type of the instance to format."""

    fitspec: _FitSpec[_T]
    """The fitspec for the instance,"""

    initial_instance: _T
    """The default instance (p0) which starts the fit corresponding to
    the instance. This may either be the provided value or the default
    value constructed from the `FitSpec`, depending on `p0_provided`."""

    p0_provided: bool
    """Whether a p0 instance was provided."""

    @_overload
    def __init__(
        self,
        instance: _T,
        *,
        print_header: _Optional[bool] = None,
        print_extra_params: _Optional[bool] = None,
        print_bounds: _Optional[_PrintBoundsArg] = None,
        print_initial_values: _Optional[bool] = None,
        p0: _Optional[_T] = None,
        linesep: _Optional[str] = None
    ):
        pass

    @_overload
    def __init__(
        self,
        instance: _FitResult[_T],
        *,
        print_header: _Optional[bool] = None,
        print_extra_params: _Optional[bool] = None,
        print_bounds: _Optional[_PrintBoundsArg] = None,
        print_initial_values: _Optional[bool] = None,
        linesep: _Optional[str] = None
    ):
        pass

    # Init has to be provided manually because if incompatibilities
    # between __slots__ and default values.
    def __init__(
        self,
        instance: _Union[_T, _FitResult[_T]],
        *,
        print_header: _Optional[bool] = None,
        print_extra_params: _Optional[bool] = None,
        print_bounds: _Optional[_PrintBoundsArg] = None,
        print_initial_values: _Optional[bool] = None,
        p0: _Optional[_T] = None,
        linesep: _Optional[str] = None
    ):
        """Create a new instance of the default `InstanceFormatter`.

        Args:
            instance (T | FitResult[T]]): Either the instance or the
                corresponding FitResult which should be formatted.
            print_header (bool, optional): Whether to print the header
                mentioning the class name. Defaults to True.
            print_extra_params (bool, optional): Whether to print the
                extra parameters available on the class which were not
                fit against, such as constant values. Defaults to True.
            print_bounds (PrintBounds | Literal["always", "never",
                "bounded"], optional): A `PrintBounds` value or the
                corresponding `str` alue indicating how to print the
                bounds for fields. Defaults to "always".
            print_initial_values (bool, optional): Whether to print
                the initial values. Defaults to True. If no `p0` is
                provided, the initial instance will be generated
                from the `FitSpec`.
            p0 (T, optional): The initial instance. If not provided, it
                will be generated from the `FitSpec`. Must not be
                provided if `instance` is a `FitResult` instance, in
                which case p0 will be inferred from the instance.
            linesep (str, optional): The newline separator to use.
                Defaults to `os.linesep`.

        Raises:
            ValueError: If `print_bounds` is not a valid value as
                mentioned above. If `instance` is a `FitResult` instance
                and `p0` is provided.
        """
        if isinstance(instance, _FitResult):
            if p0 is not None:
                raise ValueError(
                    "p0 must not be provided when 'instance' is a "
                    "FitResult."
                )
            p0 = instance.p0
            instance = instance.opt_instance

        object.__setattr__(self, "instance", instance)
        clss = instance.__class__
        object.__setattr__(self, "clss", clss)
        fitspec = _spec_registry.get_fit_spec(clss)
        object.__setattr__(self, "fitspec", fitspec)

        if p0 is None:
            p0 = fitspec.create_default_fit_instance()
            object.__setattr__(self, "p0_provided", False)
        else:
            object.__setattr__(self, "p0_provided", True)
        object.__setattr__(self, "initial_instance", p0)

        if print_header is None:
            print_header = True
        object.__setattr__(self, "print_header", print_header)
        if print_extra_params is None:
            print_extra_params = True
        object.__setattr__(self, "print_extra_params", print_extra_params)
        if linesep is None:
            linesep = _os.linesep
        object.__setattr__(self, "linesep", linesep)
        if print_initial_values is None:
            print_initial_values = True
        object.__setattr__(self, "print_initial_values", print_initial_values)

        if print_bounds is None:
            print_bounds = PrintBounds.always
        print_bounds = PrintBounds.sanitize(print_bounds)
        object.__setattr__(self, "print_bounds", print_bounds)

    def _write_line(self, line: str, stream: _TextIOBase) -> int:
        """Write a line to a text stream. It will be followed by the
        `self.linesep` value.

        Args:
            line (str): The line to write.
            stream (TextIOBase): The stream to write to

        Returns:
            int: The total numbers of written characters, including the
                line separator.
        """
        return stream.write(line) + stream.write(self.linesep)

    def format_instance(self) -> str:
        """Format the instance and return the result as a `str`.

        Returns:
            str: The formatted instance.
        """
        buffer = _io.StringIO(newline=self.linesep)
        self.process_instance(buffer)
        return buffer.getvalue()

    # Maybe write to io object instead of list?
    def process_instance(self, output: _TextIOBase):
        """Process the instance and write the output information to the
        provided stream. Note that if an exception occurs during this
        method, the provided stream may contain incomplete/corrupted
        output.

        Args:
            output (TextIOBase): The stream to write to.
        """

        # Header
        if self.print_header:
            header = self._format_header()
            self._write_line(header, output)

        instance = self.instance

        # Fitting fields
        fs = self.fitspec
        descriptors = dict(fs.fitting_fields)
        for fpfn in fs.fitting_params:
            field = descriptors.pop(fpfn)
            value = getattr(instance, fpfn)
            ff = self._format_field(fpfn, True, field, value)
            self._write_line(ff, output)

        # Extra fields
        if self.print_extra_params and (len(descriptors) > 0):
            self._write_line("Additional parameters (not fitted):", output)

            for p in fs.init_order:
                try:
                    field = descriptors.pop(p)
                except KeyError:
                    continue
                value = getattr(instance, p)
                ff = self._format_field(p, False, field, value)
                self._write_line(ff, output)

    def _format_header(self) -> str:
        """Format the header that contains the class name.

        Returns:
            str: The header to write to the output.
        """
        clss = self.clss
        return f"Fit performed with type {clss.__qualname__!r}:"

    def _format_float(
        self,
        value: _SupportsFloat,
        field: str,
        which: WhichFloat
    ) -> str:
        """Format a float to be written to the output.

        Args:
            value (SupportsFloat): The value of the float. This may also
                be inf or -inf.
            field (str): The field this value belongs to.
            which (WhichFloat): Information about in which way the
                provided value belongs to the field.

        Returns:
            str: The formatted float.
        """
        return f"{float(value):.15e}"

    def _format_bounds_extra(
        self,
        name: str,
        field: _Union[_FittingField, None]
    ) -> str:
        """Format the extra information about the bounds.

        Args:
            name (str): The name of the field.
            field (FittingField or None): The fit field description.

        Returns:
            str: The extra information about the field bounds.
        """
        if (
            (not isinstance(field, _BoundedField))
            or (not field.actually_bounded)
        ):
            return "unbounded"

        def format_bound(
            v: float,
            b_inf: str,
            b_fin: str,
            which: WhichFloat,
            fstr: str
        ) -> str:
            b = b_inf if _math.isinf(v) else b_fin
            v_s = self._format_float(v, name, which)
            return fstr.format(value=v_s, bracket=b)

        max_s = format_bound(
            field.max, '[', ']', WhichFloat.UpperBound, "{value}{bracket}"
        )
        min_s = format_bound(
            field.min, ']', '[', WhichFloat.LowerBound, "{bracket}{value}"
        )
        return f"bounded: {min_s};{max_s}"

    def _format_initial_value_extra(
        self,
        name: str,
        field: _Union[_FittingField, None]
    ) -> str:
        """Format the extra information about the field's initial value.

        Args:
            name (str): The name of the field
            field (FittingField or None): The fit field description.

        Returns:
            str: The extra information about the initial value of the
                field.
        """
        default = getattr(self.initial_instance, name)
        dfvs = self._format_float(default, name, WhichFloat.InitialValue)
        return f"initial: {dfvs}"

    def _format_field(
        self,
        name: str,
        is_fitparam: bool,
        field: _Union[_FittingField, None],
        value: float
    ) -> str:
        """Format a field.

        Args:
            name (str): The name of the field.
            is_fitparam (bool): Whether the field as a fit parameter.
                If False, the field is an "extra".
            field (FittingField or None): The fit field description.
            value (float): The value of the field in the optimized
                instance.

        Raises:
            NotImplementedError: If `field` is not a known
                `FittingField`.
            TypeError: If `field` is not a `FittingField`.

        Returns:
            str: The formatted information regarding the `field`.
        """
        value_str = self._format_float(value, name, WhichFloat.FieldValue)

        extras: _List[str] = list()

        if isinstance(field, _ConstField):
            extras.append("const.")
        elif isinstance(field, _SameAsField):
            extras.append(f"=!= {field.name!r}")
        elif isinstance(field, _BoundedField):
            if self.print_bounds != PrintBounds.never:
                extras.append(self._format_bounds_extra(name, field))
            if self.print_initial_values:
                extras.append(self._format_initial_value_extra(name, field))
        elif (field is None) or isinstance(field, _RegularField):
            if self.print_bounds == PrintBounds.always:
                extras.append(self._format_bounds_extra(name, field))
            if self.print_initial_values:
                extras.append(self._format_initial_value_extra(name, field))
        else:  # pragma: no cover
            if isinstance(field, _FittingField):
                exception_type = NotImplementedError
            else:
                exception_type = TypeError
            raise exception_type(
                f"Invalid field description encountered: {field!r}"
            )

        extra_str = ''
        if len(extras) > 0:
            fextras = ", ".join(extras)
            extra_str = f" ({fextras})"

        return f"{name}: {value_str}{extra_str}"


@_overload
def dump_result(
    instance: _FitResult[_T],
    *,
    print_header: _Optional[bool] = None,
    print_extra_params: _Optional[bool] = None,
    print_bounds: _Optional[_PrintBoundsArg] = None,
    print_initial_values: _Optional[bool] = None,
    linesep: _Optional[str] = None
) -> str:
    pass


@_overload
def dump_result(
    instance: _T,
    *,
    print_header: _Optional[bool] = None,
    print_extra_params: _Optional[bool] = None,
    print_bounds: _Optional[_PrintBoundsArg] = None,
    print_initial_values: _Optional[bool] = None,
    p0: _Optional[_T] = None,
    linesep: _Optional[str] = None
) -> str:
    pass


def dump_result(
    instance: _Union[_T, _FitResult[_T], _FitResult],
    *,
    print_header: _Optional[bool] = None,
    print_extra_params: _Optional[bool] = None,
    print_bounds: _Optional[_PrintBoundsArg] = None,
    print_initial_values: _Optional[bool] = None,
    p0: _Optional[_T] = None,
    linesep: _Optional[str] = None
) -> str:
    """Format the optimal instance of a fit into a multiline `str` with
    details using the default `InstanceFormatter`. It is recommended to
    provided the full `FitResult` instance to have `p0` included
    automatically.

    Args:
        instance (T, FitResult[T]): The optimal instance to format,
            either provided directly or via the full `FitResult`.
        print_header (bool, optional): Whether to print the header
            mentioning the class name. Defaults to True.
        print_extra_params (bool, optional): Whether to print the
            extra parameters available on the class which were not
            fit against, such as constant values. Defaults to True.
        print_bounds (PrintBounds | Literal["always", "never",
            "bounded"], optional): A `PrintBounds` value or the
            corresponding `str` alue indicating how to print the
            bounds for fields. Defaults to "always".
        print_initial_values (bool, optional): Whether to print
            the initial values. Defaults to True. If no `p0` is
            provided, the initial instance will be generated
            from the `FitSpec`.
        p0 (T, optional): The initial instance. If not provided, it
            will be generated from the `FitSpec`. Must not be
            provided if `instance` is a `FitResult` instance, in
            which case p0 will be inferred from the instance.
        linesep (str, optional): The newline separator to use.
            Defaults to `os.linesep`.

    Raises:
        ValueError: If `instance` is a `FitResult` instance and `p0` is
            provided.

    Returns:
        str: The str describing the parameters of the optimal instance.
    """
    formatter = InstanceFormatter(
        instance,
        print_header=print_header,
        print_extra_params=print_extra_params,
        print_bounds=print_bounds,
        print_initial_values=print_initial_values,
        p0=p0,
        linesep=linesep
    )
    return formatter.format_instance()
