"""
Merge an "overwrite" file into preferences.xml
"""

import argparse
import lxml.etree as etree
from pathlib import Path
from typing import TypeAlias

Element: TypeAlias = etree._Element


def pxp(elem: Element | None) -> str:
    if elem is None:
        return ""
    p = f"/{elem.tag}"
    if id_ := elem.get("id"):
        p += f'[@id="{id_}"]'
    return pxp(elem.getparent()) + p


def pxp_list(elem: Element | None) -> list[tuple[str, str]]:
    if elem is None:
        return []
    return pxp_list(elem.getparent()) + [(elem.tag, elem.get("id"))]


def get_or_create(source: Element, target_tree: Element) -> Element:
    selector_list = pxp_list(source)
    parent = target_tree.getroot()
    for (tag, id_) in selector_list[1:]:
        assert id_
        item = parent.find(f'{tag}[@id="{id_}"]')
        if item is None:
            item = etree.SubElement(parent, tag)
            item.set("id", id_)
        parent = item
    return parent


def overwrite_preferences(
        path_pref_overwrite: Path = Path("preferences-speleo3.xml"),
        path_pref_backup: Path = Path("preferences.xml.bak"),
        path_pref: Path = Path("preferences.xml"),
) -> None:

    with open(path_pref, "rb") as handle:
        tree = etree.parse(handle)

    with open(path_pref_overwrite, "rb") as handle:
        tree_speleo3 = etree.parse(handle)

    for source in tree_speleo3.xpath("//*[@id]"):
        try:
            target = get_or_create(source, tree)
        except IndexError as ex:
            print("Failed:", pxp(source))
            continue
        for key, value in source.attrib.items():
            target.attrib[key] = value

    buf = etree.tostring(
        tree,
        encoding="utf-8",
        pretty_print=True,
        xml_declaration=True,
    )

    path_pref_backup.write_bytes(path_pref.read_bytes())
    path_pref.write_bytes(buf)


def main():
    argparser = argparse.ArgumentParser(description=__doc__)
    argparser.add_argument(
        "--overwrite",
        metavar="PATH",
        type=Path,
        default=Path("preferences-speleo3.xml"),
        help="File which gets merged into --preferences (default: %(default)s)",
    )
    argparser.add_argument(
        "--preferences",
        metavar="PATH",
        type=Path,
        default=Path("preferences.xml"),
        help="File to update (default: %(default)s)",
    )
    argparser.add_argument(
        "--backup",
        metavar="PATH",
        type=Path,
        default=Path("preferences.xml.bak"),
        help="Backup file to write (default: %(default)s)",
    )
    options = argparser.parse_args()

    overwrite_preferences(
        path_pref_overwrite=options.overwrite,
        path_pref_backup=options.backup,
        path_pref=options.preferences,
    )


if __name__ == '__main__':
    main()
