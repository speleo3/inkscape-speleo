import therion_mp_output as m
import subprocess
import math
from pathlib import Path

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"


def test_uround():
    assert math.copysign(1, m.uround(-0.1)) == -1
    assert math.copysign(1, m.uround(-0.0)) == 1  # drop sign
    assert math.copysign(1, m.uround(0.0)) == 1
    assert math.copysign(1, m.uround(0.1)) == 1


def test_get_metapost_color_arg():
    assert m.get_metapost_color_arg("blue") == " withcolor (0.0,0.0,1.0)"
    assert m.get_metapost_color_arg("#00cc00") == " withcolor (0.0,0.8,0.0)"


def test_therion_mp_output(tmp_path, executable_args):
    path_input = TEMPLATES_DIR / "therion_mp.svg"
    mpcontent = subprocess.check_output(
        executable_args + [m.__file__, str(path_input)], encoding="utf-8")

    assert """
def p_u_smiley(expr pos,theta,sc,al) =
    U:=(0.4u,0.4u);
    T:=identity aligned al rotated theta scaled sc shifted pos;
    pickup pencircle scaled 0.05u;
    p:=fullcircle scaled 0.4u;
    thfill p withcolor (1.0,1.0,0.0);
    thdraw p withcolor (0.0,0.502,0.0);
    thdraw (0.2u,-0.1u)..controls (0.18u,-0.2u) and (0.1u,-0.25u)..(0.0u,-0.25u)..controls (-0.1u,-0.25u) and (-0.18u,-0.2u)..(-0.2u,-0.1u) withcolor (0.0,0.502,0.0);
    thdraw fullcircle xscaled 0.03u yscaled 0.05u shifted (0.15u,0.15u) withcolor (0.0,0.502,0.0);
    thdraw fullcircle xscaled 0.03u yscaled 0.05u shifted (-0.15u,0.15u) withcolor (0.0,0.502,0.0);
enddef;
""" in mpcontent

    assert """
def p_stalactite_UIS(expr pos,theta,sc,al) =
    U:=(0.15u,0.4u);
    T:=identity aligned al rotated theta scaled sc shifted pos;
    pickup pencircle scaled 0.05u;
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
  pickup pencircle scaled 0.1u;
  thdraw P withcolor (1.0,0.0,1.0);
enddef;
""" in mpcontent

    assert """
def l_rockborder_FANCY(expr P) =
  T:=identity;
  thfill P withcolor (0.0,0.502,0.502);
enddef;
""" in mpcontent

    assert """
def l_rockedge_FANCY(expr P) =
  T:=identity;
  pickup pencircle scaled 0.2u;
  thdraw P withcolor (0.0,0.0,1.0);
enddef;
""" in mpcontent
