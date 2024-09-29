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
if unknown ID_p_stalactite_UIS:
  initsymbol("p_stalactite_UIS");
fi
""" in mpcontent

    # waterflow
    assert " withcolor (0.0,0.0,1.0) dashed dashpattern(on 0.005u off 0.06u);" in mpcontent

    assert """
def l_pit(expr P) =
  myarclen := arclength P;
  if myarclen > 0:
    mystep := adjust_step(myarclen, 0.6u);
    for mytime=(mystep / 2) step mystep until myarclen:
      t := arctime mytime of P;
      T := identity rotated angle(thdir(P, t)) shifted (point t of P);
      thfill (0.0u,0.4u)--(0.2u,0.0u)--(-0.2u,0.0u)--cycle withcolor (1.0,0.0,1.0);
    endfor;
  fi;
  T:=identity;
  pickup PenA;
  thdraw P withcolor (1.0,0.0,1.0);
enddef;
""" in mpcontent
