"""Executing this script will run the examples shown in the README.md
file in order to verify their correctness.
"""

import dataclasses
import os.path as ospath
import subprocess
import tempfile
import traceback
import warnings

from contextlib import contextmanager
from dataclasses import dataclass
from hypothesis.errors import NonInteractiveExampleWarning
from subprocess import CompletedProcess
from typing import Iterable, Tuple, Union

try:
    import pydantic as _  # type: ignore # noqa: F401
except ModuleNotFoundError:
    PYDANTIC_UNAVAILABLE = True
else:
    PYDANTIC_UNAVAILABLE = False


README_PATH = ospath.normpath(
    ospath.join(__file__, "..", "..", "README.md")
)
"""The path to the readme file."""


START_MARKER = "```python"
"""The start marker for python code blocks."""


END_MARKER = "```"
"""The end marker for all code blocks."""


@dataclass(frozen=True)
class ExecutionResult:
    """The execution result of an example in the readme."""

    success: bool
    """Whether the execution was successful."""

    exc: Union[Exception, None]
    """The exception that occurred."""

    pydantic_failure: bool
    """Whether the execution actually failed, but because pydantic was
    not available."""

    def print_status(self):
        """Print the message for the execution result to stdout."""
        if self.success:
            if self.pydantic_failure:
                print(
                    "OK (failed because pydantic is not available)."
                )
            else:
                print("Success.")
        else:
            exception = self.exc
            if exception is None:
                print("Failed. No exception provided.")
            else:
                traceback.print_exception(exception)


@dataclass(frozen=True)
class LintResult:

    proc: CompletedProcess
    """The completed flake8 process."""

    file: str
    """The path to the file that was processed."""

    output: str = dataclasses.field(init=False)
    """Stores the output."""

    error: str = dataclasses.field(init=False)
    """Stores the error output."""

    success: bool = dataclasses.field(init=False)
    """Whether there were no (linting) errors"""

    def __post_init__(self) -> None:
        proc = self.proc

        err: Union[str, None] = proc.stderr
        if err is None:
            raise AssertionError
        msg_err = err.strip()
        object.__setattr__(self, "error", msg_err)

        out: Union[str, None] = proc.stdout
        if out is None:
            raise AssertionError
        msg = out.strip().replace(self.file, "<code>")
        object.__setattr__(self, "output", msg)

        proc_ok = proc.returncode == 0
        msg_ok = (len(msg_err) + len(msg)) == 0
        success = proc_ok and msg_ok
        object.__setattr__(self, "success", success)

    def print_status(self):
        """Print the message for the linting result."""
        if self.success:
            print("Everything is ok.")
            return
        out = self.output
        if len(out) > 0:
            print(out)
        err = self.error
        if len(err) > 0:
            print("Found stderr:")
            print(err)


@dataclass(frozen=True)
class CodeBlock:
    """Represents a block of code from the readme."""

    line: int
    """The line on which the code block starts."""

    code: str
    """The code contained in the block."""

    @contextmanager
    def in_tempfile(self):
        """Create a contextmanager for a temporary file containing the
        code of this code block.

        Yields:
            NamedTemporaryFile: The temporary file containing the code.
        """
        # We need to create a temporary directory. On Windows, it is not
        # possible for other processes to read the temporary file while
        # it is still being used. Therefore, using a temporary directory
        # should solve this. (Closing a tempfile without removing it is
        # probably not a good idea.)
        with tempfile.TemporaryDirectory() as tdir:
            filename = ospath.join(tdir, "codefile.py")
            with open(filename, "w") as ofi:
                ofi.write(self.code)
            yield filename

    def run_test(self) -> ExecutionResult:
        """Run the `CodeBlock` and return the execution result.

        Returns:
            ExecutionResult: The execution result.
        """
        print(f"Testing example from line {self.line}...")
        try:
            with warnings.catch_warnings():
                warnings.filterwarnings(
                    "ignore", category=NonInteractiveExampleWarning
                )
                exec(self.code, {})
        except ModuleNotFoundError as mnfe:
            if ("pydantic" in str(mnfe)) and PYDANTIC_UNAVAILABLE:
                return ExecutionResult(True, mnfe, True)
            else:
                return ExecutionResult(False, mnfe, False)
        except Exception as ex:
            return ExecutionResult(False, ex, False)
        return ExecutionResult(True, None, False)

    def run_linter(self) -> LintResult:
        """Apply flake8 to the code block.

        Returns:
            LintResult: The linting result.
        """
        print(f"Running linter on code block from line {self.line}...")
        with self.in_tempfile() as fname:
            f8_proc = subprocess.run(
                ("flake8", fname), text=True, capture_output=True
            )
            return LintResult(f8_proc, fname)

    @classmethod
    def collect_from_readme(cls, readme_path: str) -> Tuple["CodeBlock", ...]:
        """Open the readme file and extract the code blocks.

        Args:
            readme_path (str): The path to the readme.

        Raises:
            FormattingException: If the readme is formatted incorrectly.

        Returns:
            tuple[CodeBlock, ...]: The code blocks extracted from the
                readme file.
        """
        print(f"Collecting code from {str(readme_path)!r}...")

        def find_code_blocks(lines: Iterable[str]):
            recording = False
            start_line = None
            text = ''
            for i, cline in enumerate(lines, start=1):
                if cline.startswith(START_MARKER):
                    if recording:
                        raise FormattingException(
                            f"A second code block started on line {i} "
                            "while reading the code block from line "
                            f"{start_line}."
                        )
                    if (start_line is not None) or (text != ''):
                        raise AssertionError(f"{start_line!r}, {text!r}")
                    recording = True
                    start_line = i
                    continue
                if cline.startswith(END_MARKER):
                    # The end markers are not language specific so we
                    # might not be recording python code when we
                    # encounter one.
                    if not recording:
                        continue
                    if start_line is None:
                        raise AssertionError(f"{start_line!r}")
                    yield cls(start_line, text)
                    recording = False
                    start_line = None
                    text = ''
                    continue
                if recording:
                    text += cline
                    continue
            if recording:
                raise FormattingException(
                    f"The code block starting on line {start_line} was "
                    "never closed."
                )
            if (start_line is not None) or (text != ''):
                raise AssertionError(f"{start_line!r}, {text!r}")

        with open(readme_path) as rmfi:
            return tuple(find_code_blocks(rmfi))


class FormattingException(Exception):
    """And exception that is raised if the readme file is formatted
    incorrectly.
    """
    pass


def main() -> int:
    """The main method.

    Returns:
        int: The exit code.
    """
    code_blocks = CodeBlock.collect_from_readme(README_PATH)
    num_examples = len(code_blocks)
    print(f"Collected {num_examples} examples.")
    print()

    lint_failures = 0
    print("Linting code blocks...")
    for block in code_blocks:
        lres = block.run_linter()
        lres.print_status()
        if not lres.success:
            lint_failures += 1
    if lint_failures > 0:
        print(
            f"Linting completed. There were {lint_failures} examples "
            "with errors."
        )
    else:
        print("Linting successful.")
    print()

    failures = 0
    for block in code_blocks:
        tres = block.run_test()
        tres.print_status()
        if not tres.success:
            failures += 1
    if failures > 0:
        print(f"Found {failures} failed examples.")
    else:
        print("All examples passed.")

    if (lint_failures + failures) > 0:
        return -1

    return 0


if __name__ == "__main__":
    exit(main())
