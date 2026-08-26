#!/usr/bin/env python3
"""Harvest Texas court/judicial news into a durable catalog, then rebuild the live feed.

Captures are append-only metadata (title, source, urls, snippet, date).
Full republishing of paywalled articles is intentionally not done.
Wayback links are recorded so a vanished page still has a public record pointer.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAPTURES = ROOT / "archive" / "captures.jsonl"
ENTRIES = ROOT / "entries.json"
QUERIES = ROOT / "ingest" / "queries.txt"
UA = "JusticePulseWire/1.0 (+https://everwright.github.io/justice-pulse/)"

MUST = re.compile(
    r"\b(judge|judicial|justice of the peace|\bJP\b|magistrate|court of appeals|"
    r"supreme court|criminal appeals|probate|arbitration|SCJC|commission on judicial|"
    r"recusal|district court|family court|county judge|guardianship|juvenile court)\b",
    re.I,
)
TEXAS = re.compile(
    r"\b(Texas|Texan|Houston|Dallas|Austin|San Antonio|Fort Worth|Harris County|"
    r"Bexar|Travis|Tarrant|El Paso|Midland|Maverick|Angelina|McLennan|Fort Bend|"
    r"Collin|Denton|Montgomery|Galveston|Cameron|Hidalgo|Nueces|Jefferson|Lubbock|"
    r"Amarillo|Waco|Tyler|Laredo|Corpus|McAllen)\b",
    re.I,
)
EXCLUDE = re.compile(
    r"National Guard to Illinois|Louisiana appeals|ICE custody|"
    r"court interpreter released|Trump can.?t deploy|Healthcare Dive|D\.R\. Horton",
    re.I,
)
COUNTIES = [
    ("Harris", "Houston"),
    ("Dallas", "DFW"),
    ("Tarrant", "DFW"),
    ("Collin", "DFW"),
    ("Denton", "DFW"),
    ("Bexar", "San Antonio"),
    ("Travis", "Austin"),
    ("Williamson", "Austin"),
    ("Fort Bend", "Houston"),
    ("Montgomery", "Houston"),
    ("Galveston", "Houston"),
    ("El Paso", "West Texas / Border"),
    ("Midland", "West Texas"),
    ("Maverick", "Border"),
    ("Hidalgo", "Border"),
    ("Cameron", "Border"),
    ("Webb", "Border"),
    ("Angelina", "East Texas"),
    ("Smith", "East Texas"),
    ("McLennan", "Central Texas"),
    ("Lubbock", "West Texas"),
    ("Nueces", "Coast / South"),
    ("Jefferson", "Houston / Gulf"),
    ("Loving", "West Texas"),
    ("Deaf Smith", "West Texas"),
]


def key_of(title: str) -> str:
    t = re.sub(r"\W+", " ", (title or "").lower())
    t = re.sub(r"\b(federal|texas|a|the|an)\b", " ", t)
    return re.sub(r"\s+", " ", t).strip()[:90]


def area(blob: str) -> str:
    t = blob.lower()
    if any(k in t for k in ["contribution", "campaign finance", "recusal"]):
        return "Campaign finance"
    if "chapter 87" in t:
        return "Chapter 87"
    if any(k in t for k in ["family court", "custody", "cps ", "child protective", "divorce"]):
        return "Family"
    if "probate" in t or "guardianship" in t:
        return "Probate"
    if "arbitration" in t:
        return "Arbitration"
    if any(k in t for k in ["election", "primary", "ballot", "candidate", "voter guide"]):
        return "Elections"
    if any(k in t for k in ["scjc", "judicial conduct", "reprimand", "admonition", "public warning"]):
        return "SCJC"
    if "justice of the peace" in t or re.search(r"\bjp\b", t):
        return "Criminal / JP"
    if "criminal" in t:
        return "Criminal"
    if "court of appeals" in t or "supreme court" in t:
        return "Appellate"
    if any(k in t for k in ["ruling", "opinion", "injunction", "strikes down", "struck down"]):
        return "Rulings"
    return "Courts"


def geo(blob: str):
    for c, r in COUNTIES:
        if re.search(rf"\b{re.escape(c)}\b", blob, re.I):
            return c, r
    if re.search(r"Texas Supreme Court|Court of Criminal Appeals|statewide|State Commission on Judicial Conduct", blob, re.I):
        return "Statewide", "Statewide"
    if "Houston" in blob:
        return "Harris", "Houston"
    if "Dallas" in blob:
        return "Dallas", "DFW"
    if "Austin" in blob:
        return "Travis", "Austin"
    if "San Antonio" in blob:
        return "Bexar", "San Antonio"
    if "Fort Worth" in blob:
        return "Tarrant", "DFW"
    if "El Paso" in blob:
        return "El Paso", "West Texas / Border"
    return "Statewide", "Statewide"


def parse_date(p: str | None) -> str | None:
    if not p:
        return None
    try:
        dt = parsedate_to_datetime(p)
        if dt.tzinfo:
            dt = dt.astimezone(timezone.utc)
        return dt.date().isoformat()
    except Exception:
        return None


def fetch(url: str, timeout: int = 25) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def unwrap(url: str) -> str:
    if not url or "news.google.com" not in url:
        return url
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA}, method="HEAD")
        with urllib.request.urlopen(req, timeout=8) as r:
            return r.geturl() or url
    except Exception:
        return url


def wayback_url(url: str) -> str:
    return "https://web.archive.org/web/" + urllib.parse.quote(url, safe="")


def request_wayback_save(url: str) -> str | None:
    if not url or url.startswith("https://news.google.com"):
        return None
    try:
        save = "https://web.archive.org/save/" + url
        req = urllib.request.Request(save, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=40) as r:
            final = r.geturl()
            return final if "web.archive.org" in final else None
    except Exception:
        return None


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def google_rss(query: str, when: str) -> list[dict]:
    q = f"{query} when:{when}"
    url = "https://news.google.com/rss/search?q=" + urllib.parse.quote(q) + "&hl=en-US&gl=US&ceid=US:en"
    raw = fetch(url)
    root = ET.fromstring(raw)
    items = []
    for it in root.findall(".//item"):
        title = (it.findtext("title") or "").strip()
        link = (it.findtext("link") or "").strip()
        pub = (it.findtext("pubDate") or "").strip()
        src = (it.findtext("source") or "").strip()
        desc = it.findtext("description") or ""
        desc = html.unescape(re.sub(r"<[^>]+>", " ", desc))
        desc = re.sub(r"\s+", " ", desc).strip()[:600]
        items.append({"title": title, "url": link, "pubDate": pub, "source": src, "summary": desc})
    return items


def accept(title: str, summary: str) -> bool:
    blob = title + " " + summary
    if EXCLUDE.search(blob):
        return False
    if not MUST.search(blob):
        return False
    if not TEXAS.search(blob):
        return False
    return True


def to_record(it: dict, captured: str, unwrap_urls: bool) -> dict | None:
    title = it.get("title") or ""
    summary = it.get("summary") or ""
    if not accept(title, summary):
        return None
    d = parse_date(it.get("pubDate"))
    if not d or d < "2018-01-01":
        return None
    tclean = re.sub(r"\s+-\s+[^-]{3,60}$", "", title).strip()[:180]
    blob = tclean + " " + summary
    county, region = geo(blob)
    url = it.get("url") or ""
    if unwrap_urls:
        url = unwrap(url)
    src = re.sub(r"\s*-\s*Breaking.*", "", it.get("source") or "News")[:80]
    rec = {
        "id": key_of(tclean),
        "date": d,
        "title": tclean,
        "source": src,
        "url": url,
        "canonical_url": url,
        "archive_url": wayback_url(url) if url else "",
        "summary": (summary or tclean)[:520],
        "area": area(blob),
        "county": county,
        "region": region,
        "status": "confirmed",
        "kind": "news",
        "quality": "Published reporting via public news wire",
        "captured_at": captured,
    }
    return rec


def merge(existing: list[dict], incoming: list[dict]) -> tuple[list[dict], int]:
    by = {}
    for row in existing:
        by[row.get("id") or key_of(row.get("title", ""))] = row
    added = 0
    for row in incoming:
        k = row.get("id") or key_of(row.get("title", ""))
        if k in by:
            old = by[k]
            if row.get("eve_read") and not old.get("eve_read"):
                old["eve_read"] = row["eve_read"]
                old["kind"] = "featured"
            if row.get("canonical_url") and "news.google.com" in (old.get("url") or "") and "news.google.com" not in row["canonical_url"]:
                old["url"] = row["canonical_url"]
                old["canonical_url"] = row["canonical_url"]
                old["archive_url"] = wayback_url(row["canonical_url"])
            continue
        by[k] = row
        added += 1
    rows = list(by.values())
    rows.sort(key=lambda x: (x.get("date") or "", 1 if x.get("kind") == "featured" else 0), reverse=True)
    return rows, added


def feed_item(row: dict) -> dict:
    keep = [
        "date", "title", "source", "url", "summary", "area", "county", "region",
        "status", "kind", "quality", "eve_read", "archive_url",
    ]
    return {k: row[k] for k in keep if k in row and row[k] not in (None, "")}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--when", default="7d", help="Google News window, e.g. 1d, 7d, 1y, 5y")
    ap.add_argument("--unwrap", action="store_true")
    ap.add_argument("--wayback-save", type=int, default=0, help="Request IA save for N new URLs")
    ap.add_argument("--sleep", type=float, default=0.15)
    args = ap.parse_args()

    captured = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    queries = [q.strip() for q in QUERIES.read_text(encoding="utf-8").splitlines() if q.strip() and not q.startswith("#")]
    incoming = []
    for q in queries:
        try:
            raw = google_rss(q, args.when)
            print(f"ok {len(raw):3d}  {q}", flush=True)
            for it in raw:
                rec = to_record(it, captured, unwrap_urls=False)
                if rec:
                    incoming.append(rec)
        except Exception as e:
            print(f"FAIL {q}: {type(e).__name__} {e}", flush=True)
        time.sleep(args.sleep)

    existing = load_jsonl(CAPTURES)
    # seed from live entries if catalog empty
    if not existing and ENTRIES.exists():
        live = json.loads(ENTRIES.read_text(encoding="utf-8"))
        for it in live.get("items", []):
            it = dict(it)
            it["id"] = key_of(it.get("title", ""))
            it.setdefault("captured_at", captured)
            it.setdefault("canonical_url", it.get("url", ""))
            it.setdefault("archive_url", wayback_url(it.get("url", "")) if it.get("url") else "")
            existing.append(it)

    rows, added = merge(existing, incoming)
    if args.unwrap:
        n = 0
        for row in rows:
            if n >= 80:
                break
            u = row.get("url") or ""
            if "news.google.com" not in u:
                continue
            nu = unwrap(u)
            if nu != u:
                row["url"] = nu
                row["canonical_url"] = nu
                row["archive_url"] = wayback_url(nu)
                n += 1
            time.sleep(0.05)

    saved = 0
    if args.wayback_save:
        for row in rows:
            if saved >= args.wayback_save:
                break
            if row.get("wayback_saved"):
                continue
            u = row.get("canonical_url") or row.get("url") or ""
            loc = request_wayback_save(u)
            if loc:
                row["archive_url"] = loc
                row["wayback_saved"] = True
                saved += 1
                time.sleep(1.0)

    write_jsonl(CAPTURES, rows)
    items = [feed_item(r) for r in rows]
    ENTRIES.write_text(
        json.dumps(
            {
                "updated": date.today().isoformat(),
                "note": "Newest first. Durable catalog in archive/captures.jsonl. archive_url points at Wayback.",
                "items": items,
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"catalog={len(rows)} added={added} wayback_saved={saved} feed={len(items)}")


if __name__ == "__main__":
    main()
