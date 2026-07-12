# Now Showing

Static, auto-refreshing page of today's movie schedules for a small list of Metro Manila theaters. Published at [nowshowing.ngpcloud.org](https://nowshowing.ngpcloud.org) via Cloudflare Workers (static assets).

## How it works

- `scripts/fetch_and_build.py` pulls today's schedule from **two independent sources** per theater and cross-references them before rendering `index.html`:
  - **ClickTheCity** (`api.clickthecity.com`) — primary, richer per-screen breakdown
  - **popcorn.app** — secondary, sourced from the cinema operators' own booking backends (not a ClickTheCity mirror)
- Each movie gets a cross-check badge: **verified · 2 sources agree** (both list it with matching upcoming showtimes), **ClickTheCity only** (not on popcorn.app's narrower catalog), or **sources disagree** (both list it but showtimes genuinely differ). popcorn.app drops showtimes that have already started today, so the comparison only checks still-upcoming showtimes against it — an elapsed early showing doesn't get flagged as a false mismatch.
- If ClickTheCity fails outright, the page falls back to popcorn.app alone for that theater (flagged, reduced detail — no per-screen breakdown or rating/runtime).
- Each movie title links to IMDb (via IMDb's public suggestion-search endpoint, no API key). A remake/re-release exact-title-colliding with a decades-old original (e.g. "Moana" 2026 vs. 2016 vs. 1959) isn't flagged as uncertain — only one candidate is recent enough to be the one actually in cinemas. Genuine collisions (two *different* current-era films sharing an exact title, e.g. two 2025/2026 movies both called "The Furious") link to IMDb's top-ranked match but are marked "best guess" (dashed border, tooltip) rather than claimed as certain.
- A GitHub Actions workflow (`.github/workflows/refresh.yml`) runs the script 3x daily (06:00, 13:00, 19:00 Asia/Manila) and pushes `public/index.html` if it changed. Cloudflare auto-deploys on every push to `master`.
- No build step, no framework, no dependencies — stdlib-only `fetch_and_build.py` writes `public/index.html` + `public/style.css`. `wrangler.jsonc` points Cloudflare's asset server at `./public` only — everything else in the repo (scripts, README, workflow) stays private, not publicly served.

## Theaters tracked

| Theater | ClickTheCity slug | popcorn.app URL |
|---|---|---|
| Robinsons Galleria Ortigas | `robinsons-galleria-ortigas` | `/ph/robinsons-movieworld/galleria-ortigas/cinema/550` |
| Power Plant Mall (Rockwell) | `power-plant-mall` | `/ph/powerplant/power-plant-mall/cinema/2633` |
| Ortigas Cinemas Estancia (Capitol Commons) | `ortigas-cinemas-estancia` | `/ph/ortigas-cinema/estancia-cinemas/cinema/2766` |
| Robinsons Place Manila (Ermita) | `robinsons-place-manila` | `/ph/robinsons/manila/cinema/552` |

Add more by appending a `{"ctc_slug": ..., "popcorn_url": ...}` entry to `THEATERS` in `scripts/fetch_and_build.py`. Find a ClickTheCity slug by trying `https://clickthecity.com/api/movies/theater/<guess>?date=YYYY-MM-DD` (`status: true` means it's right); find a popcorn.app URL by searching `site:popcorn.app "<mall name>"`.

## Local run

```
python3 scripts/fetch_and_build.py
open public/index.html
```

Dry-run the actual deploy without touching Cloudflare:
```
npx wrangler deploy --dry-run --outdir /tmp/nowshowing-dry-run
```
Should report "Read 2 files from the assets directory .../public" — if it reports more, something outside `public/` is leaking in.

## Deployment (one-time setup)

1. `gh repo create nowshowing --public --source=. --push`
2. Cloudflare dashboard → Workers & Pages → Create application → **Workers** (current Cloudflare onboarding routes static sites through Workers static assets, not the older classic Pages flow) → Connect to Git → select this repo.
   - Build command: leave empty
   - Deploy command: `npx wrangler deploy` (prefilled default — correct, reads `wrangler.jsonc`)
   - `wrangler.jsonc` in this repo already declares `assets.directory: ./public`, so only `public/index.html` + `public/style.css` get served — nothing else in the repo is exposed.
3. Project → Settings → Domains & Routes → add `nowshowing.ngpcloud.org`.
4. DNS (ngpcloud.org zone) → add CNAME `nowshowing` → `<project>.workers.dev` (Cloudflare usually offers to add this automatically in step 3).
