import therion_mp_output as m
import subprocess
import sys
from pathlib import Path

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"


def test_therion_mp_output(tmp_path):
    path_input = TEMPLATES_DIR / "therion_mp.svg"
    mpcontent = subprocess.check_output(
        [sys.executable, m.__file__, str(path_input)], encoding="utf-8")

    assert """
def p_u_smiley(expr pos,theta,sc,al) =
    U:=(0.4u,0.4u);
    T:=identity aligned al rotated theta scaled sc shifted pos;
    pickup PenC;
""" in mpcontent

    assert """
def p_stalactite_UIS(expr pos,theta,sc,al) =
    U:=(0.15u,0.4u);
    T:=identity aligned al rotated theta scaled sc shifted pos;
    pickup PenC;
    thdraw (0.0u,-0.4u)--(0.0u,0.15u)--(-0.15u,0.4u);
    thdraw (0.0u,0.15u)--(0.15u,0.4u);
enddef;
""" in mpcontent
