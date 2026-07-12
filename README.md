# Now Showing

Static, auto-refreshing page of today's movie schedules for a small list of Metro Manila theaters. Published at [nowshowing.ngpcloud.org](https://nowshowing.ngpcloud.org) via Cloudflare Pages.

## How it works

- `scripts/fetch_and_build.py` pulls today's schedule from **two independent sources** per theater and cross-references them before rendering `index.html`:
  - **ClickTheCity** (`api.clickthecity.com`) — primary, richer per-screen breakdown
  - **popcorn.app** — secondary, sourced from the cinema operators' own booking backends (not a ClickTheCity mirror)
- Each movie gets a cross-check badge: **verified · 2 sources agree** (both list it with matching upcoming showtimes), **ClickTheCity only** (not on popcorn.app's narrower catalog), or **sources disagree** (both list it but showtimes genuinely differ). popcorn.app drops showtimes that have already started today, so the comparison only checks still-upcoming showtimes against it — an elapsed early showing doesn't get flagged as a false mismatch.
- If ClickTheCity fails outright, the page falls back to popcorn.app alone for that theater (flagged, reduced detail — no per-screen breakdown or rating/runtime).
- A GitHub Actions workflow (`.github/workflows/refresh.yml`) runs the script 3x daily (06:00, 13:00, 19:00 Asia/Manila) and pushes `index.html` if it changed. Cloudflare Pages auto-deploys on every push to `master`.
- No build step, no framework, no dependencies — stdlib-only `fetch_and_build.py` + `index.html` + `style.css`.

## Theaters tracked

| Theater | ClickTheCity slug | popcorn.app URL |
|---|---|---|
| Robinsons Galleria Ortigas | `robinsons-galleria-ortigas` | `/ph/robinsons-movieworld/galleria-ortigas/cinema/550` |
| Power Plant Mall (Rockwell) | `power-plant-mall` | `/ph/powerplant/power-plant-mall/cinema/2633` |
| Ortigas Cinemas Estancia (Capitol Commons) | `ortigas-cinemas-estancia` | `/ph/ortigas-cinema/estancia-cinemas/cinema/2766` |

Add more by appending a `{"ctc_slug": ..., "popcorn_url": ...}` entry to `THEATERS` in `scripts/fetch_and_build.py`. Find a ClickTheCity slug by trying `https://clickthecity.com/api/movies/theater/<guess>?date=YYYY-MM-DD` (`status: true` means it's right); find a popcorn.app URL by searching `site:popcorn.app "<mall name>"`.

## Local run

```
python3 scripts/fetch_and_build.py
open index.html
```

## Deployment (one-time setup)

1. `gh repo create nowshowing --public --source=. --push`
2. Cloudflare dashboard → Workers & Pages → Create application → Pages → Connect to Git → select this repo. Framework: None. Build command: empty. Output directory: `/`.
3. Pages project → Custom domains → add `nowshowing.ngpcloud.org`.
4. DNS (ngpcloud.org zone) → add CNAME `nowshowing` → `<project>.pages.dev`.
