"""
SVG -> Therion Metapost

Scale is 1pc SVG = 1u MetaPost
"""

from dataclasses import dataclass
import itertools
import re
from typing import cast, IO, List, Optional, Union, Tuple, Type, TypeVar

import inkex
import inkex.paths as inkpa
import inkex.elements as inkel
from inkex.extensions import OutputExtension

pens = [
    (1.0 / 10, "PenA"),
    (0.7 / 10, "PenB"),
    (0.5 / 10, "PenC"),
    (0.35 / 10, "PenD"),
    (1.2 / 10, "PenX"),
]

T = TypeVar("T")


def cast_assert(typ: Type[T], val) -> T:
    """
    Returns:
      Unchanged val
    Raises:
      AssertionError: If val is not of type typ
    """
    assert isinstance(val, typ)
    return val


def uround(value: float) -> float:
    """
    Round the given user units value to the accepted precision.

    Drops the sign from signed zero.
    """
    return round(value, 4) or 0.0


def approx_equal(a: float, b: float) -> bool:
    '''
    True if a and b are approximately equal in user units
    '''
    return abs(a - b) < 1e-4


def removeprefix(s: str, prefix: str) -> str:
    '''Drop-in for Python 3.10's ...'''
    assert isinstance(s, str)
    return s[len(prefix):] if s.startswith(prefix) else s


def get_pen_for_width(width: float) -> str:
    """
    Get the pen which is closest to the given width.

    Args:
      width: Stroke width in centimeters
    """
    return min(pens, key=lambda pen: abs(pen[0] - width))[1]


def get_label(node: inkel.ShapeElement) -> str:
    """
    Get the label which would be displayed in Inkscape's Object & Layer dialog.
    """
    return node.get("inkscape:label") or node.get("id") or ""


def descrim(transform: inkex.Transform) -> float:
    """
    Descriminant of the given transformation matrix.
    """
    mat = transform.matrix
    det = mat[0][0] * mat[1][1] - mat[0][1] * mat[1][0]
    return abs(det)**0.5


def get_metapost_color_arg(color: str) -> str:
    """
    Get the metapost color command for the given SVG color.
    """
    rgb = inkex.colors.Color(color).to_rgb()
    assert len(rgb) == 3
    if rgb == [0, 0, 0]:
        return ""
    return " withcolor (" + ",".join(f"{round(c / 0xFF, 4)}" for c in rgb) + ")"


@dataclass
class ShapeEtc:
    shape: inkel.ShapeElement
    path: inkpa.Path
    transform: inkex.Transform


