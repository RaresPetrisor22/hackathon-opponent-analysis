"""scrape_media.py — One-off scraper for SuperLiga "CRONICA" match reports.

Usage:
    cd backend
    uv run python scripts/scrape_media.py

Pulls tactical match-report articles from Romanian football news sites,
extracts the body text, strips boilerplate, and writes one .txt + one
.meta.json per article into backend/data/raw_texts/.

This is a standalone utility — it does not touch the DB or the FastAPI app.
Plug demo team URLs into TARGETS below.
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from dataclasses import dataclass
from datetime import date
from hashlib import sha1
from pathlib import Path

import httpx
from bs4 import BeautifulSoup, Tag

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

OUTPUT_DIR = Path(__file__).parent.parent / "data" / "raw_texts"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36"
)

REQUEST_TIMEOUT = 20.0

BOILERPLATE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)^\s*(citeste si|citește și|vezi si|vezi și)\b.*$"),
    re.compile(r"(?i)^\s*(share|distribuie|abonează-te|aboneaza-te)\b.*$"),
    re.compile(r"(?i)^\s*(foto|video|sursa|sursă)\s*[:\-].*$"),
    re.compile(r"(?i)^\s*(comentari[ui]|reclam[ăa])\b.*$"),
    re.compile(r"(?i)^\s*publicat\s+(la|pe)\b.*$"),
)


@dataclass(frozen=True)
class Target:
    """A single article to scrape."""

    url: str
    team_id: int
    match_date: str  # ISO YYYY-MM-DD


# Demo teams: FCSB=559, CFR Cluj=2246, UTA Arad=2589, FCU Cluj=2599
# Dates are approximate — exact dates appear in the article body text.
# Note: gsp.ro/rezultate-live/meci/* pages are match-stats widgets (no editorial
# content) and will be skipped automatically by the 200-char body filter.
TARGETS: list[Target] = [
    # --- FCSB (team_id=559) — last 11 matches of 2024-25 regular season ---
    Target(url="https://www.gsp.ro/fotbal/liga-1/live-fcsb-universitatea-craiova-etapa-30-784308.html", team_id=559, match_date="2025-03-09"),
    Target(url="https://www.gsp.ro/fotbal/liga-1/rapid-fcsb-etapa-29-live-782650.html", team_id=559, match_date="2025-03-02"),
    Target(url="https://www.gsp.ro/fotbal/liga-1/fcsb-dinamo-derby-superliga-live-780600.html", team_id=559, match_date="2025-03-01"),
    Target(url="https://www.gsp.ro/fotbal/liga-1/live-gloria-buzau-fcsb-superliga-etapa-27-778830.html", team_id=559, match_date="2025-02-23"),
    Target(url="https://www.gsp.ro/fotbal/liga-1/live-fcsb-sepsi-etapa26-777301.html", team_id=559, match_date="2025-02-16"),
    Target(url="https://www.gsp.ro/fotbal/liga-1/live-petrolul-fcsb-etapa-25-776643.html", team_id=559, match_date="2025-02-09"),
    Target(url="https://www.gsp.ro/fotbal/liga-1/live-fcsb-uta-arad-arena-nationala-etapa14-superliga-858046.html", team_id=559, match_date="2025-11-24"),
    Target(url="https://www.gsp.ro/fotbal/liga-1/fcsb-hermannstadt-live-superliga-772610.html", team_id=559, match_date="2025-01-25"),
    Target(url="https://www.gsp.ro/fotbal/liga-1/live-poli-iasi-fcsb-superliga-769651.html", team_id=559, match_date="2025-01-05"),
    Target(url="https://www.gsp.ro/fotbal/liga-1/farul-fcsb-live-etapa-20-768505.html", team_id=559, match_date="2025-01-26"),
    Target(url="https://www.gsp.ro/fotbal/liga-1/live-fcsb-fc-botosani-etapa-19-767551.html", team_id=559, match_date="2025-01-19"),
    # --- CFR Cluj (team_id=2246) — article URLs only (meci/* pages have no body text) ---
    Target(url="https://www.gsp.ro/fotbal/liga-1/superliga-cfr-cluj-dinamo-finala-euro-2024-748349.html", team_id=2246, match_date="2024-07-14"),
    Target(url="https://www.gsp.ro/fotbal/liga-1/rapid-cfr-cluj-superliga-etapa-2-live-824206.html", team_id=2246, match_date="2024-07-20"),
    Target(url="https://www.gsp.ro/fotbal/liga-1/dan-nistor-istoria-superligii-u-cluj-cfr-751934.html", team_id=2246, match_date="2024-08-04"),
    Target(url="https://www.gsp.ro/fotbal/liga-1/cfr-cluj-fc-botosani-25082024-754388-galerie-foto-pic-1484744.html?sourcearticle=754398", team_id=2246, match_date="2024-08-25"),
    Target(url="https://www.gsp.ro/fotbal/liga-1/live-cfr-cluj-fcsb-etapa-9-superliga-756590.html", team_id=2246, match_date="2024-10-13"),
    # meci/* stats pages — included so they show up in the skip log
    Target(url="https://www.gsp.ro/rezultate-live/meci/4381194", team_id=2246, match_date="2024-07-20"),
    Target(url="https://www.gsp.ro/rezultate-live/meci/4381223", team_id=2246, match_date="2024-07-27"),
    Target(url="https://www.gsp.ro/rezultate-live/meci/434107", team_id=2246, match_date="2024-09-01"),
    Target(url="https://www.gsp.ro/rezultate-live/meci/4381260", team_id=2246, match_date="2024-09-01"),
    Target(url="https://www.gsp.ro/rezultate-live/meci/291771", team_id=2246, match_date="2024-10-06"),
    Target(url="https://www.gsp.ro/rezultate-live/meci/8020221", team_id=2246, match_date="2025-03-01"),
    Target(url="https://www.gsp.ro/rezultate-live/meci/8020252", team_id=2246, match_date="2025-03-08"),
    # --- UTA Arad (team_id=2589) — last 12 matches incl. play-out ---
    Target(url="https://www.gsp.ro/fotbal/liga-1/uta-sepsi-etapa-28-superliga-live-781228.html", team_id=2589, match_date="2025-02-22"),
    Target(url="https://www.gsp.ro/fotbal/liga-1/live-gloria-buzau-uta-arad-etapa-29-superliga-782834.html", team_id=2589, match_date="2025-03-02"),
    Target(url="https://www.gsp.ro/fotbal/liga-1/uta-dinamo-meciul-care-incheie-sezonul-regulat-al-superligii-784692.html", team_id=2589, match_date="2025-03-09"),
    Target(url="https://www.gsp.ro/fotbal/liga-1/uta-otelul-play-out-superliga-live-785962.html", team_id=2589, match_date="2025-03-30"),
    Target(url="https://www.gsp.ro/fotbal/liga-1/poli-iasi-uta-play-out-live-789670.html", team_id=2589, match_date="2025-04-06"),
    Target(url="https://www.gsp.ro/fotbal/liga-1/live-uta-fc-botosani-un-duel-intre-doua-echipe-in-situatii-diamental-opuse-lesslessechipe-probabile-cele-mai-tari-cote-791809.html", team_id=2589, match_date="2025-04-13"),
    Target(url="https://www.gsp.ro/fotbal/liga-1/live-unirea-slobozia-uta-play-out-etapa-4-superliga-794266.html", team_id=2589, match_date="2025-04-20"),
    Target(url="https://www.gsp.ro/fotbal/liga-1/live-uta-arad-sepsi-etapa-play-out-superliga-795511.html", team_id=2589, match_date="2025-04-27"),
    Target(url="https://www.gsp.ro/fotbal/liga-1/hermannstadt-uta-superliga-live-798118.html", team_id=2589, match_date="2025-05-04"),
    Target(url="https://www.gsp.ro/fotbal/liga-1/uta-petrolul-live-etapa-7-play-out-superliga-801041.html", team_id=2589, match_date="2025-05-11"),
    Target(url="https://www.gsp.ro/fotbal/liga-1/farul-uta-arad-superliga-etapa8-live-802114.html", team_id=2589, match_date="2025-05-18"),
    Target(url="https://www.gsp.ro/fotbal/liga-1/live-uta-arad-gloria-buzau-superliga-play-out-etapa-9-804504.html", team_id=2589, match_date="2025-05-25"),
]


def slugify(value: str, max_len: int = 60) -> str:
    normalised = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    normalised = re.sub(r"[^a-zA-Z0-9]+", "-", normalised).strip("-").lower()
    return normalised[:max_len] or "article"


def clean_text(raw: str) -> str:
    lines = [line.strip() for line in raw.splitlines()]
    kept: list[str] = []
    for line in lines:
        if not line:
            continue
        if any(p.match(line) for p in BOILERPLATE_PATTERNS):
            continue
        if len(line) < 3:
            continue
        kept.append(line)

    text = "\n\n".join(kept)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_article_body(html: str) -> tuple[str, str]:
    """Return (title, body_text). Falls back to all <p> if no <article>."""
    soup = BeautifulSoup(html, "html.parser")

    for bad in soup(["script", "style", "noscript", "iframe", "form", "aside", "nav", "footer"]):
        bad.decompose()

    title_tag = soup.find(["h1"]) or soup.find("title")
    title = title_tag.get_text(strip=True) if isinstance(title_tag, Tag) else ""

    # Try div.article-body first — GSP uses it as the primary content container
    container: Tag | None = soup.select_one("div.article-body")
    if container is None:
        container = soup.find("article")
    if container is None:
        for selector in ("div.post-content", "div.entry-content", "main"):
            found = soup.select_one(selector)
            if isinstance(found, Tag):
                container = found
                break
    if container is None:
        container = soup.body if isinstance(soup.body, Tag) else None

    if container is None:
        return title, ""

    paragraphs = [p.get_text(" ", strip=True) for p in container.find_all("p")]
    body = "\n".join(paragraphs)
    return title, clean_text(body)


def fetch(client: httpx.Client, url: str) -> str | None:
    try:
        resp = client.get(url, follow_redirects=True, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
    except (httpx.HTTPError, httpx.TimeoutException) as exc:
        print(f"  ! fetch failed for {url}: {exc}", file=sys.stderr)
        return None
    return resp.text


def write_article(target: Target, title: str, body: str) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    url_hash = sha1(target.url.encode("utf-8")).hexdigest()[:8]
    stem = f"{target.team_id}_{target.match_date}_{slugify(title)}_{url_hash}"
    txt_path = OUTPUT_DIR / f"{stem}.txt"
    meta_path = OUTPUT_DIR / f"{stem}.meta.json"

    txt_path.write_text(body, encoding="utf-8")
    meta_path.write_text(
        json.dumps(
            {
                "team_id": target.team_id,
                "source_url": target.url,
                "match_date": target.match_date,
                "title": title,
                "scraped_at": date.today().isoformat(),
                "char_count": len(body),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return txt_path


def run(targets: list[Target]) -> None:
    if not targets:
        print("No targets configured. Edit TARGETS in scrape_media.py.")
        return

    headers = {"User-Agent": USER_AGENT, "Accept-Language": "ro-RO,ro;q=0.9,en;q=0.5"}
    ok = 0
    skipped = 0
    with httpx.Client(headers=headers) as client:
        for i, target in enumerate(targets, 1):
            print(f"[{i}/{len(targets)}] {target.url}")
            html = fetch(client, target.url)
            if html is None:
                skipped += 1
                continue
            try:
                title, body = extract_article_body(html)
            except Exception as exc:  # noqa: BLE001 — never abort the batch
                print(f"  ! parse failed: {exc}", file=sys.stderr)
                skipped += 1
                continue
            if len(body) < 200:
                print(f"  ! body too short ({len(body)} chars), skipping")
                skipped += 1
                continue
            path = write_article(target, title, body)
            print(f"  -> {path.name} ({len(body)} chars)")
            ok += 1

    print(f"\nDone. Saved {ok}/{len(targets)} articles ({skipped} skipped) to {OUTPUT_DIR}")


if __name__ == "__main__":
    run(TARGETS)
