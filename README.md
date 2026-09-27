# Now Showing

Static, auto-refreshing page of today's movie schedules for a small list of Metro Manila and Iloilo theaters. Published at [nowshowing.ngpcloud.org](https://nowshowing.ngpcloud.org) via Cloudflare Workers (static assets).

## How it works

- `scripts/fetch_and_build.py` pulls today's schedule for each theater from **ClickTheCity** (`www.clickthecity.com`): per-screen breakdown, rating and runtime.
- If ClickTheCity fails for a theater, that theater shows a "Could not load schedule" notice.
- ClickTheCity is the only source. The search for a second, independent source is tracked in [#8](https://github.com/ngpestelos/nowshowing/issues/8).
- Each movie title links to IMDb (via IMDb's public suggestion-search endpoint, no API key). A remake/re-release exact-title-colliding with a decades-old original (e.g. "Moana" 2026 vs. 2016 vs. 1959) isn't flagged as uncertain — only one candidate is recent enough to be the one actually in cinemas. Genuine collisions (two *different* current-era films sharing an exact title, e.g. two 2025/2026 movies both called "The Furious") link to IMDb's top-ranked match but are marked "best guess" (dashed border, tooltip) rather than claimed as certain.
- Per-seat ticket price, where verified: `THEATER_PRICING` in the script holds a **dated snapshot** (not a live daily fetch) sourced directly from each operator's own booking checkout page. Ortigas Cinemas Estancia and Power Plant Mall both run the Vista Entertainment ticketing platform (`ortigascinemas.com` / `tickets.powerplantcinema.com`) — confirmed by pulling a real session's price. A cinema room's *name* is classified into regular/premium tier by keyword (`screening room`, `vip`, `premiere`, `dolby atmos`, `imax`); Power Plant's premium rooms show "Price unavailable" since only the regular tier was verified there — not guessed. Robinsons Movieworld (Robinsons Galleria Ortigas, Robinsons Place Manila) runs a different, custom, reCAPTCHA-gated booking backend; this script won't script around a CAPTCHA, so those theaters show "Price unavailable" rather than a fabricated number.
- A GitHub Actions workflow (`.github/workflows/refresh.yml`) runs the script 3x daily (06:00, 13:00, 19:00 Asia/Manila) and pushes `public/index.html` if it changed. Cloudflare auto-deploys on every push to `master`.
- The page header has a **city selector** (Metro Manila / Iloilo). Each theater entry carries a required `city` field; the build emits `data-city` on sections and cinema options so the client filter (and schedule refresh) stays correct. Default is Metro Manila; choice sticks via `localStorage`, and non-default city is also reflected in `?city=`.
- No build step, no framework, no dependencies — stdlib-only `fetch_and_build.py` writes `public/index.html` + `public/style.css`. `wrangler.jsonc` points Cloudflare's asset server at `./public` only — everything else in the repo (scripts, README, workflow) stays private, not publicly served.

## Theaters tracked

| Theater | ClickTheCity slug |
|---|---|
| Robinsons Galleria Ortigas | `robinsons-galleria-ortigas` |
| Power Plant Mall (Rockwell) | `power-plant-mall` |
| Ortigas Cinemas Estancia (Capitol Commons) | `ortigas-cinemas-estancia` |
| Robinsons Place Manila (Ermita) | `robinsons-place-manila` |
| SM Megamall (Mandaluyong) | `sm-megamall` |
| SM North EDSA (Quezon City) | `sm-city-north-edsa` |
| The Podium (Ortigas Center) | `the-podium` |
| Greenbelt 3 (Ayala Center) | `greenbelt-3` |
| Glorietta 4 | `glorietta-4` |
| Trinoma | `trinoma-mall` |
| UP Town Center | `up-town-center` |
| SM City Iloilo | `sm-city-iloilo` |
| Robinsons Place Iloilo | `robinsons-place-iloilo` |
| Robinsons Place Jaro | `robinsons-place-jaro` |
| Festive Walk Iloilo | `festive-walk-iloilo` |
| Vista Mall Iloilo | `vista-mall-iloilo` |

### Adding new theaters

Add entries to `THEATERS` in `scripts/fetch_and_build.py`:

```python
{
    "ctc_slug": "sm-city-iloilo",
    "fallback_name": "SM City Iloilo",
    "city": "iloilo",  # required: "metro-manila" or "iloilo"
}
```

1. **Find ClickTheCity slug:** Probe `https://www.clickthecity.com/api/movies/theater/<guess>?date=YYYY-MM-DD` (`status: true` means it's valid).
2. **Set `fallback_name`** to ClickTheCity's own theater name. It labels the theater's error notice when ClickTheCity fails.

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
