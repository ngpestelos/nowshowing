# Now Showing

Static, auto-refreshing page of today's movie schedules for a small list of Metro Manila theaters. Published at [nowshowing.ngpcloud.org](https://nowshowing.ngpcloud.org) via Cloudflare Pages.

## How it works

- `scripts/fetch_and_build.py` pulls today's schedule from ClickTheCity's API (`api.clickthecity.com`, no auth) for each theater in `THEATERS` and regenerates `index.html`.
- A GitHub Actions workflow (`.github/workflows/refresh.yml`) runs the script 3x daily (06:00, 13:00, 19:00 Asia/Manila) and pushes `index.html` if it changed. Cloudflare Pages auto-deploys on every push to `master`.
- No build step, no framework — `index.html` + `style.css`.

## Theaters tracked

- Robinsons Galleria Ortigas
- Power Plant Mall (Rockwell)
- Ortigas Cinemas Estancia (Capitol Commons)

Add more by appending a theater slug to `THEATERS` in `scripts/fetch_and_build.py`. Find a slug by trying `https://clickthecity.com/api/movies/theater/<guess>?date=YYYY-MM-DD` — `status: true` means the slug is right.

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
