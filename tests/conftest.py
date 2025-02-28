import os
import sys
import pytest
from pathlib import Path


def _make_coverage_options(inipath: Path) -> "list[str]":
    """
    Make coverage command line options which allow running coverage from a
    different directory.
    """
    from coverage import tomlconfig
    p = tomlconfig.TomlConfigParser(False)
    p.read(inipath)

    root = inipath.parent

    return [
        f"--rcfile={inipath}",
        f"--data-file={root / '.coverage'}",
        "--source=" + ",".join(str(root / v) for v in p.getlist("run", "source")),
        "--omit=" + ",".join(str(root / v) for v in p.getlist("run", "omit")),
    ]


@pytest.fixture(scope="session")
def executable_args(pytestconfig):
    args = [sys.executable]
    if os.getenv("COVERAGE_RUN") == "true":
        args += ["-m", "coverage", "run"]
        # Required for subprocess with changed cwd
        args += _make_coverage_options(pytestconfig.inipath)
    return args
