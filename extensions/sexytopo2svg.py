#!/usr/bin/env python3
"""
Converts SexyTopo drawing files to SVG format.
"""

import argparse
import json
import sys
from math import cos, sin, radians
from pathlib import Path
from lxml import etree

CLARK_SVG_G = "{http://www.w3.org/2000/svg}g"
CLARK_INKSCAPE_LABEL = "{http://www.inkscape.org/namespaces/inkscape}label"
CLARK_INKSCAPE_GROUPMODE = "{http://www.inkscape.org/namespaces/inkscape}groupmode"

SVG_TEMPLATE = """<?xml version="1.0" ?>
<svg xmlns="http://www.w3.org/2000/svg"
   xmlns:sodipodi="http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd"
   xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape"
   xmlns:therion="http://therion.speleo.sk/therion"
   width="21cm" height="29.7cm"
   viewBox="0 0 42 59.4">
<sodipodi:namedview
   inkscape:document-units="cm"
   pagecolor="#ffffff">
  <inkscape:grid type="xygrid" empspacing="10"
     spacingx="1"
     spacingy="1"
     units="cm" />
</sodipodi:namedview>
<defs>
<style type="text/css">
path {
    fill:none;
    stroke-linecap:round;
    stroke-linejoin:round;
}
</style>
</defs>
<g
   inkscape:groupmode="layer"
   inkscape:label="SexyTopo"
   therion:role="none">
</g>
</svg>
"""

STATION_NAME_SPLAY = "-"
EE_DIRECTION_LEFT = "left"
EE_DIRECTION_RIGHT = "right"

SCALE = (1, 200)
SCALE_CM = 100 * SCALE[0] / SCALE[1]
BBOX_PADDING_CM = 1
BBOX_PADDING_PX = BBOX_PADDING_CM / SCALE_CM
STROKE_WIDTH_CM = 0.025
STROKE_WIDTH_PX = STROKE_WIDTH_CM / SCALE_CM


class BBox:
    x_min: float = float("inf")
    x_max: float = float("-inf")
    y_min: float = float("inf")
    y_max: float = float("-inf")

    def is_empty(self) -> bool:
        return self.x_max < self.x_min

    def width(self) -> float:
        return self.x_max - self.x_min

    def height(self) -> float:
        return self.y_max - self.y_min

    def add_point(self, x: float, y: float):
        self.x_min = min(x, self.x_min)
        self.x_max = max(x, self.x_max)
        self.y_min = min(y, self.y_min)
        self.y_max = max(y, self.y_max)


def read_json(path: Path) -> dict:
    with open(path) as handle:
        return json.load(handle)


def write_drawing(parent: etree.Element, data: dict, bbox: BBox):
    for path in data["paths"]:
        color = path["colour"].lower()
        d = "M " + " L ".join(f"{point['x']} {point['y']}" for point in path["points"])
        etree.SubElement(parent, "path", {
            "d": d,
            "style": f"stroke:{color}",
        })

        for point in path["points"]:
            bbox.add_point(point["x"], point["y"])

    for label in data["labels"]:
        color = label["colour"].lower()
        size = label["size"]
        x = label["location"]["x"]
        y = label["location"]["y"]
        elem_text = etree.SubElement(parent, "text", {
            "x": str(x),
            "y": str(y),
            "style": f"font-size:{size};fill:{color}",
        })
        elem_text.text = label["text"]

        bbox.add_point(x, y)


