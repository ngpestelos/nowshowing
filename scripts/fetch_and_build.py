#!/usr/bin/env python3
"""Fetch today's schedules from ClickTheCity and rebuild index.html."""
import datetime
import html
import json
import pathlib
import urllib.request
import zoneinfo

THEATERS = [
    "robinsons-galleria-ortigas",
    "power-plant-mall",
    "ortigas-cinemas-estancia",
]

API_URL = "https://clickthecity.com/api/movies/theater/{slug}?date={date}"
REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
MANILA = zoneinfo.ZoneInfo("Asia/Manila")


def fetch_theater(slug: str, date: str) -> dict | None:
    url = API_URL.format(slug=slug, date=date)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.load(resp)
    except Exception as e:
        print(f"WARN: failed to fetch {slug}: {e}")
        return None
    if not data.get("status"):
        print(f"WARN: {slug} returned status=false")
        return None
    return data


def render_theater(data: dict, date: str) -> str:
    theater = data["theater"]
    movies = {m["movieId"]: m for m in data["now_showing"]}
    rows = []
    for s in data["schedules"]:
        if s["date"] != date:
            continue
        movie = movies.get(s["movieId"], {})
        title = html.escape(movie.get("title", f"Movie #{s['movieId']}"))
        rating = html.escape(movie.get("mtrcb_rating", ""))
        runtime = html.escape(movie.get("running_time", ""))
        cinema = html.escape(s["theaterName"].lstrip("- ").strip())
        showtimes = ", ".join(s["showtimes"])
        rows.append(
            f'<tr><td class="title" data-label="Movie">{title}</td>'
            f'<td class="meta" data-label="Rating / Runtime">{rating} &middot; {runtime}</td>'
            f'<td class="cinema" data-label="Cinema">{cinema}</td>'
            f'<td class="showtimes" data-label="Showtimes">{showtimes}</td></tr>'
        )
    if not rows:
        rows_html = '<tr><td colspan="4" class="empty">No schedule available today.</td></tr>'
    else:
        rows_html = "\n".join(rows)
    name = html.escape(theater["name"])
    address = html.escape(theater["address"])
    return f"""
    <section class="theater">
      <h2>{name}</h2>
      <p class="address">{address}</p>
      <table>
        <thead><tr><th>Movie</th><th>Rating / Runtime</th><th>Cinema</th><th>Showtimes</th></tr></thead>
        <tbody>
        {rows_html}
        </tbody>
      </table>
    </section>
    """


def build(date: str) -> str:
    sections = []
    for slug in THEATERS:
        data = fetch_theater(slug, date)
        if data is None:
            sections.append(
                f'<section class="theater theater-error"><p>Could not load schedule for '
                f'<code>{html.escape(slug)}</code> today.</p></section>'
            )
            continue
        sections.append(render_theater(data, date))
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
  <p>Source: <a href="https://clickthecity.com">ClickTheCity</a>. Refreshed daily.</p>
</footer>
</body>
</html>
"""


def main():
    date = datetime.datetime.now(MANILA).strftime("%Y-%m-%d")
    html_out = build(date)
    (REPO_ROOT / "index.html").write_text(html_out, encoding="utf-8")
    print(f"Wrote index.html for {date}")


if __name__ == "__main__":
    main()