class PointBuilder:

    NAMEPREFIX = "p_"

    def __init__(self, mpbuilder: "MetapostBuilder", node: inkel.ShapeElement):
        self.mpbuilder = mpbuilder
        self.shape_U: Optional[inkel.ShapeElement] = None
        self.shapes_etc: List[ShapeEtc] = []
        self.draws: List[str] = []
        self.pen = None
        self.name = removeprefix(get_label(node), self.NAMEPREFIX) or "unnamed"
        self.lname = self.NAMEPREFIX + self.name
        self.center = (0.0, 0.0)

        self.process_shape(node)

        if not self.shapes_etc:
            inkex.errormsg(f"Empty point: {self.name}")
            return

        bbox = self.get_bbox()
        assert bbox

        self.center = bbox.center.x, bbox.center.y

        for etc in self.shapes_etc:
            self.finish_shape(etc)

        out_draws = ';\n    '.join(self.draws)
        out = f"""
def {self.lname}(expr pos,theta,sc,al) =
    U:={self.format_point_abs(bbox.width / 2, bbox.height / 2)};
    T:=identity aligned al rotated theta scaled sc shifted pos;
    {out_draws};
enddef;
if unknown ID_{self.lname}:
  initsymbol("{self.lname}");
fi
"""
        self.mpbuilder.stream.write(out.encode("utf-8"))

    def get_transform_for_node(self, node: inkel.ShapeElement) -> inkex.Transform:
        transform = node.composed_transform()
        transform.add_scale(self.mpbuilder.px_to_u)
        return transform

    def get_path_for_node(self, node: inkel.ShapeElement) -> inkpa.Path:
        return cast(inkpa.Path, node.path).to_absolute()

    def get_bbox(self) -> inkex.BoundingBox:
        if self.shape_U is not None:
            transform = self.get_transform_for_node(self.shape_U)
            path = self.get_path_for_node(self.shape_U).transform(transform)
            return path.bounding_box()
        return sum(
            (etc.path.bounding_box() for etc in self.shapes_etc),  # type: ignore[misc]
            start=inkex.BoundingBox())

    def format_point(self, x: float, y: float) -> str:
        return self.format_point_abs(x - self.center[0], self.center[1] - y)

    def format_point_abs(self, x: float, y: float) -> str:
        x = uround(x)
        y = uround(y)
        return f"({x}u,{y}u)"

    def process_special_shape(self, node: inkel.ShapeElement) -> bool:
        """
        If node is the `U` shape, process it and return true.
        """
        label = get_label(node)
        if label == "U":
            if self.shape_U is not None:
                raise UserWarning(f"more than one U for point {self.name}")
            self.shape_U = node
            return True
        return False

    def process_shape(self, node: inkel.ShapeElement):
        """
        Child-recursive function which builds `shape_U` and `shapes_etc`.
        """
        if self.process_special_shape(node):
            return

        if isinstance(node, inkel.Group):
            for child in node:
                if isinstance(child, inkel.ShapeElement):
                    self.process_shape(child)
        else:
            transform = self.get_transform_for_node(node)
            path = self.get_path_for_node(node).transform(transform)
            self.shapes_etc.append(ShapeEtc(node, path, transform))

    def check_mainpath(self, segments: List[inkpa.AbsolutePathCommand]) -> bool:
        return False

    def finish_mainpath(self, pen: str, draw_args: str):
        raise AssertionError("bug")

    def _get_circle_p(self, etc: ShapeEtc):
        if not isinstance(etc.shape, (inkex.Circle, inkex.Ellipse)) or len(etc.path) < 2:
            return None
        arc = cast_assert(inkpa.Arc, etc.path[1])
        rx, ry = uround(arc.rx), uround(arc.ry)
        rot = uround(arc.x_axis_rotation) % 180
        if rot >= 90:
            rot -= 90
            rx, ry = ry, rx
        buf = ["fullcircle"]
        if rx != ry:
            buf.append(f" xscaled {rx}u yscaled {ry}u")
        else:
            buf.append(f" scaled {rx}u")
        if rot != 0:
            buf.append(f" rotated {rot}")
        center_formatted = self.format_point(*etc.path.bounding_box().center)
        if center_formatted != self.format_point_abs(0, 0):
            buf.append(f" shifted {center_formatted}")
        return buf

    def finish_shape(self, etc: ShapeEtc):
        """
        Build `draws`
        """
        ps: List[List[str]] = []

        segments = list(etc.path.to_superpath().to_segments())

        # circle optimization
        circle_p = self._get_circle_p(etc)
        if circle_p is not None:
            ps.append(circle_p)
            segments = []

        is_mainpath = self.check_mainpath(segments)
        if is_mainpath:
            segments = []

        for seg in segments:
            assert isinstance(seg, inkpa.AbsolutePathCommand)
            if isinstance(seg, inkpa.Move):
                ps.append([self.format_point(seg.x, seg.y)])
                continue
            assert ps
            if isinstance(seg, inkpa.Line):
                ps[-1].append("--" + self.format_point(seg.x, seg.y))
            elif isinstance(seg, inkpa.ZoneClose):
                ps[-1].append("--cycle")
            elif isinstance(seg, inkpa.Curve):
                ps[-1].append("..controls {} and {}..{}".format(
                    self.format_point(seg.x2, seg.y2),
                    self.format_point(seg.x3, seg.y3),
                    self.format_point(seg.x4, seg.y4),
                ))
            else:
                raise TypeError(type(seg))

        style = etc.shape.specified_style()
        stroke = style.get("stroke")
        fill = style.get("fill")
        fill_opacity = float(style.get("fill-opacity") or 1)

        draw_args = ""
        fill_args = ""

        if stroke != "none":
            draw_args += get_metapost_color_arg(stroke)

            scale = descrim(etc.transform)

            stroke_dasharray = style.get("stroke-dasharray")
            if stroke_dasharray and stroke_dasharray[0].isdigit():
                values = [
                    etc.shape.to_dimensionless(v) * scale
                    for v in re.split(r"[\s,]+", stroke_dasharray)
                ]
                pattern = " ".join(
                    f"{onoff} {v}u"
                    for (onoff, v) in zip(itertools.cycle(["on", "off"]), values))
                draw_args += f" dashed dashpattern({pattern})"

            stroke_width = etc.shape.to_dimensionless(
                style.get("stroke-width", "1")) * scale
            pen = get_pen_for_width(stroke_width)
            if is_mainpath:
                self.finish_mainpath(pen, draw_args)
            elif pen != self.pen:
                self.draws.append("pickup " + pen)
                self.pen = pen

        if fill != "none" and fill_opacity > 0:
            fill_args += get_metapost_color_arg(fill)
            if fill_opacity < 1:
                fill_args += f" withalpha {1.0 - fill_opacity}"

        for p in ps:
            if stroke != "none":
                if fill != "none":
                    self.draws.append("p:=" + ''.join(p))
                    self.draws.append("thfill p" + fill_args)
                    self.draws.append("thdraw p" + draw_args)
                else:
                    self.draws.append("thdraw " + ''.join(p) + draw_args)
            elif fill != "none":
                self.draws.append("thfill " + ''.join(p) + fill_args)


