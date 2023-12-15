#!/usr/bin/env python3
"""
Create a dummy Python package and install it with pip.
"""

import sys
import subprocess
import tempfile
from pathlib import Path

name, version = sys.argv[1:]

pyprojectbody = f"""[project]
name = "{name}"
version = "{version}"
"""

with tempfile.TemporaryDirectory() as tmpdirname:
    assert isinstance(tmpdirname, str)
    pyprojectpath = Path(tmpdirname) / "pyproject.toml"
    pyprojectpath.write_text(pyprojectbody)
    subprocess.check_call([sys.executable, "-m", "pip", "install", tmpdirname])
