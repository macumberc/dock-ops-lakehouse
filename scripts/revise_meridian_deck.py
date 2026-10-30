#!/usr/bin/env python3
"""Rebuild the native Meridian presentation around the customer decision.

Author and inspect a private draft before applying the same editable objects to
the existing Google Slides URL. Local assets stay private in Drive. No sharing
permissions are created, and the original live presentation is backed up locally.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any

from build_google_slides import Slide, rgb

ROOT = Path(__file__).resolve().parents[1]
DECK = ROOT / "deck"
LIVE_ID = "1aHc3m1N-RoiVbmZy3XPoPNjJ76ItUt88AKvzdas3T2c"
APP_URL = "https://dock-ops-app-7474658947307895.aws.databricksapps.com"
GENIE_URL = "https://fevm-fedex-fevm.cloud.databricks.com/genie/rooms/01f1a3243b00149fa4876211f8b5c004"
NOTEBOOK_URL = "https://fevm-fedex-fevm.cloud.databricks.com/#notebook/3195548178609337"
RUN_URL = "https://fevm-fedex-fevm.cloud.databricks.com/?o=7474658947307895#job/135215719684712/run/215469768958398"
INK, ORANGE, TEAL = "#142E36", "#FF3620", "#1B6374"
PAPER, WHITE, MUTED, LINE = "#FBFAF7", "#FFFFFF", "#536F77", "#D5DFDF"
LIGHT_TEXT = "#B4C8CA"
LOGOS = Path.home() / "Documents" / "logos"
ASSET_PATHS = {
    "cover": DECK / "assets" / "cover-dock.jpg",
    "app": DECK / "assets" / "operations-focus.png",
    "brand": LOGOS / "primary-lockup-full-color-rgb-713x113-4ac2f20.png",
    "lakeflow": LOGOS / "lakeflow-spark-declarative-pipelines-icon-full-color.png",
    "lakebase": LOGOS / "lakebase-icon-full-color-512x512-ab842cd.png",
    "uc": LOGOS / "unity-catalog-icon-full-color-512x512-ab842cd.png",
    "genie": LOGOS / "genie-icon-full-color-512x512-ab842cd.png",
}
SPECS = [
    {"id": "meridian_01", "layout": "cover", "title": "Dock staffing before the rush", "minutes": 0.5},
    {"id": "meridian_02", "layout": "customer", "title": "The loading dock sets the pace", "minutes": 1.5},
    {"id": "meridian_03", "layout": "mismatch", "title": "The rush arrives. The roster stays flat", "minutes": 1.5},
    {"id": "meridian_04", "layout": "cost", "title": "The mismatch creates a measurable cost", "minutes": 1},
    {"id": "meridian_05", "layout": "change", "title": "A different start to the next shift", "minutes": 1},
    {"id": "meridian_06", "layout": "demo", "title": "One operating view for all 36 doors", "minutes": 4},
    {"id": "meridian_07", "layout": "decision", "title": "A recommendation the supervisor can act on", "minutes": 3},
    {"id": "meridian_08", "layout": "architecture", "title": "The data journey behind that decision", "minutes": 1.5},
    {"id": "meridian_09", "layout": "scorecard", "title": "Prototype evidence and pilot success measures", "minutes": 1},
    {"id": "meridian_10", "layout": "pilot", "title": "A 30-day pilot with owners and decision gates", "minutes": 1.5},
    {"id": "meridian_11", "layout": "economics", "title": "The Memphis business case", "minutes": 1},
    {"id": "meridian_12", "layout": "ask", "title": "Decision today: a Memphis pilot", "minutes": 1.5},
    {"id": "meridian_13", "layout": "technical", "title": "Appendix: technical evidence and limits", "minutes": 0},
    {"id": "meridian_14", "layout": "presenter", "title": "Appendix: presenter navigation", "minutes": 0},
]


class NarrativeSlide(Slide):
    """Use restrained native layouts with editable data and sourced images."""

    def __init__(self, entry: dict[str, Any], number: int, assets: dict[str, str]) -> None:
        super().__init__(entry["id"], number, False)
        self.dark = entry["layout"] in {"cover", "decision", "ask"}
        self.requests[1]["updatePageProperties"]["pageProperties"]["pageBackgroundFill"]["solidFill"]["color"]["rgbColor"] = rgb(INK if self.dark else PAPER)
        self.assets = assets

    def image(self, asset: str, x: float, y: float, width: float, height: float) -> None:
        """Insert an original raster asset at its intended aspect ratio."""
        self.counter += 1
        self.requests.append({"createImage": {
            "objectId": f"{self.page_id}_image_{self.counter}", "url": self.assets[asset],
            "elementProperties": {"pageObjectId": self.page_id,
                "size": {"width": {"magnitude": width, "unit": "PT"},
                         "height": {"magnitude": height, "unit": "PT"}},
                "transform": {"scaleX": 1, "scaleY": 1, "translateX": x, "translateY": y, "unit": "PT"}}}})

    def heading(self, value: str, size: int = 36) -> None:
        """Place a short, readable subject or takeaway above the evidence."""
        self.text(value, 48, 38, 864, 72, size, bold=True)

    def footer(self, caption: str = "Fictional carrier. Synthetic demonstration.") -> None:
        """Keep the simulation disclosure visible without competing with content."""
        self.text(caption, 48, 506, 420 if self.dark else 710, 23, 10, LIGHT_TEXT if self.dark else MUTED)
        if not self.dark:
            self.image("brand", 795, 507, 112, 17.75)

    def rule(self, x: float, y: float, width: float) -> None:
        """Add a neutral alignment rule for an evidence table."""
        self.line(x, y, x + width, y, False)

    def grid(self, rows: list[list[str]], widths: list[float], y: float,
             row_height: float, font: int = 19, x: float = 48) -> None:
        """Create a flat native table with editable cells and light row rules."""
        self.counter += 1
        tid = f"{self.page_id}_native_table_{self.counter}"
        self.requests.append({"createTable": {
            "objectId": tid, "rows": len(rows), "columns": len(widths),
            "elementProperties": {"pageObjectId": self.page_id,
                "size": {"width": {"magnitude": sum(widths), "unit": "PT"},
                         "height": {"magnitude": len(rows) * row_height, "unit": "PT"}},
                "transform": {"scaleX": 1, "scaleY": 1, "translateX": x, "translateY": y, "unit": "PT"}}}})
        for col, width in enumerate(widths):
            self.requests.append({"updateTableColumnProperties": {
                "objectId": tid, "columnIndices": [col],
                "tableColumnProperties": {"columnWidth": {"magnitude": width, "unit": "PT"}},
                "fields": "columnWidth"}})
        for i, row in enumerate(rows):
            for j, value in enumerate(row):
                cell = {"rowIndex": i, "columnIndex": j}
                color = WHITE if self.dark else INK
                if i == 0:
                    color = LIGHT_TEXT if self.dark else TEAL
                self.requests.extend([
                    {"insertText": {"objectId": tid, "cellLocation": cell, "text": value, "insertionIndex": 0}},
                    {"updateTextStyle": {"objectId": tid, "cellLocation": cell,
                        "textRange": {"type": "ALL"}, "style": {"fontFamily": "Barlow",
                        "fontSize": {"magnitude": font - 2 if i == 0 else font, "unit": "PT"},
                        "bold": i == 0, "foregroundColor": {"opaqueColor": {"rgbColor": rgb(color)}}},
                        "fields": "fontFamily,fontSize,bold,foregroundColor"}},
                    {"updateTableCellProperties": {"objectId": tid,
                        "tableRange": {"location": cell, "rowSpan": 1, "columnSpan": 1},
                        "tableCellProperties": {"contentAlignment": "MIDDLE", "tableCellBackgroundFill": {
                            "solidFill": {"color": {"rgbColor": rgb(INK if self.dark else PAPER)}}}},
                        "fields": "contentAlignment,tableCellBackgroundFill"}},
                    {"updateTableBorderProperties": {"objectId": tid,
                        "tableRange": {"location": cell, "rowSpan": 1, "columnSpan": 1},
                        "borderPosition": "ALL", "tableBorderProperties": {"dashStyle": "SOLID",
                            "weight": {"magnitude": 0.5, "unit": "PT"},
                            "tableBorderFill": {"solidFill": {"color": {"rgbColor": rgb("#355059" if self.dark else LINE)}}}},
                        "fields": "dashStyle,weight,tableBorderFill"}},
                ])


def notes(time: str, lead: str, show: str, land: str, bridge: str, source: str,
          discussion: str = "") -> str:
    """Write slide-specific presenter cues with a reason for the next slide."""
    return (f"TIME: {time}\n\nLEAD WITH\n{lead}\n\nSHOW\n{show}\n\nLAND THE POINT\n{land}"
            f"\n\nTRANSITION\n{bridge}\n\nOPTIONAL DISCUSSION\n{discussion or 'Take the question at the audience\'s level, then return to the operational decision.'}"
            f"\n\nSOURCES\n{source}\n")


def compose(entry: dict[str, Any], number: int, assets: dict[str, str]) -> tuple[NarrativeSlide, str]:
    """Build one narrative beat and its supporting presenter notes."""
    s = NarrativeSlide(entry, number, assets)
    kind = entry["layout"]
    if kind != "economics":
        s.footer()
    if kind == "cover":
        s.image("cover", 485, 0, 474.7, 540)
        s.text("MERIDIAN FREIGHT", 48, 58, 414, 36, 19, LIGHT_TEXT, True)
        s.text("Dock staffing\nbefore the rush", 48, 150, 435, 160, 55, WHITE, True)
        s.text("Dock visibility and labor planning\nA 30-day Memphis pilot", 48, 349, 418, 92, 23, WHITE)
        n = notes("30 seconds", "Meridian Freight is a fictional LTL carrier. Today we will follow one decision: how a terminal manager prepares the dock shift before trailer queues and overtime build up.",
                  "Introduce the VP of Terminal Operations as the economic sponsor and the Data/Platform Architect as the owner of trusted, usable data. The proposed outcome is a scoped Memphis pilot, with owners and measurable gates.",
                  "The story starts with the operator's problem, then tests a specific staffing decision in the working demo.",
                  "First, where does a loading-dock decision fit in this carrier's operation?",
                  "DEMO.md; src/dock_ops/config.py. Cover photograph: Pexels, https://www.pexels.com/photo/warehouse-with-delivery-truck-exiting-the-loading-dock-29786116/ (illustrative stock photograph, not Meridian or Federal Express).")
    elif kind == "customer":
        s.heading(entry["title"])
        s.text("Meridian Freight transfers loads between trailers\nacross three cross-dock terminals.", 48, 135, 545, 85, 25)
        s.text("A trailer needs an available door and a crew.\nWhen either falls behind, the next load waits.", 48, 240, 545, 86, 24, MUTED)
        s.text("36", 651, 125, 250, 110, 80, ORANGE, True)
        s.text("loading doors", 654, 241, 245, 42, 27, INK, True)
        for y, city, doors in [(312, "Atlanta", "12"), (360, "Dallas", "10"), (408, "Memphis", "14")]:
            s.text(city, 653, y, 168, 38, 23, INK, city == "Memphis")
            s.text(doors, 838, y, 60, 38, 23, ORANGE if city == "Memphis" else MUTED, True, align="END")
        s.text("The manager's decision", 48, 371, 550, 36, 20, TEAL, True)
        s.text("Which doors and workers need attention\nbefore the next arrival wave?", 48, 410, 550, 72, 26, INK, True)
        n = notes("1.5 minutes", "This is a less-than-truckload operation: freight moves through the terminal and changes trailers. The dock connects the arrival schedule to the outbound departure.",
                  "Orient the room to Atlanta, Dallas, and Memphis, totaling 36 doors. The terminal manager must align workers with door activity. The VP cares about trailer waiting and labor cost. The architect must provide reliable data to both.",
                  "A useful solution must improve a shift decision, not merely collect another camera feed or report.",
                  "The problem is that the arrival wave changes while the roster barely does.", "src/dock_ops/config.py; DEMO.md. Operational framing describes the fictional scenario, not a real carrier assessment.")
    elif kind == "mismatch":
        s.heading(entry["title"])
        s.text("Average workers per terminal, selected hours", 48, 120, 650, 32, 18, MUTED)
        values = [("02", 3.3, 1.8), ("06", 7, 4.1), ("08", 7, 7.1), ("10", 7, 9.4),
                  ("11", 7, 10.1), ("12", 7, 9.3), ("20", 7, 8.2)]
        s.text("Scheduled", 48, 162, 170, 30, 18, TEAL, True)
        s.text("Needed from actual workload", 237, 162, 380, 30, 18, ORANGE, True)
        for i, (hour, scheduled, needed) in enumerate(values):
            x = 58 + i * 78
            for offset, value, color in [(0, scheduled, TEAL), (27, needed, ORANGE)]:
                s.box(x + offset, 425 - value * 19.5, 23, value * 19.5, color)
            s.text(f"{needed:.1f}", x + 17, 392 - needed * 19.5, 53, 28, 15, ORANGE, True, align="CENTER")
            s.text(hour + ":00", x - 5, 434, 67, 31, 17, align="CENTER")
        s.text("11:00", 677, 179, 230, 55, 36, INK, True)
        s.text("10.1", 673, 241, 241, 96, 68, ORANGE, True)
        s.text("workers needed", 678, 339, 230, 40, 25)
        s.text("7.0 scheduled\n3.1 worker gap", 678, 391, 230, 77, 24, TEAL)
        n = notes("1.5 minutes", "The schedule is nearly flat during the day. The workload has a pronounced peak. That mismatch is visible before we discuss any AI.",
                  "Read the chart at 06:00 and 11:00. At 11:00, actual-workload staffing averages 10.1 workers per terminal against 7.0 scheduled, a 3.1-worker gap. These are historical network averages, not Memphis forecast rows.",
                  "This is a timing opportunity. It suggests reallocating labor across hours, subject to skills, breaks, and labor constraints.",
                  "Now connect the missed hours to the cost line the VP owns.", "evidence/2026-10-15-data-reconciliation.md. Selected-hour chart after the arrival-hour correction. Model forecasts appear separately on slide 7.")
    elif kind == "cost":
        s.heading(entry["title"])
        s.text("$344,720", 48, 124, 570, 104, 72, ORANGE, True)
        s.text("combined cost across 31 synthetic days", 53, 231, 560, 42, 23)
        s.text("Detention", 48, 292, 165, 30, 17, ORANGE, True)
        s.text("Modeled overtime", 210, 292, 230, 30, 17, TEAL, True)
        max_cost = 135623.63
        for y, city, detention, overtime in [(344, "Memphis", 91649.63, 43974), (393, "Atlanta", 75277.09, 36498), (442, "Dallas", 69013.47, 28308)]:
            s.text(city, 48, y - 4, 110, 33, 21, bold=city == "Memphis")
            d_width, o_width = detention / max_cost * 348, overtime / max_cost * 348
            s.box(166, y, d_width, 22, ORANGE)
            s.box(166 + d_width, y, o_width, 22, TEAL)
            s.text(f"${detention + overtime:,.0f}", 529, y - 5, 132, 37, 22, bold=True)
        s.text("Why Memphis first", 699, 146, 215, 67, 28, INK, True)
        s.text("$91,650", 695, 239, 220, 65, 42, ORANGE, True)
        s.text("highest detention cost", 699, 305, 216, 65, 23)
        s.text("Start with one terminal.\nMeasure before scaling.", 699, 396, 217, 70, 20, MUTED)
        n = notes("1 minute", "The synthetic baseline is $235,940.19 in detention plus $108,780 in modeled overtime. Together that is $344,720.19 across 31 days.",
                  "Compare the stacked terminal bars. Memphis combines $91,649.63 in detention and $43,974 in modeled overtime, or $135,623.63. It has the largest detention cost and becomes the pilot candidate.",
                  "The network annualized cost is about $4.06 million. This is cost exposure in a synthetic scenario; it is not realized savings or a Federal Express financial result.",
                  "So what should change in the manager's next shift?", "evidence/2026-10-15-data-reconciliation.md; evidence/workspace-demo-current.json. Economics assume a two-hour free window and $75 per trailer-hour beyond it.")
    elif kind == "change":
        s.heading(entry["title"])
        s.text("Current pattern", 48, 139, 375, 42, 24, MUTED, True)
        s.text("Proposed operating routine", 501, 139, 412, 42, 24, TEAL, True)
        rows = [(211, "Review yesterday's report", "Check the latest dock snapshot"),
                (292, "Carry forward the fixed roster", "Review the dated staffing gaps"),
                (373, "Add overtime after queues grow", "Approve staffing before the rush")]
        for y, before, after in rows:
            s.text(before, 48, y, 375, 60, 25, MUTED)
            s.text(after, 501, y, 412, 60, 25, INK, True)
            s.rule(48, y + 67, 865)
        s.text("The supervisor approves the change and records the result.", 48, 463, 865, 38, 22, TEAL)
        n = notes("1 minute", "The proposed workflow changes when and how the manager makes a staffing decision.",
                  "Walk one row at a time. A dock snapshot gives an observation time and door state. A dated forecast identifies the gap. A concise briefing supports the supervisor, who still checks worker availability, skills, and shift rules.",
                  "The prototype is decision support. It does not autonomously dispatch labor or integrate with an HR scheduler.",
                  "Let's follow that routine in the working console.", "app/app.py; app/static/index.html; notebooks/00_demo_walkthrough.py. The current and proposed routines are scenario framing, not a measured customer before/after study.")
    elif kind == "demo":
        s.heading(entry["title"])
        s.image("app", 48, 134, 864, 341)
        s.text("Open the live console", 48, 477, 345, 33, 20, TEAL, True, link=APP_URL)
        s.text("Follow the Memphis staffing gap", 507, 477, 404, 33, 20, MUTED, align="END")
        n = notes("4 minutes including the live app", "The terminal manager should be able to answer: what is the dock state, and which shift needs attention? I will show both in one operating view.",
                  f"Open {APP_URL}. Confirm the visible synthetic snapshot timestamp. Inspect all 36 doors, then point to the top Memphis staffing rows. The board and staffing plan report Lakebase as their source. Show the historical KPI period and the hour-of-day profile without reading every tile. Use the slide screenshot only as a labeled fallback.",
                  "The manager can move from a network view to a particular terminal-hour. The screenshot shows a verified October 15 app session, with July–September synthetic data; it is not a live customer feed.",
                  "The next screen makes the proposed staffing action explicit.", "deck/assets/operations-focus.png, cropped from scratch/deployed-app-verified.png; evidence/2026-10-15-app-current.json; app/app.py.",
                  "If the app reports a warehouse fallback, state that source. Lakebase provides fast reads of the copied snapshot; a production implementation still needs a freshness SLA and ongoing synchronization.")
    elif kind == "decision":
        s.heading(entry["title"], 34)
        s.text("MEMPHIS   3 SEP 2026   10:00 UTC", 48, 144, 865, 36, 20, LIGHT_TEXT, True)
        s.text("+9", 48, 207, 310, 152, 108, "#FF715E", True)
        s.text("additional workers", 55, 374, 337, 48, 29, WHITE, True)
        s.text("17 required\n8 scheduled", 458, 218, 446, 104, 33, WHITE, True)
        s.text("Supervisor checks availability,\nqualifications, and shift rules\nbefore approving a move.", 458, 344, 447, 112, 24, LIGHT_TEXT)
        s.text("Open the briefing", 48, 461, 330, 37, 21, WHITE, True, link=APP_URL)
        s.text("Ask a leadership follow-up in Genie", 458, 461, 448, 37, 21, WHITE, True, link=GENIE_URL)
        n = notes("3 minutes including briefing and Genie", "Here is the specific decision the forecast supports: Memphis at 10am on September 3 needs 17 workers against 8 scheduled, a gap of 9. This is a dated synthetic example.",
                  f"In the app ({APP_URL}), click Generate briefing. Check the first recommendation against that exact forecast row. Then open Genie ({GENIE_URL}) and ask: Which terminal has the highest total detention fees? Include the date range of this synthetic dataset. The verified answer is Memphis, $91,650 rounded. Inspect the SQL and result rows. If useful, ask which dated shifts have the largest staffing gaps.",
                  "The staffing number is a planning signal. A supervisor must decide whether workers can move and record the actual action. The model's $378 for this hour is modeled overtime exposure, not a proven saving.",
                  "For the architect, here is the data path that makes this answer traceable.", "evidence/06_forecast.md; evidence/2026-10-15-genie-current.json; evidence/2026-10-15-genie-staffing.json; evidence/2026-10-15-app-current.json.")
    elif kind == "architecture":
        s.heading(entry["title"])
        s.text("Signals", 48, 178, 145, 34, 24, INK, True)
        s.text("Gate events\nDock-camera frames", 48, 225, 168, 74, 20, MUTED)
        for asset, x, label, detail in [("lakeflow", 256, "Lakeflow", "Bronze and silver"),
                                        ("uc", 451, "Gold tables", "Curated metrics"),
                                        ("lakebase", 651, "Lakebase", "Operational copy")]:
            s.image(asset, x, 157, 51, 51)
            s.text(label, x - 8, 220, 178, 40, 24, INK, True)
            s.text(detail, x - 8, 264, 178, 51, 18, MUTED)
        s.text("App", 811, 221, 105, 38, 27, INK, True)
        s.text("Supervisor\ndecision", 811, 265, 105, 64, 19, MUTED)
        for x1, x2 in [(201, 239), (408, 434), (605, 634), (793, 817)]:
            s.line(x1, 186, x2, 186)
        s.text("MLflow models", 451, 365, 221, 35, 23, TEAL, True)
        s.text("Vision and staffing predictions\nwrite back to gold", 451, 406, 265, 63, 18, MUTED)
        s.line(500, 322, 500, 354)
        s.image("genie", 779, 362, 44, 44)
        s.text("Genie", 832, 368, 86, 35, 23, INK, True)
        s.text("Questions on the same gold", 740, 419, 177, 56, 18, MUTED)
        s.line(605, 320, 605, 336, False)
        s.line(605, 336, 802, 336, False)
        s.line(802, 336, 802, 354)
        s.text("Unity Catalog governs lakehouse data and models. Postgres uses database roles.", 48, 476, 870, 30, 17, TEAL)
        n = notes("1.5 minutes", "The architecture follows the operational decision we just made.",
                  "Lakeflow ingests gate events and camera frames into bronze and silver. Gold provides curated metrics and the operational snapshot. Unity Catalog governs lakehouse access and registered models. Forecast and CV predictions feed the gold serving tables. Lakebase stores an operational copy for the app; Genie queries the gold analytics directly. The app also calls a Databricks-hosted foundation model to draft the briefing from the selected staffing rows.",
                  "The same definitions support operational reads and leadership questions. Lakebase has separate Postgres roles and a snapshot-copy script; UC policies do not automatically follow copied data. The forecast is batch scored, and the image classifier has a model endpoint.",
                  "Integration is demonstrated. The next question is what the pilot still needs to prove.", "notebooks/01_generate_data.py through notebooks/07_genai_assistant.py; scripts/lakebase_sync.py; app/app.py; original icons from ~/Documents/logos.",
                  "Show the worker-ID mask and grants in the walkthrough if asked. It is a group-based table column mask, not a governed-tag ABAC policy. A real-feed design must address late events, identity, image retention, and serving freshness.")
    elif kind == "scorecard":
        s.heading(entry["title"], 34)
        s.text("Verified prototype", 48, 139, 390, 42, 27, TEAL, True)
        s.text("Proposed pilot acceptance", 504, 139, 408, 42, 27, ORANGE, True)
        evidence = ["36 doors served through Lakebase", "Forecast and briefing connected", "Genie answer reconciled to source", "Four synthetic camera states classified"]
        targets = ["At least 10% lower detention per trailer", "No increase in overtime per trailer", "Forecast MAE at or below 2 workers", "p95 data age at or below 5 minutes"]
        for i, (actual, target) in enumerate(zip(evidence, targets)):
            y = 209 + i * 58
            s.text(actual, 48, y, 388, 52, 22)
            s.text(target, 504, y, 408, 52, 22, INK, True)
        s.text("Agree targets after baseline review. Test them with real pilot feeds and matched shifts.", 48, 463, 865, 40, 19, MUTED)
        n = notes("1 minute", "The demo proves that the components connect and that the displayed answer can be checked. It does not prove savings on real operations.",
                  "Separate four verified prototype checks from four proposed pilot targets. Detention per trailer should fall at least 10%, overtime per trailer should not rise, forecast MAE should be no greater than two workers, and p95 observation age should be within five minutes. These are suggested acceptance criteria for sponsor review, not achieved prototype SLAs or industry benchmarks.",
                  "Baseline and comparable-shift selection come before the intervention. Real-camera evaluation and supervisor acceptance remain part of readiness.",
                  "A small pilot needs named owners and explicit stop/go gates to produce that evidence.", "evidence/2026-10-15-app-current.json; evidence/2026-10-15-cv-current.json; evidence/2026-10-15-genie-current.json; evidence/workspace-demo-current.json. Pilot thresholds are proposed assumptions.")
    elif kind == "pilot":
        s.heading(entry["title"], 34)
        s.text("Scope: Memphis, existing feeds, supervisor-approved staffing changes", 48, 127, 864, 44, 22, MUTED)
        s.grid([
            ["When", "Deliverable", "Accountable owner", "Decision gate"],
            ["Week 1", "Feeds connected\nBaseline scorecard", "Platform architect\nTerminal manager", "Data ready and\nbaseline agreed"],
            ["Week 2", "Shadow staffing plan\nCamera validation", "Analytics lead\nTerminal manager", "Forecast and\nfreshness accepted"],
            ["Week 3", "Controlled staffing trial\nAction log", "Terminal manager", "Supervisor and\nsafety approval"],
            ["Week 4", "Matched-shift results\nNet cost assessment", "VP Operations\nFinance partner", "Scale, revise,\nor stop"],
        ], [90, 275, 255, 244], 178, 51, 18)
        s.text("Clock starts after feed access and pilot ownership are confirmed.", 48, 473, 864, 32, 19, TEAL, True)
        n = notes("1.5 minutes", "Propose one terminal for 30 days, with a decision gate each week. The calendar begins when owners and access are ready, not on a promise made in this presentation.",
                  "Week 1 establishes feeds, metric definitions, and comparable shifts. Week 2 runs the forecast in shadow mode and validates camera conditions and freshness. Week 3 trials supervisor-approved staffing changes and logs overrides. Week 4 compares detention and overtime per trailer and reviews the net cost.",
                  "The VP and finance partner decide whether to expand, correct the approach, or stop. Each gate has an accountable role; names must be assigned at kickoff.",
                  "That decision needs a transparent economic baseline and an agreed cost envelope.", "Proposed pilot plan. No customer dates, staffing commitments, budget, or implementation effort have been approved.",
                  "If feeds or labor-system constraints block Week 1, scope a data-readiness phase rather than claiming that a fixed 30-day value test has begun.")
    elif kind == "economics":
        s.heading(entry["title"])
        s.text("31-day synthetic cost baseline", 48, 136, 411, 38, 22, MUTED)
        s.text("$135,624", 44, 185, 435, 95, 63, INK, True)
        s.text("$91,650 detention\n$43,974 modeled overtime", 48, 299, 423, 87, 26, MUTED)
        s.text("At the proposed 10% detention target", 502, 136, 413, 67, 23, TEAL, True)
        s.text("$9,165", 497, 223, 420, 90, 60, ORANGE, True)
        s.text("gross benefit per comparable 31 days", 502, 320, 410, 62, 23)
        s.text("Net benefit must deduct incremental labor, platform, and implementation costs.", 48, 424, 866, 57, 25, INK, True)
        s.footer("Illustrative sensitivity only. Replace synthetic costs with the agreed pilot baseline.")
        n = notes("1 minute", "Size the first business case for Memphis, not the entire network.",
                  "The exact Memphis synthetic baseline is $91,649.63 plus $43,974 = $135,623.63 over 31 days. At constant trailer volume, the proposed 10% detention-per-trailer improvement would reduce detention by $9,164.96, rounded to $9,165 gross benefit. This assumes no overtime increase and illustrates the same target shown on the pilot scorecard; it is not an achieved saving.",
                  "Before approval, finance must replace simulated exposure with actual invoices and payroll. Subtract incremental regular labor, platform consumption, and implementation cost. Do not double-count overtime shifted to regular staffing as free savings.",
                  "The immediate ask is a named sponsor and a scoped kickoff that can approve those assumptions.", "evidence/2026-10-15-data-reconciliation.md. Calculation: 91649.63 * 0.10 = 9164.963 at constant trailer volume and no overtime increase. No industry benchmark or guaranteed ROI claim.")
    elif kind == "ask":
        s.heading(entry["title"])
        s.text("Authorize one terminal and a measured trial.", 48, 126, 864, 54, 29, WHITE, True)
        actions = [
            (215, "Within 2 business days", "VP Operations", "Name the Memphis sponsor and terminal owner"),
            (297, "Within 5 business days", "Terminal manager + architect", "Confirm feeds, access, and staffing constraints"),
            (379, "At a 45-minute kickoff", "Sponsor + finance + delivery", "Approve scorecard, cost cap, and trial start"),
        ]
        for y, when, owner, action in actions:
            s.text(when, 48, y, 280, 36, 22, "#FF8A79", True)
            s.text(owner, 48, y + 39, 299, 32, 17, LIGHT_TEXT)
            s.text(action, 382, y + 2, 529, 74, 25, WHITE, True)
        s.text("Kickoff output: signed pilot scope, named owners, and an agreed success scorecard", 48, 473, 864, 30, 18, LIGHT_TEXT)
        n = notes("1.5 minutes, then 6 minutes for discussion", "We have followed the problem from the roster mismatch to a specific Memphis staffing decision. The next step is a measured pilot with an accountable sponsor.",
                  "Ask the VP to nominate the Memphis sponsor and terminal owner within two business days. Ask the terminal manager and architect to confirm access to gate events, camera frames, labor schedules, and cost data within five business days. Propose a 45-minute kickoff with the sponsor, finance, and delivery owners to approve the scorecard, cost cap, and start gate.",
                  "The meeting should end with a named accountable owner and a scheduled kickoff. If readiness is incomplete, agree the missing input and its owner rather than accepting a vague follow-up.",
                  "Invite questions from the VP on economics and adoption, and from the architect on data readiness and governance. Use the appendices only as needed.", "Proposed next steps. Timing is relative to sponsor agreement, not a calendar commitment. DEMO.md; the preceding pilot scope and illustrative economics.",
                  "Ask: Who will own Memphis operations for this pilot, and can we schedule the kickoff with the platform and finance owners? Confirm the answer and the next deliverable before closing.")
    elif kind == "technical":
        s.heading(entry["title"], 34)
        s.grid([
            ["Component", "Evidence", "Pilot validation still required"],
            ["Staffing model", "MAE 1.885 workers\n5.6% better than baseline", "Real-demand holdout\nStaffing and skills constraints"],
            ["Camera classifier", "Four states verified live\n100% synthetic holdout", "Real cameras, lighting,\nocclusion, and drift"],
            ["Serving and governance", "App reads Lakebase\nWorker-ID column mask in UC", "Continuous sync and freshness\nSeparate Postgres grants"],
            ["AI briefing and Genie", "Dated recommendations\nSQL and source rows inspectable", "Human review and identity\nvalidation at each boundary"],
        ], [185, 308, 371], 152, 63, 18)
        s.text("Forecast metrics describe the original synthetic training snapshot.", 48, 477, 864, 30, 17, MUTED)
        n = notes("Optional technical appendix", "The technical proof is inspectable, and its limits define the pilot work.",
                  "The forecast uses GradientBoosting with a five-day time holdout. MAE is 1.885, versus 1.997 for the hourly-mean baseline, and R-squared is 0.606. The arrival-hour correction did not retrain that model. The classifier is a UC-registered pyfunc deployed as version 2; a UC alias change alone does not refresh the serving endpoint.",
                  "Four successful image-state requests and synthetic holdout accuracy do not establish real-camera accuracy. UC masks apply to lakehouse reads, while Lakebase uses separate Postgres roles. Genie and the app can run under different configured identities.",
                  "Return to the specific pilot gate or decision the question concerns.", "evidence/05_cv_model.md; evidence/06_forecast.md; evidence/2026-10-15-cv-current.json; evidence/2026-10-15-app-current.json; notebooks/04_governance.py.")
    elif kind == "presenter":
        s.heading(entry["title"])
        for y, title, detail, url in [
            (142, "Operations console", "Dock snapshot, dated staffing plan, and briefing", APP_URL),
            (216, "Genie", "Ask about terminal cost, then inspect SQL", GENIE_URL),
            (290, "Workspace walkthrough", "Source reconciliation, forecasts, and governance", NOTEBOOK_URL),
            (364, "Successful validation run", "Read-only walkthrough and reconciled totals", RUN_URL),
        ]:
            s.text(title, 48, y, 385, 42, 27, TEAL, True, link=url)
            s.text(detail, 464, y + 2, 448, 57, 21, MUTED)
        s.text("19 minutes for the story and demo. 6 minutes for questions.", 48, 460, 865, 41, 25, INK, True)
        n = notes("Presenter reference", "Pre-open the console, Genie, and the walkthrough. Keep the two stakeholder roles in mind throughout.",
                  "Delivery timing: setup and context 2 minutes; roster mismatch 1.5; cost 1; operating change 1; console 4; briefing and Genie 3; architecture 1.5; scorecard 1; pilot 1.5; economics 1; decision 1.5. Total 19 minutes plus 6 for discussion. The actual prepared segment totals 19 minutes by the slide-level timing plan.",
                  "History is July 30–August 29, 2026. Forecasts cover August 30–September 5. The software runs live, while its underlying example data is a dated synthetic replay. If a live step fails, label the displayed screenshot or saved evidence as a fallback.",
                  "Resume the main narrative at the customer decision, not a feature tour.", "deck/deck-spec.json; evidence/workspace-demo-current.json; evidence/2026-10-15-app-current.json; evidence/2026-10-15-genie-current.json.")
    else:
        raise ValueError(f"Unknown narrative layout: {kind}")
    return s, n


def upload_assets(builder: Any) -> dict[str, str]:
    """Retrieve native image URLs without changing asset-sharing permissions."""
    manifest = DECK / "assets" / "native-assets.json"
    if not manifest.exists():
        raise RuntimeError("The private slide-image asset manifest is missing. Restore deck/assets/native-assets.json.")
    native = builder.get_presentation(json.loads(manifest.read_text())["id"])
    if len(native.get("slides", [])) != len(ASSET_PATHS):
        raise RuntimeError("The private slide-image asset presentation has an unexpected slide count.")
    return {key: next(e["image"]["contentUrl"] for e in page["pageElements"] if "image" in e)
            for key, page in zip(ASSET_PATHS, native["slides"])}


def replace_slides(builder: Any, pres_id: str, assets: dict[str, str], only: str | None = None) -> None:
    """Apply native slide objects, then write correctly aligned speaker notes."""
    current = builder.get_presentation(pres_id)
    layout_info = next(x for x in current["layouts"] if x["layoutProperties"].get("displayName") == "Content E - Blank")
    layout = layout_info["objectId"]
    master_id = layout_info["layoutProperties"]["masterObjectId"]
    master = next(m for m in current["masters"] if m["objectId"] == master_id)
    legacy_footer = [e["objectId"] for e in master.get("pageElements", [])
                     if e.get("transform", {}).get("translateY", 0) > 490 * 12700]
    if legacy_footer:
        builder.batch_update(pres_id, [{"deleteObject": {"objectId": x}} for x in legacy_footer])
    # This template's blank layout has an opaque white rectangle above the
    # actual page background. All revised slides use this layout, so remove
    # that inherited fill once and let each page own its intended background.
    for element in layout_info.get("pageElements", []):
        if element.get("shape", {}).get("shapeType") == "RECTANGLE":
            builder.batch_update(pres_id, [{"updateShapeProperties": {
                "objectId": element["objectId"],
                "shapeProperties": {"shapeBackgroundFill": {"propertyState": "NOT_RENDERED"}},
                "fields": "shapeBackgroundFill.propertyState"}}])
    existing = {p["objectId"] for p in current.get("slides", [])}
    for i, entry in enumerate(SPECS, 1):
        if only and entry["id"] != only:
            continue
        slide, _ = compose(entry, i, assets)
        slide.requests[0]["createSlide"]["slideLayoutReference"] = {"layoutId": layout}
        if entry["id"] in existing:
            slide.requests.insert(0, {"deleteObject": {"objectId": entry["id"]}})
        builder.batch_update(pres_id, slide.requests)
        print(f"Slide {i}: {entry['title']}", flush=True)
    if only:
        index = next(i for i, s in enumerate(SPECS) if s["id"] == only)
        builder.batch_update(pres_id, [{"updateSlidesPosition": {"slideObjectIds": [only], "insertionIndex": index}}])
    current = builder.get_presentation(pres_id)
    extra = [p["objectId"] for p in current.get("slides", []) if p["objectId"] not in {s["id"] for s in SPECS}]
    if extra:
        builder.batch_update(pres_id, [{"deleteObject": {"objectId": x}} for x in extra])
    current = builder.get_presentation(pres_id)
    reqs: list[dict[str, Any]] = []
    for i, page in enumerate(current["slides"], 1):
        entry = next(s for s in SPECS if s["id"] == page["objectId"])
        _, cue = compose(entry, i, assets)
        np = page["slideProperties"]["notesPage"]
        nid = np["notesProperties"]["speakerNotesObjectId"]
        old = "".join(t.get("textRun", {}).get("content", "") for e in np.get("pageElements", [])
                      if e["objectId"] == nid for t in e.get("shape", {}).get("text", {}).get("textElements", []))
        if old.strip():
            reqs.append({"deleteText": {"objectId": nid, "textRange": {"type": "ALL"}}})
        reqs.append({"insertText": {"objectId": nid, "text": cue, "insertionIndex": 0}})
        for e in page.get("pageElements", []):
            if e.get("shape", {}).get("placeholder", {}).get("type") == "SLIDE_NUMBER":
                reqs.append({"deleteObject": {"objectId": e["objectId"]}})
    builder.batch_update(pres_id, reqs)


def main() -> None:
    """Build a private review draft or publish the reviewed design in place."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--builder", required=True, type=Path)
    ap.add_argument("--publish", action="store_true")
    ap.add_argument("--slide")
    ap.add_argument("--verify-only", action="store_true")
    args = ap.parse_args()
    module = importlib.util.spec_from_file_location("gslides_builder", args.builder)
    if module is None or module.loader is None:
        raise RuntimeError("Cannot load the Google Slides helper.")
    builder = importlib.util.module_from_spec(module)
    module.loader.exec_module(builder)
    draft_path = ROOT / "scratch" / "revision-draft.json"
    if args.publish:
        pres_id = LIVE_ID
    elif draft_path.exists():
        pres_id = json.loads(draft_path.read_text())["presentation_id"]
    else:
        pres_id = builder.copy_presentation(LIVE_ID, "Meridian Freight - narrative revision review")
        draft_path.write_text(json.dumps({"presentation_id": pres_id}) + "\n")
    if not args.verify_only:
        assets = upload_assets(builder)
        replace_slides(builder, pres_id, assets, args.slide)
    report = builder.validate_presentation(pres_id)
    prefix = DECK if args.publish else ROOT / "scratch" / "revision-draft"
    prefix.mkdir(exist_ok=True, parents=True)
    (prefix / "validation.json").write_text(json.dumps(report, indent=2) + "\n")
    rendered = builder.export_thumbnails(pres_id, str(prefix / "previews"))
    (prefix / "thumbnails.json").write_text(json.dumps(rendered, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "issues"}), flush=True)
    print("Rendered", rendered["exported"], "slides", flush=True)
    if args.publish:
        (DECK / "deck-spec.json").write_text(json.dumps(SPECS, indent=2) + "\n")
        (DECK / "presentation.json").write_text(json.dumps({"presentation_id": LIVE_ID,
            "url": f"https://docs.google.com/presentation/d/{LIVE_ID}/edit", "slide_count": len(SPECS),
            "speaker_notes": True, "revision": "customer narrative and pilot decision", "sharing": "private"}, indent=2) + "\n")
        guide = ["# Meridian Freight presenter guide", "", "19 minutes of story and live demo, then 6 minutes of discussion.", ""]
        for i, entry in enumerate(SPECS, 1):
            _, cue = compose(entry, i, {key: "" for key in ASSET_PATHS})
            guide.extend([f"## {i}. {entry['title']}", "", cue, ""])
        (ROOT / "demo" / "roleplay_demo_script.md").write_text("\n".join(guide).rstrip() + "\n")
    if report["errors"]:
        raise RuntimeError("Slides need review; inspect validation.json before delivery.")


if __name__ == "__main__":
    main()
