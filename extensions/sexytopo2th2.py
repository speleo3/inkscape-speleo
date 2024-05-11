#!/usr/bin/env python3
"""
Converts SexyTopo drawing files to TH2 format.
"""

import argparse
import json
import sys
from math import cos, sin, radians
from pathlib import Path

from th2_output import fstr2 as fstr

STATION_NAME_SPLAY = "-"
EE_DIRECTION_LEFT = "left"
EE_DIRECTION_RIGHT = "right"

SCALE = (1, 100)
BBOX_PADDING_PX = 100


def to_th2_space(point: dict | tuple) -> tuple[float, float]:
    """
    Project a point to therions coordinate space
    """
    if isinstance(point, dict):
        x, y = point["x"], point["y"]
    else:
        x, y = point
    return x * SCALE[1], -y * SCALE[1]


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


def write_drawing(parent: list[str], data: dict, bbox: BBox):
    for path in data["paths"]:
        color = path["colour"].lower()

        parent.append(f"line u:{color}")
        for point in path["points"]:
            x, y = to_th2_space(point)
            parent.append(f"  {fstr(x)} {fstr(y)}")
            bbox.add_point(x, y)
        parent.append("endline")

    for label in data["labels"]:
        color = label["colour"].lower()
        # size = label["size"]  # scale???
        x, y = to_th2_space(label["location"])

        text = label["text"].replace('"', "'").replace("\n", "<br>")
        parent.append(f'point {fstr(x)} {fstr(y)} label -text "{text}"')

        bbox.add_point(x, y)


def write_shots(parent: list[str], data: dict, bbox: BBox, is_ext: bool):
    name2pos = {}
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

            if leg["destination"] != STATION_NAME_SPLAY:
                assert leg["destination"] not in name2pos
                name2pos[leg["destination"]] = posdest

            bbox.add_point(*to_th2_space(pos[:2]))
            bbox.add_point(*to_th2_space(posdest[:2]))

    for name, (x, y, _) in name2pos.items():
        x, y = to_th2_space((x, y))
        parent.append(f"point {fstr(x)} {fstr(y)} station -name {name}")


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

    stem = filename.name.rsplit(".", 2)[0]
    projection = 'extended' if is_ext else 'plan'

    bbox = BBox()

    g_drawing = [
        "encoding  utf-8",
        "##XTHERION## xth_me_area_zoom_to 50",
        f"scrap s_{projection}_{stem} -projection {projection}",
    ]
    g_shots = g_drawing

    if is_plan or is_ext:
        write_drawing(g_drawing, read_json(filename), bbox)

    if datafilename.is_file():
        write_shots(g_shots, read_json(datafilename), bbox, is_ext)

    if not bbox.is_empty():
        g_drawing.insert(1, (f"##XTHERION## xth_me_area_adjust"
                             f" {fstr(bbox.x_min - BBOX_PADDING_PX)}"
                             f" {fstr(bbox.y_min - BBOX_PADDING_PX)}"
                             f" {fstr(bbox.x_max + BBOX_PADDING_PX)}"
                             f" {fstr(bbox.y_max + BBOX_PADDING_PX)}"))

    g_drawing += ["endscrap", ""]

    sys.stdout.write("\n".join(g_drawing))


if __name__ == "__main__":
    main()
