#!/usr/bin/env python3
"""Fetch today's schedules from two independent sources, cross-reference them
for accuracy, and rebuild index.html. ClickTheCity is primary (richer
per-screen detail); popcorn.app is a secondary check sourced from the
cinema operators' own booking backends — a genuinely different data
provider, not a ClickTheCity mirror. Falls back to popcorn.app alone if
ClickTheCity is unreachable.
"""
import datetime
import html
import json
import pathlib
import re
import urllib.request
import zoneinfo

THEATERS = [
    {
        "ctc_slug": "robinsons-galleria-ortigas",
        "popcorn_url": "https://www.popcorn.app/ph/robinsons-movieworld/galleria-ortigas/cinema/550",
    },
    {
        "ctc_slug": "power-plant-mall",
        "popcorn_url": "https://www.popcorn.app/ph/powerplant/power-plant-mall/cinema/2633",
    },
    {
        "ctc_slug": "ortigas-cinemas-estancia",
        "popcorn_url": "https://www.popcorn.app/ph/ortigas-cinema/estancia-cinemas/cinema/2766",
    },
]

CTC_API_URL = "https://clickthecity.com/api/movies/theater/{slug}?date={date}"
REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
MANILA = zoneinfo.ZoneInfo("Asia/Manila")

STUDIO_PREFIXES = ["disney:", "marvel studios'", "marvel studios:", "pixar's", "20th century studios'"]
QUALIFIER_SUFFIXES = [" - live action", " (2d)", " (3d)", " (imax)"]


