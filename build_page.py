"""Build a static, phone-friendly dashboard and RSS feed from prices.json."""
import json
from datetime import datetime
from email.utils import format_datetime
from html import escape
from pathlib import Path
from xml.etree import ElementTree as ET
import os


def money(cents):
    return f"${cents / 100:,.2f}"


def main():
    state = json.loads(Path("prices.json").read_text("utf-8"))
    site = Path("site")
    site.mkdir(exist_ok=True)
    base = os.getenv("PAGE_URL", "http://localhost:8000").rstrip("/")
    feed = ET.Element("rss", version="2.0")
    channel = ET.SubElement(feed, "channel")
    for tag, value in dict(title="MacBook price drops", link=base + "/", description="Observed US listing price drops").items():
        ET.SubElement(channel, tag).text = value
    drops = []
    for d in state["drops"]:
        title = f"{d['store']} · {d['condition']}: {money(d['previous'])} → {money(d['cents'])} · {d['title']}"
        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = title
        ET.SubElement(item, "link").text = d["url"]
        ET.SubElement(item, "guid", isPermaLink="false").text = f"{d['id']}:{d['date']}"
        ET.SubElement(item, "pubDate").text = format_datetime(datetime.fromisoformat(d["date"]))
        if len(drops) < 5:
            drops.append(f'<li><small>{escape(d["date"][:16].replace("T", " "))} UTC</small><br>'
                         f'<a href="{escape(d["url"])}">{escape(title)}</a></li>')
    ET.ElementTree(feed).write(site / "drops.xml", encoding="utf-8", xml_declaration=True)
    rows, status = [], []
    for name, src in state["sources"].items():
        stamp = (src["checked"] or "")[:16].replace("T", " ")
        status.append(f"<li><b>{escape(name)}</b> · {escape(src['status'])} · "
                      + (f"last success {escape(stamp)} UTC" if stamp else "no successful check yet") + "</li>")
        for r in src["items"]:
            stale = " · Last known price" if src["status"] != "Updated" else ""
            rows.append((r["cents"], f'<li><strong>{money(r["cents"])}</strong> <small>{escape(name)} · '
                         f'{escape(r["condition"])}{stale}</small><br><a href="{escape(r["url"])}">'
                         f'{escape(r["title"])}</a><br><small>{escape(r["specs"])}</small></li>'))
    page = """<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>MacBook price watch</title>
<link rel="alternate" type="application/rss+xml" href="drops.xml" title="Price drops">
<style>
:root{font:100%/1.5 system-ui;color:#182923;background:#f6f7f1}
body{max-width:46rem;margin:auto;padding:1.5rem}h1{font:600 clamp(2.4rem,8vw,4rem)/1.05 Georgia,serif;margin:.6em 0 .2em}
h2{font:600 1.6rem Georgia,serif;margin:1.8em 0 .35em}ul{padding:0;list-style:none}li{border-top:1px solid #bac7bc;padding:.7rem 0;overflow-wrap:anywhere}
a{color:#005d49;text-underline-offset:.16em}a:focus-visible{outline:3px solid #a64800}small{color:#40594e}
strong{font-size:1.35rem;font-variant-numeric:tabular-nums;margin-right:.5rem}
</style><main><h1>MacBook price watch</h1><p>US listings · M4 or M5 · 24 GB+ RAM · 512 GB+ SSD</p>
<a href="drops.xml">Subscribe to price drops (RSS)</a>"""
    page += "<h2>Source status</h2><ul>" + "".join(status) + "</ul>"
    page += "<h2>Recent drops</h2>" + ("<ul>" + "".join(drops) + "</ul>" if drops else "<p>No price drops observed yet.</p>")
    page += f"<h2>Matching listings ({len(rows)})</h2><p>Lowest item price first. Tax and shipping not included.</p>"
    page += ("<ul>" + "".join(row for _, row in sorted(rows)) + "</ul>" if rows else
             "<p>No matching listings to show. Check the source status above.</p>")
    (site / "index.html").write_text(page + "</main></html>", encoding="utf-8")


if __name__ == "__main__":
    main()
