#!/usr/bin/env python3
"""Build the editable Meridian Freight deck with the Google Slides skill helper.

The manifest makes reruns update the same presentation. No sharing permissions
are created. Google authentication and API transport remain in gslides_builder.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "deck" / "presentation.json"
TEMPLATE = "12HWqnLB_0X49H9GsqjvC4lwQrH9CBZK92hsf8Hj6PhU"
HOST = "https://fevm-fedex-fevm.cloud.databricks.com"
APP = "https://dock-ops-app-7474658947307895.aws.databricksapps.com"
GENIE = f"{HOST}/genie/rooms/01f1a3243b00149fa4876211f8b5c004"
TEAL = "#1B3037"
BLUE = "#1B5161"
MUTED = "#618793"
RED = "#FF3620"
WHITE = "#FFFFFF"
PALE = "#F2F7F8"
GRAY = "#DCE5E8"


def rgb(value: str) -> dict[str, float]:
    """Convert a hex color to the Slides RGB representation."""
    return {key: int(value[index:index + 2], 16) / 255
            for key, index in (("red", 1), ("green", 3), ("blue", 5))}


class Slide:
    """Collect native, editable Google Slides requests for one slide."""

    def __init__(self, page_id: str, number: int, dark: bool = False) -> None:
        self.page_id = page_id
        self.number = number
        self.dark = dark
        self.counter = 0
        self.requests: list[dict[str, Any]] = [
            {"createSlide": {"objectId": page_id,
                             "slideLayoutReference": {"predefinedLayout": "BLANK"}}},
            {"updatePageProperties": {
                "objectId": page_id,
                "pageProperties": {"pageBackgroundFill": {
                    "solidFill": {"color": {"rgbColor": rgb(TEAL if dark else WHITE)}}}},
                "fields": "pageBackgroundFill"}},
        ]
        # The 2026 blank layout includes an opaque white rectangle above the
        # page background. A slide-owned background keeps dark covers readable.
        if dark:
            self.box(0, 0, 959.7, 540, TEAL)

    def box(self, x: float, y: float, width: float, height: float,
            fill: str | None = None) -> str:
        """Add a rectangle or transparent text container in points."""
        self.counter += 1
        object_id = f"{self.page_id}_e{self.counter:03d}"
        self.requests.append({"createShape": {
            "objectId": object_id, "shapeType": "RECTANGLE" if fill else "TEXT_BOX",
            "elementProperties": {"pageObjectId": self.page_id,
                                  "size": {"width": {"magnitude": width, "unit": "PT"},
                                           "height": {"magnitude": height, "unit": "PT"}},
                                  "transform": {"scaleX": 1, "scaleY": 1,
                                                "translateX": x, "translateY": y, "unit": "PT"}}}})
        properties: dict[str, Any] = {"outline": {"propertyState": "NOT_RENDERED"},
                                      "contentAlignment": "TOP"}
        if fill:
            properties["shapeBackgroundFill"] = {"solidFill": {"color": {"rgbColor": rgb(fill)}}}
        self.requests.append({"updateShapeProperties": {
            "objectId": object_id, "shapeProperties": properties,
            "fields": ",".join(properties)}})
        return object_id

    def text(self, value: str, x: float, y: float, width: float, height: float,
             size: float = 20, color: str | None = None, bold: bool = False,
             align: str = "START", link: str | None = None) -> str:
        """Add text with explicit base styling over the entire stored range."""
        object_id = self.box(x, y, width, height)
        style: dict[str, Any] = {
            "fontFamily": "Barlow", "fontSize": {"magnitude": size, "unit": "PT"},
            "bold": bold, "foregroundColor": {"opaqueColor": {
                "rgbColor": rgb(color or (WHITE if self.dark else TEAL))}}}
        if link:
            style["link"] = {"url": link}
        self.requests.extend([
            {"insertText": {"objectId": object_id, "text": value, "insertionIndex": 0}},
            {"updateTextStyle": {"objectId": object_id, "textRange": {"type": "ALL"},
                                 "style": style, "fields": ",".join(style)}},
            {"updateParagraphStyle": {"objectId": object_id, "textRange": {"type": "ALL"},
                                      "style": {"alignment": align, "lineSpacing": 110,
                                                "spaceAbove": {"magnitude": 0, "unit": "PT"},
                                                "spaceBelow": {"magnitude": 0, "unit": "PT"}},
                                      "fields": "alignment,lineSpacing,spaceAbove,spaceBelow"}},
        ])
        return object_id

    def title(self, value: str) -> None:
        """Add a consistently positioned slide title."""
        self.text(value, 44, 32, 875, 72, 32, bold=True)

    def footer(self, caption: str = "Fictional company. Synthetic data.") -> None:
        """Add the visible data disclosure and slide number."""
        self.text(caption, 44, 506, 820, 21, 10,
                  "#9EB7BE" if self.dark else MUTED)
        self.text(str(self.number), 882, 506, 32, 21, 10,
                  "#9EB7BE" if self.dark else MUTED, align="END")

    def table(self, rows: list[list[str]], x: float = 44, y: float = 145,
              width: float = 870, height: float = 240, font: float = 18) -> None:
        """Create a native table with readable header and body formatting."""
        self.counter += 1
        table_id = f"{self.page_id}_table{self.counter}"
        self.requests.append({"createTable": {
            "objectId": table_id, "rows": len(rows), "columns": len(rows[0]),
            "elementProperties": {"pageObjectId": self.page_id,
                                  "size": {"width": {"magnitude": width, "unit": "PT"},
                                           "height": {"magnitude": height, "unit": "PT"}},
                                  "transform": {"scaleX": 1, "scaleY": 1,
                                                "translateX": x, "translateY": y, "unit": "PT"}}}})
        for row_index, row in enumerate(rows):
            for col_index, value in enumerate(row):
                cell = {"rowIndex": row_index, "columnIndex": col_index}
                self.requests.extend([
                    {"insertText": {"objectId": table_id, "cellLocation": cell,
                                    "text": value, "insertionIndex": 0}},
                    {"updateTextStyle": {"objectId": table_id, "cellLocation": cell,
                                         "textRange": {"type": "ALL"},
                                         "style": {"fontFamily": "Barlow", "fontSize": {
                                             "magnitude": font, "unit": "PT"}, "bold": row_index == 0,
                                             "foregroundColor": {"opaqueColor": {"rgbColor": rgb(
                                                 WHITE if row_index == 0 else TEAL)}}},
                                         "fields": "fontFamily,fontSize,bold,foregroundColor"}},
                    {"updateTableCellProperties": {
                        "objectId": table_id,
                        "tableRange": {"location": cell, "rowSpan": 1, "columnSpan": 1},
                        "tableCellProperties": {"contentAlignment": "MIDDLE",
                                                "tableCellBackgroundFill": {"solidFill": {
                                                    "color": {"rgbColor": rgb(BLUE if row_index == 0
                                                                             else PALE if row_index % 2 else WHITE)}}}},
                        "fields": "contentAlignment,tableCellBackgroundFill"}},
                ])

    def node(self, title: str, detail: str, x: float, y: float, width: float = 180,
             height: float = 110) -> None:
        """Add one architecture component with an editable label."""
        self.box(x, y, width, height, PALE)
        self.text(title, x + 12, y + 10, width - 24, 30, 18, BLUE, True)
        self.text(detail, x + 12, y + 44, width - 24, height - 44, 15)

    def line(self, x1: float, y1: float, x2: float, y2: float, arrow: bool = True) -> None:
        """Add a native connector between architecture components."""
        self.counter += 1
        object_id = f"{self.page_id}_line{self.counter}"
        reverse = x2 < x1 or y2 < y1
        self.requests.extend([
            {"createLine": {"objectId": object_id, "lineCategory": "STRAIGHT",
                            "elementProperties": {"pageObjectId": self.page_id,
                                "size": {"width": {"magnitude": max(abs(x2 - x1), 0.1), "unit": "PT"},
                                         "height": {"magnitude": max(abs(y2 - y1), 0.1), "unit": "PT"}},
                                "transform": {"scaleX": 1, "scaleY": 1,
                                              "translateX": min(x1, x2),
                                              "translateY": min(y1, y2), "unit": "PT"}}}},
            {"updateLineProperties": {"objectId": object_id,
                                      "lineProperties": {"lineFill": {"solidFill": {
                                          "color": {"rgbColor": rgb(MUTED)}}},
                                          "weight": {"magnitude": 1.5, "unit": "PT"},
                                          "startArrow": "FILL_ARROW" if arrow and reverse else "NONE",
                                          "endArrow": "FILL_ARROW" if arrow and not reverse else "NONE"},
                                      "fields": "lineFill,weight,startArrow,endArrow"}},
        ])



def main() -> None:
    """Rebuild the current customer narrative in the existing Google Slides deck."""
    import sys
    from revise_meridian_deck import main as build_narrative

    if "--publish" not in sys.argv:
        sys.argv.append("--publish")
    build_narrative()


if __name__ == "__main__":
    main()