class LineBuilder(PointBuilder):

    NAMEPREFIX = "l_"

    def __init__(self, mpbuilder: "MetapostBuilder", node: inkel.ShapeElement):
        self.mpbuilder = mpbuilder
        self.shape_U_in: Optional[inkel.ShapeElement] = None
        self.shape_U_out: Optional[inkel.ShapeElement] = None
        self.shapes_etc: List[ShapeEtc] = []
        self.draws: List[str] = []
        self.draws_main: List[str] = []
        self.pen = None
        self.name = removeprefix(get_label(node), self.NAMEPREFIX) or "unnamed"
        self.lname = self.NAMEPREFIX + self.name
        self.center = (0.0, 0.0)

        self.process_shape(node)

        if not self.shapes_etc:
            inkex.errormsg(f"Empty line: {self.name}")
            return

        self.center, self.width = self.get_center_and_width()

        for etc in self.shapes_etc:
            self.finish_shape(etc)

        out_draws = ';\n    '.join(self.draws)
        out_draws_main = ';\n  '.join(self.draws_main)

        out = f"""
def {self.lname}(expr P) ="""
        if out_draws:
            out += f"""
  myarclen := arclength P;
  if myarclen > 0:
    mystep := adjust_step(myarclen, {self.width}u);
    for mytime=(mystep / 2) step mystep until myarclen:
      t := arctime mytime of P;
      T := identity rotated angle(thdir(P, t)) shifted (point t of P);
      {out_draws};
    endfor;
  fi;"""
        if out_draws_main:
            out += f"""
  T:=identity;
  {out_draws_main};"""
        out += f"""
enddef;
if unknown ID_{self.lname}:
  initsymbol("{self.lname}");
fi
"""

        self.mpbuilder.stream.write(out.encode("utf-8"))

    def get_bbox_for_node(self, node: inkex.ShapeElement) -> inkex.BoundingBox:
        transform = self.get_transform_for_node(node)
        path = self.get_path_for_node(node).transform(transform)
        return path.bounding_box()

    def get_center_and_width(self) -> Tuple[Tuple[float, float], float]:
        if self.shape_U_in is None:
            raise UserWarning("Missing U_in")
        if self.shape_U_out is None:
            raise UserWarning("Missing U_out")

        bbox_in = self.get_bbox_for_node(self.shape_U_in)
        bbox_out = self.get_bbox_for_node(self.shape_U_out)

        def assert_approx_equal(a: float, b: float, msg):
            if not approx_equal(a, b):
                ids = self.shape_U_in.get('id'), self.shape_U_out.get('id')
                raise UserWarning(f"U_in and U_out must be {msg} [{a} != {b}] {ids}")

        assert_approx_equal(bbox_in.left, bbox_out.left, "left-aligned")
        assert_approx_equal(bbox_in.width, bbox_out.width, "same width")
        assert_approx_equal(bbox_in.bottom, bbox_out.top, "aligned bottom to top")

        return (
            uround(bbox_in.center_x),
            uround(bbox_in.bottom),
        ), uround(bbox_in.width)

    def process_special_shape(self, node: inkel.ShapeElement) -> bool:
        label = get_label(node)
        if label == "U_in":
            if self.shape_U_in is not None:
                raise UserWarning(f"more than one U_in for point {self.name}")
            self.shape_U_in = node
            return True
        if label == "U_out":
            if self.shape_U_out is not None:
                raise UserWarning(f"more than one U_out for point {self.name}")
            self.shape_U_out = node
            return True
        return False

    def check_mainpath(self, segments: List[inkpa.AbsolutePathCommand]) -> bool:
        """
        True if the path is the main path, which means it's on the x-axis and
        has self.width length.
        """
        if not (len(segments) == 2 and isinstance(segments[1], inkpa.Line)):
            return False
        assert isinstance(segments[0], inkpa.Move)
        if not approx_equal(segments[0].y, self.center[1]):
            return False
        if not approx_equal(segments[1].y, self.center[1]):
            return False
        if not approx_equal(segments[0].x, self.center[0] - self.width / 2):
            return False
        if not approx_equal(segments[1].x, self.center[0] + self.width / 2):
            return False
        return True

    def finish_mainpath(self, pen: str, draw_args: str):
        """
        Add draws for the main path with given pen and draw arguments.
        """
        self.draws_main.append("pickup " + pen)
        self.draws_main.append(f"thdraw P{draw_args}")


class MetapostBuilder:

    def __init__(self, extension: OutputExtension, stream: IO[bytes]):
        self.stream = stream
        svg = cast(inkel.SvgDocumentElement, extension.svg)
        self.px_to_u: float = 1.0 / svg.viewport_to_unit("1pc", "px")
        self.process_group(svg)

    def process_group(self, group: Union[inkel.Group, inkel.SvgDocumentElement]):
        for node in group:
            if not isinstance(node, inkel.ShapeElement):
                continue
            label = get_label(node)
            if label.startswith("p_"):
                PointBuilder(self, node)
            elif label.startswith("l_"):
                LineBuilder(self, node)
            elif isinstance(node, inkel.Group):
                self.process_group(node)
            else:
                inkex.errormsg(f"Ignored shape: {node}")


class TherionMetapostOutputExtension(OutputExtension):
    def save(self, stream):
        MetapostBuilder(self, stream)


if __name__ == "__main__":
    TherionMetapostOutputExtension().run()