def normalize_title(title: str) -> str:
    t = title.lower().strip()
    for p in STUDIO_PREFIXES:
        if t.startswith(p):
            t = t[len(p):].strip()
    for s in QUALIFIER_SUFFIXES:
        if t.endswith(s):
            t = t[: -len(s)].strip()
    t = re.sub(r"[^\w\s]", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def natural_sort_key(s: str) -> list:
    """Case-insensitive, numeric-aware sort key so 'Cinema 2' sorts before
    'Cinema 10' instead of after it (plain string sort would put '10' first)."""
    return [int(p) if p.isdigit() else p.lower() for p in re.split(r"(\d+)", s)]


def normalize_time(t: str) -> str:
    t = t.upper().replace(" ", "")
    m = re.match(r"^0?(\d{1,2}):(\d{2})(AM|PM)$", t)
    return f"{m.group(1)}:{m.group(2)}{m.group(3)}" if m else t


IMDB_SUGGESTION_URL = "https://v3.sg.media-imdb.com/suggestion/{first_char}/{query}.json"
_imdb_cache: dict[str, tuple[str, bool] | None] = {}
_imdb_year_hint = None  # set once per build() run from the schedule date


def _fetch_imdb_id(title: str) -> tuple[str, bool] | None:
    """Returns (tt_id, is_ambiguous). A remake/re-release (e.g. "Moana" 2026)
    will exact-title-collide with the decades-old original on IMDb, but that's
    not real ambiguity — only one candidate is recent enough to be the one
    actually in cinemas now. Genuine ambiguity is 2+ RECENT exact-title
    matches (e.g. two different 2025/2026 films both called "The Furious"),
    where we can't tell which one this listing means from the title alone."""
    query = re.sub(r"[^\w\s]", "", title.lower()).strip()
    query = re.sub(r"\s+", "_", query)
    if not query:
        return None
    url = IMDB_SUGGESTION_URL.format(first_char=query[0], query=query)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.load(resp)
    except Exception as e:
        print(f"WARN: IMDb lookup failed for {title!r}: {e}")
        return None
    target = normalize_title(title)
    exact_matches = [
        item for item in data.get("d", [])
        if item.get("qid") == "movie" and normalize_title(item.get("l", "")) == target
    ]
    if not exact_matches:
        return None
    recent = [m for m in exact_matches if isinstance(m.get("y"), int) and m["y"] >= _imdb_year_hint - 1]
    if len(recent) == 1:
        return recent[0]["id"], False
    return exact_matches[0]["id"], True


def imdb_lookup(title: str) -> tuple[str, bool] | None:
    key = normalize_title(title)
    if key not in _imdb_cache:
        _imdb_cache[key] = _fetch_imdb_id(title)
    return _imdb_cache[key]


def imdb_link_html(imdb: tuple | None) -> str:
    if imdb is None:
        return ""
    tt_id, ambiguous = imdb
    if ambiguous:
        cls, tip = "imdb-link imdb-ambiguous", "Best guess — multiple IMDb entries share this title"
    else:
        cls, tip = "imdb-link", "View on IMDb"
    return (
        f' <a class="{cls}" href="https://www.imdb.com/title/{html.escape(tt_id)}/" '
        f'target="_blank" rel="noopener" title="{html.escape(tip)}">IMDb</a>'
    )


def minutes_since_midnight(t: str) -> int:
    """t must already be normalize_time()'d, e.g. '11:40AM'."""
    m = re.match(r"^(\d{1,2}):(\d{2})(AM|PM)$", t)
    if not m:
        return -1
    h, mm, ap = int(m.group(1)), int(m.group(2)), m.group(3)
    if ap == "PM" and h != 12:
        h += 12
    if ap == "AM" and h == 12:
        h = 0
    return h * 60 + mm


# --- ClickTheCity (primary) ---------------------------------------------

def fetch_ctc(slug: str, date: str) -> dict | None:
    url = CTC_API_URL.format(slug=slug, date=date)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.load(resp)
    except Exception as e:
        print(f"WARN: ClickTheCity fetch failed for {slug}: {e}")
        return None
    if not data.get("status"):
        print(f"WARN: ClickTheCity returned status=false for {slug}")
        return None
    return data


def ctc_index(data: dict, date: str) -> dict:
    """normalized_title -> {raw_title, rating, runtime, cinema_rows, showtimes}"""
    movies = {m["movieId"]: m for m in data["now_showing"]}
    index = {}
    for s in data["schedules"]:
        if s["date"] != date:
            continue
        movie = movies.get(s["movieId"], {})
        raw_title = movie.get("title", f"Movie #{s['movieId']}")
        key = normalize_title(raw_title)
        entry = index.setdefault(key, {
            "raw_title": raw_title,
            "rating": movie.get("mtrcb_rating", ""),
            "runtime": movie.get("running_time", ""),
            "cinema_rows": [],
            "showtimes": set(),
        })
        cinema = s["theaterName"].lstrip("- ").strip()
        entry["cinema_rows"].append((cinema, s["showtimes"]))
        entry["showtimes"].update(normalize_time(t) for t in s["showtimes"])
    return index


# --- popcorn.app (secondary/cross-check) --------------------------------

def fetch_popcorn(url: str) -> dict | None:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            page = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"WARN: popcorn.app fetch failed for {url}: {e}")
        return None
    marker = "allShowtimes: "
    start = page.find(marker)
    if start == -1:
        print(f"WARN: popcorn.app page structure changed (no allShowtimes) for {url}")
        return None
    start += len(marker)
    depth = 0
    started = False
    end = None
    for i in range(start, len(page)):
        c = page[i]
        if c == "{":
            depth += 1
            started = True
        elif c == "}":
            depth -= 1
            if started and depth == 0:
                end = i + 1
                break
    if end is None:
        print(f"WARN: popcorn.app JSON brace-matching failed for {url}")
        return None
    try:
        return json.loads(page[start:end])
    except json.JSONDecodeError as e:
        print(f"WARN: popcorn.app JSON parse failed for {url}: {e}")
        return None


def popcorn_index(data: dict, date: str) -> dict:
    """normalized_title -> {raw_title, showtimes}"""
    index = {}
    for movie in data.get(date, []):
        raw_title = movie.get("MovieName", "")
        key = normalize_title(raw_title)
        entry = index.setdefault(key, {"raw_title": raw_title, "showtimes": set()})
        for showtimes in movie.get("Cinemas", {}).values():
            for st in showtimes:
                t = st.get("ShowTime")
                if t:
                    entry["showtimes"].add(normalize_time(t))
    return index