def write_shots(parent: etree.Element, data: dict, bbox: BBox, is_ext: bool):
    name2pos = {}
    d_splays = []
    d_splays_vertical = []
    d_legs = []
    ee_directions = {
        station["name"]: station["eeDirection"]
        for station in data["stations"]
    }
    for station in data["stations"]:
        for leg in station["legs"]:
            if not name2pos:
                pos = name2pos.setdefault(station["name"], (0, 0, 0))
            else:
                pos = name2pos[station["name"]]
            distxy = leg["distance"] * cos(radians(leg["inclination"]))
            distz = leg["distance"] * sin(radians(leg["inclination"]))
            distx = distxy * sin(radians(leg["azimuth"]))
            disty = distxy * cos(radians(leg["azimuth"]))

            if leg["destination"] == STATION_NAME_SPLAY:
                ee_dir = station["eeDirection"]
            else:
                ee_dir = ee_directions[leg["destination"]]

            if not is_ext:
                posdest = (pos[0] + distx, pos[1] - disty, pos[2] + distz)
            elif ee_dir == EE_DIRECTION_RIGHT:
                posdest = (pos[0] + distxy, pos[1] - distz, 0)
            else:
                assert ee_dir == EE_DIRECTION_LEFT
                posdest = (pos[0] - distxy, pos[1] - distz, 0)
            d_frag = f"M {pos[0]} {pos[1]} L {posdest[0]} {posdest[1]}"
            if leg["destination"] != STATION_NAME_SPLAY:
                assert leg["destination"] not in name2pos
                name2pos[leg["destination"]] = posdest
                d_legs.append(d_frag)
            elif abs(distz) < distxy:
                d_splays.append(d_frag)
            else:
                d_splays_vertical.append(d_frag)

            bbox.add_point(pos[0], pos[1])
            bbox.add_point(posdest[0], posdest[1])

    d = " ".join(d_splays_vertical)
    etree.SubElement(
        parent, "path", {
            "d": d,
            "style": f"stroke:#f90;stroke-width:{STROKE_WIDTH_PX/4};stroke-dasharray:0.05 0.1",
            CLARK_INKSCAPE_LABEL: "splays-vertical",
        })
    d = " ".join(d_splays)
    etree.SubElement(
        parent, "path", {
            "d": d,
            "style": f"stroke:#f90;stroke-width:{STROKE_WIDTH_PX/4}",
            CLARK_INKSCAPE_LABEL: "splays",
        })
    d = " ".join(d_legs)
    etree.SubElement(
        parent, "path", {
            "d": d,
            "style": f"stroke:#f00;stroke-width:{STROKE_WIDTH_PX/2}",
            CLARK_INKSCAPE_LABEL: "survey",
        })


def main(args=None):
    argparser = argparse.ArgumentParser(description=__doc__)
    argparser.add_argument(
        "filename",
        type=Path,
        help="Sexytopo plan, ext-elevation, or data file in JSON format")
    options = argparser.parse_args(args)
    filename = options.filename

    assert filename.suffix == ".json"

    is_data = filename.name.endswith(".data.json")
    is_plan = filename.name.endswith(".plan.json")
    is_ext = filename.name.endswith(".ext-elevation.json")

    assert is_data or is_plan or is_ext

    datafilename = filename.with_suffix("").with_suffix(".data.json")

    root = etree.fromstring(SVG_TEMPLATE)

    parent = root.find(CLARK_SVG_G)
    assert parent is not None

    g_drawing = etree.SubElement(parent, "g", {
        CLARK_INKSCAPE_LABEL: "drawing",
        "style": f"stroke-width:{STROKE_WIDTH_PX}",
    })
    g_shots = etree.SubElement(parent, "g", {CLARK_INKSCAPE_LABEL: "shots"})

    bbox = BBox()

    if is_plan or is_ext:
        write_drawing(g_drawing, read_json(filename), bbox)

    if datafilename.is_file():
        write_shots(g_shots, read_json(datafilename), bbox, is_ext)

    if not bbox.is_empty():
        width = bbox.width() + BBOX_PADDING_PX * 2
        height = bbox.height() + BBOX_PADDING_PX * 2
        root.attrib["viewBox"] = (
            f"{bbox.x_min - BBOX_PADDING_PX} {bbox.y_min - BBOX_PADDING_PX} "
            f"{width} {height}")
        root.attrib["width"] = f"{width * SCALE_CM}cm"
        root.attrib["height"] = f"{height * SCALE_CM}cm"

    sys.stdout.buffer.write(etree.tostring(root, encoding="utf-8"))


if __name__ == "__main__":
    main()
