"""Sanity check for TC-42: axe-core finds no violations on a real page and does flag a
low-contrast control page. Usage: axe_sanity.py <load-sessions.json>"""

import json
import sys
from pathlib import Path

from axe_playwright_python.sync_playwright import Axe
from playwright.sync_api import sync_playwright

d = json.loads(Path(sys.argv[1]).read_text())["drivers"][0]
with sync_playwright() as p:
    b = p.chromium.launch()
    c = b.new_context()
    c.add_cookies([{"name": "sessionid", "value": d["sessionid"], "url": "http://127.0.0.1:8100"}])
    pg = c.new_page()
    pg.goto("http://127.0.0.1:8100/reservations/search/")
    vid = pg.locator("#vehicle option[value]:not([value=''])").first.get_attribute("value")
    pg.goto(
        f"http://127.0.0.1:8100/reservations/search/?lot=1&vehicle={vid}&start=2026-11-06T10:00&end=2026-11-06T12:00"
    )
    print("result cards:", pg.locator(".search-result").count())
    r = (
        Axe()
        .run(pg, options={"runOnly": {"type": "tag", "values": ["wcag2a", "wcag2aa", "wcag21aa"]}})
        .response
    )
    print(
        "violations",
        len(r["violations"]),
        "passes",
        len(r["passes"]),
        "incomplete",
        [(i["id"], len(i["nodes"])) for i in r["incomplete"]],
    )
    for i in r["incomplete"]:
        for n in i["nodes"]:
            print(
                "  needs review:",
                i["id"],
                n["html"][:120],
                "|",
                n.get("failureSummary", "")[:160].replace("\n", " "),
            )
    print(
        "color-contrast passed nodes:",
        sum(len(x["nodes"]) for x in r["passes"] if x["id"] == "color-contrast"),
    )
    pg.set_content(
        '<html lang="en"><body><p style="color:#bbb;background:#fff">low contrast</p></body></html>'
    )
    r = Axe().run(pg).response
    print("control page violations:", [v["id"] for v in r["violations"]])