# --- Cross-reference + rendering -----------------------------------------

def cross_check_badge(ctc_times: set, pc_entry: dict | None, now_minutes: int) -> str:
    if pc_entry is None:
        return '<span class="badge badge-unverified" title="Not listed on popcorn.app">ClickTheCity only</span>'
    pc_times = pc_entry["showtimes"]
    if not pc_times:
        return '<span class="badge badge-unverified" title="popcorn.app lists this movie but no showtimes">ClickTheCity only</span>'

    # popcorn.app drops showtimes that have already started today; ClickTheCity
    # always lists the full day. Compare only the still-upcoming subset so an
    # elapsed early showtime doesn't read as a source disagreement.
    upcoming_ctc = {t for t in ctc_times if minutes_since_midnight(t) >= now_minutes}
    elapsed_count = len(ctc_times) - len(upcoming_ctc)
    elapsed_note = f" ({elapsed_count} earlier showtime{'s' if elapsed_count != 1 else ''} already passed)" if elapsed_count else ""

    if upcoming_ctc == pc_times:
        return f'<span class="badge badge-verified" title="Upcoming showtimes match on both sources{elapsed_note}">verified &middot; 2 sources agree</span>'
    overlap = upcoming_ctc & pc_times
    if overlap:
        return (
            f'<span class="badge badge-partial" title="ClickTheCity (upcoming): {", ".join(sorted(upcoming_ctc)) or "none"} '
            f'&#10;popcorn.app: {", ".join(sorted(pc_times))}{elapsed_note}">partial match &middot; {len(overlap)}/{len(upcoming_ctc | pc_times)} upcoming showtimes agree</span>'
        )
    return f'<span class="badge badge-mismatch" title="Both sources list this movie but upcoming showtimes differ{elapsed_note}">sources disagree</span>'


def render_theater(name: str, address: str, ctc: dict, pc: dict | None, source_note: str, now_minutes: int) -> str:
    pc_idx = pc if pc is not None else {}
    rows_data = []
    for key, entry in ctc.items():
        badge = cross_check_badge(entry["showtimes"], pc_idx.get(key), now_minutes)
        imdb = imdb_link_html(imdb_lookup(entry["raw_title"]))
        for cinema, showtimes in entry["cinema_rows"]:
            rows_data.append((cinema, entry["raw_title"], entry["rating"], entry["runtime"], badge, imdb, showtimes))

    # sort by cinema (natural order), then by movie name within each cinema
    rows_data.sort(key=lambda r: (natural_sort_key(r[0]), r[1].lower()))

    rows = []
    for cinema, title, rating, runtime, badge, imdb, showtimes in rows_data:
        rows.append(
            f'<tr><td class="title" data-label="Movie">{html.escape(title)}{imdb} {badge}</td>'
            f'<td class="meta" data-label="Rating / Runtime">{html.escape(rating)} &middot; {html.escape(runtime)}</td>'
            f'<td class="cinema" data-label="Cinema">{html.escape(cinema)}</td>'
            f'<td class="showtimes" data-label="Showtimes">{", ".join(showtimes)}</td></tr>'
        )
    rows_html = "\n".join(rows) if rows else '<tr><td colspan="4" class="empty">No schedule available today.</td></tr>'
    missing_from_ctc = [e["raw_title"] for k, e in pc_idx.items() if k not in ctc]
    extra_note = ""
    if missing_from_ctc:
        extra_note = (
            f'<p class="cross-check-note">popcorn.app also lists '
            f'{", ".join(html.escape(t) for t in missing_from_ctc)} at this theater today — '
            f"not found on ClickTheCity.</p>"
        )
    return f"""
    <section class="theater">
      <h2>{html.escape(name)}</h2>
      <p class="address">{html.escape(address)}</p>
      <p class="source-note">{source_note}</p>
      <table>
        <thead><tr><th>Movie</th><th>Rating / Runtime</th><th>Cinema</th><th>Showtimes</th></tr></thead>
        <tbody>
        {rows_html}
        </tbody>
      </table>
      {extra_note}
    </section>
    """


