# scipy-dataclassfitparams

![Tests](https://github.com/devds96/scipy-dataclassfitparams/actions/workflows/tests.yml/badge.svg)
[![Coverage](https://github.com/devds96/scipy-dataclassfitparams/raw/gh-pages/coverage/coverage_badge.svg)](https://devds96.github.io/scipy-dataclassfitparams/coverage/index.html)
![mypy](https://github.com/devds96/scipy-dataclassfitparams/actions/workflows/type.yml/badge.svg)
![flake8](https://github.com/devds96/scipy-dataclassfitparams/actions/workflows/lint.yml/badge.svg)


This package serves as a wrapper around `scipy.optimize.curve_fit` and
makes it possible to define dataclasses which define fit parameters
via their fields.

## Introduction

The idea behind this module is to provide a more high-level approach for
fitting a curve using scipy. The parameters used to fit the function can
be defined as fields of a dataclass. Then, instances of this datalass
will be passed to fit function to perform the fit. Currently, only
single floats are supported for the parameters.

## Example

Let's say we have some data and we want to perform a linear fit on this
dataset. A linear function is defined by two parameters, which can be,
for example, the y-intercept $b$ and the slope $m$, so that the fit
function is given by $f(x)=mx+b$.

I am using the following (almost randomly) selected dataset:

| $x$-value | $y$-value |
|-----------|-----------|
| 0         | -1        |
| 1         | 2         |
| 2.1       | 5         |
| 4         | 7         |
| 4         | 10        |

Which should give $b=-0.518797$ and $m=2.30576$ according to
[WolframAlpha](https://www.wolframalpha.com/input?i=linear+fit+%7B%280%2C+-1%29%2C+%281%2C+2%29%2C+%282.1%2C+5%29%2C+%284%2C+10%29%2C+%284%2C+7%29%7D).

Using this package, the code for performing this fit in python could
look like this:

```python
from dataclasses import dataclass
from numpy import array, floating
from numpy.typing import NDArray
from scipy_dataclassfitparams import dump_result, make_fit


@dataclass
class LinFit:

    m: float

    b: float


def f(x: NDArray[floating], params: LinFit) -> NDArray[floating]:
    return params.m * x + params.b


xdata = array([0, 1, 2.1, 4, 4])
ydata = array([-1, 2, 5, 7, 10])

fit_result = make_fit(LinFit, xdata, ydata, f)
print(dump_result(fit_result))
```

Which should print something like

> Fit performed with type 'LinFit':<br>
> m: 2.305764412812864e+00 (unbounded, initial: 0.000000000000000e+00)<br>
> b: -5.187970074292673e-01 (unbounded, initial: 0.000000000000000e+00)

As hinted at by the result text, it is possible to define fields which
are not "unbounded", meaning that the values must be from some given
range:

```python
from dataclasses import dataclass
from numpy import array, floating
from numpy.typing import NDArray
from scipy_dataclassfitparams import bounded, dump_result, make_fit


@dataclass
class LinFit:

    m: float

    b: float = bounded(min=0)


def f(x: NDArray[floating], params: LinFit) -> NDArray[floating]:
    return params.m * x + params.b


xdata = array([0, 1, 2.1, 4, 4])
ydata = array([-1, 2, 5, 7, 10])

fit_result = make_fit(LinFit, xdata, ydata, f)
print(dump_result(fit_result))
```

which will print:

>Fit performed with type 'LinFit':<br>
> m: 2.151831059405926e+00 (unbounded, initial: 0.000000000000000e+00)<br>
> b: 4.613950265325694e-13 (bounded: [0.000000000000000e+00;inf[, initial: 1.000000000000000e+00)

Notably, as required, $b$ is now positive. You can verify this for
example using Mathematica:


```mathematica
data = {{0, -1}, {1, 2}, {2.1, 5}, {4, 10}, {4, 7}};
NonlinearModelFit[data, {m x + b, b > 0}, {m, b}, x]
```

which will give you a `FittedModel` object containing the fitted
parameters:

> $m = 2.1518301433522606$<br>
> $b = 3.0934405158061573\times10^{-6}$

It seems that $m$ and $b$ differ only due to numerical error from the
values computed above or because a different fitting procedure is used
internally. Importantly, the *same* (up to some error) positive(!) value
for $m$ is recovered.

Additional "special" fields
are:

- `const`: The field is constant and will not partake in the fit.
- `same_as`: The field always takes the value of another field, whose
             name must be specified.
- `regular`: This field behaves like a regular unbounded field.

Note that these special fields do not affect the construction of
instances of the dataclass. For example, similar to the second example
above,

```python
from dataclasses import dataclass
from scipy_dataclassfitparams import bounded


@dataclass
class LinFit:

    m: float

    b: float = bounded(min=0)


LinFit(m=0, b=-100)
```

simply creates the instance `LinFit(m=0, b=-100)` without any exception
raised or similar. The special field definitions will only be used for
the curve fit and no validation is performed on parameters passed to the
dataclass constructor. If necessary, this can be implemented using
external libraries. This is also the reason why the builtin dataclass
wrapper can be used: This package does not provide any more
functionality than the interface between the dataclass and
`scipy.optimize.curve_fit`.


## Installation
The minimal supported version of Python for this package is Python 3.8.

You can install this package directly from git using pip:
```  
pip install git+https://github.com/devds96/scipy-dataclassfitparams
```

Alternatively, you can clone the git repo and run in its root directory:
```shell
pip install .
```


## Future Ideas

I have several ideas for things that may be useful, but for which I
currently do not have the time. If they become necessary, I may
implement this features:

- **Callable fit specifications**: Currently it is required to provide
  a fit function f to `make_fit`. It may be possible to instead make the
  dataclass defining the fit callable by implementing
  `__call__(self, x: NDArray[floating]) -> NDArray[floating]` on the
  dataclass. this function then defines the fit function. For this, the
  f paramter will be optional. This is also why it appears after
  `xdata` and `ydata` in the `make_fit` signature.
- **Array-valued parameters**: Currently, all parameters have to be
  `float`s. It may be possible to allow `NDArray[floating]` parameters
  with arbitrary shape. The result printing mechanism will also have to
  be adapted then in order to gracefully print arrays.
- **Frozen dataclasses**: Currently, the dataclass instances used are
  not frozen. However, setting `frozen=True` on the `@dataclass` wrapper
  does not influence the functionality of this package since the
  instances are constructed using the constructor. It may be worth
  considering to require `frozen=True` to prevent modifications of the
  constructed objects. This would also mean that array parameters as
  mentioned in the previous point would have to be set to read-only.