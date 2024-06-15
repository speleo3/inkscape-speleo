"""
SVG -> Therion Metapost

Scale is 1cm SVG = 1u MetaPost
"""

from dataclasses import dataclass
from typing import cast, IO, List, Optional, Union

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
    return " withcolor (" + ",".join(f"{round(c, 6)}" for c in rgb.to_floats()) + ")"


@dataclass
class ShapeEtc:
    shape: inkel.ShapeElement
    path: inkpa.Path
    transform: inkex.Transform


class PointBuilder:

    def __init__(self, mpbuilder: "MetapostBuilder", node: inkel.ShapeElement):
        self.mpbuilder = mpbuilder
        self.shape_U: Optional[inkel.ShapeElement] = None
        self.shapes_etc: List[ShapeEtc] = []
        self.draws: List[str] = []
        self.pen = None
        self.name = removeprefix(get_label(node), "p_") or "unnamed"
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
def p_{self.name}(expr pos,theta,sc,al) =
    U:={self.format_point_abs(bbox.width / 2, bbox.height / 2)};
    T:=identity aligned al rotated theta scaled sc shifted pos;
    {out_draws};
enddef;
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
        x = round(x, 4)
        y = round(y, 4)
        return f"({x}u,{y}u)"

    def process_shape(self, node: inkel.ShapeElement):
        """
        Child-recursive function which builds `shape_U` and `shapes_etc`.
        """
        label = get_label(node)
        if label == "U":
            if self.shape_U is not None:
                raise UserWarning(f"more than one U for point {self.name}")
            self.shape_U = node
            return

        if isinstance(node, inkel.Group):
            for child in node:
                if isinstance(child, inkel.ShapeElement):
                    self.process_shape(child)
        else:
            transform = self.get_transform_for_node(node)
            path = self.get_path_for_node(node).transform(transform)
            self.shapes_etc.append(ShapeEtc(node, path, transform))

    def finish_shape(self, etc: ShapeEtc):
        """
        Build `draws`
        """
        ps: List[List[str]] = []

        for seg in etc.path.to_superpath().to_segments():
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

            stroke_width = etc.shape.to_dimensionless(
                style.get("stroke-width")) * descrim(etc.transform)
            pen = get_pen_for_width(stroke_width)
            if pen != self.pen:
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


class MetapostBuilder:

    def __init__(self, extension: OutputExtension, stream: IO[bytes]):
        self.stream = stream
        svg = cast(inkel.SvgDocumentElement, extension.svg)
        self.px_to_u: float = 1.0 / svg.viewport_to_unit("1cm", "px")
        self.process_group(svg)

    def process_group(self, group: Union[inkel.Group, inkel.SvgDocumentElement]):
        for node in group:
            if not isinstance(node, inkel.ShapeElement):
                continue
            label = get_label(node)
            if label.startswith("p_"):
                PointBuilder(self, node)
            elif label.startswith("l_"):
                inkex.errormsg("Line not implemented yet")
            elif isinstance(node, inkel.Group):
                self.process_group(node)
            else:
                inkex.errormsg(f"Ignored shape: {node}")


class TherionMetapostOutputExtension(OutputExtension):
    def save(self, stream):
        MetapostBuilder(self, stream)


if __name__ == "__main__":
    TherionMetapostOutputExtension().run()