def render_theater_fallback(name_hint: str, pc: dict) -> str:
    rows = []
    for entry in sorted(pc.values(), key=lambda e: e["raw_title"].lower()):
        title = html.escape(entry["raw_title"])
        imdb = imdb_link_html(imdb_lookup(entry["raw_title"]))
        showtimes = ", ".join(sorted(entry["showtimes"]))
        rows.append(
            f'<tr><td class="title" data-label="Movie">{title}{imdb}</td>'
            f'<td class="meta" data-label="Rating / Runtime">&mdash;</td>'
            f'<td class="cinema" data-label="Cinema">&mdash;</td>'
            f'<td class="showtimes" data-label="Showtimes">{showtimes}</td></tr>'
        )
    rows_html = "\n".join(rows) if rows else '<tr><td colspan="4" class="empty">No schedule available today.</td></tr>'
    return f"""
    <section class="theater">
      <h2>{html.escape(name_hint)}</h2>
      <p class="source-note theater-error">ClickTheCity unavailable today &mdash; showing popcorn.app data only (no per-screen breakdown, ratings/runtime not provided by this source).</p>
      <table>
        <thead><tr><th>Movie</th><th>Rating / Runtime</th><th>Cinema</th><th>Showtimes</th></tr></thead>
        <tbody>
        {rows_html}
        </tbody>
      </table>
    </section>
    """


def build(date: str) -> str:
    global _imdb_year_hint
    _imdb_year_hint = int(date[:4])
    now_dt = datetime.datetime.now(MANILA)
    now_minutes = now_dt.hour * 60 + now_dt.minute
    sections = []
    for theater in THEATERS:
        slug = theater["ctc_slug"]
        ctc_data = fetch_ctc(slug, date)
        pc_raw = fetch_popcorn(theater["popcorn_url"])
        pc_idx = popcorn_index(pc_raw, date) if pc_raw is not None else None

        if ctc_data is not None:
            ctc = ctc_index(ctc_data, date)
            if pc_idx is not None:
                verified = sum(
                    1 for k, e in ctc.items()
                    if pc_idx.get(k) and {t for t in e["showtimes"] if minutes_since_midnight(t) >= now_minutes} == pc_idx[k]["showtimes"]
                )
                source_note = (
                    f"Sources: ClickTheCity + popcorn.app &middot; {verified}/{len(ctc)} movies "
                    f"cross-verified today"
                )
            else:
                source_note = "Source: ClickTheCity only &middot; popcorn.app cross-check unavailable today"
            sections.append(render_theater(ctc_data["theater"]["name"], ctc_data["theater"]["address"], ctc, pc_idx, source_note, now_minutes))
        elif pc_idx is not None:
            sections.append(render_theater_fallback(slug.replace("-", " ").title(), pc_idx))
        else:
            sections.append(
                f'<section class="theater theater-error"><p>Could not load schedule for '
                f'<code>{html.escape(slug)}</code> today (both sources failed).</p></section>'
            )
    now = datetime.datetime.now(MANILA).strftime("%Y-%m-%d %H:%M %Z")
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Now Showing — Metro Manila</title>
<link rel="stylesheet" href="style.css">
</head>
<body>
<header>
  <h1>Now Showing</h1>
  <p class="updated">Schedules for {date} &middot; last updated {now}</p>
</header>
<main>
{''.join(sections)}
</main>
<footer>
  <p>Sources: <a href="https://clickthecity.com">ClickTheCity</a> &amp; <a href="https://www.popcorn.app">popcorn.app</a>, cross-referenced. Refreshed 3x daily.</p>
  <p>Built by <a href="https://ngpestelos.com">ngpestelos.com</a></p>
</footer>
</body>
</html>
"""


def main():
    date = datetime.datetime.now(MANILA).strftime("%Y-%m-%d")
    html_out = build(date)
    (REPO_ROOT / "public" / "index.html").write_text(html_out, encoding="utf-8")
    print(f"Wrote public/index.html for {date}")


if __name__ == "__main__":
    main()
