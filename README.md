# 🍳 Recipes — a tiny self-hosted recipe manager

A lightweight recipe collection for your Raspberry Pi. Store recipes with your
own notes/modifications, tag and search them, and use it like an app on your
phone (installable PWA).

- **Backend:** FastAPI + SQLite (single file DB, no external database needed)
- **Frontend:** server-rendered HTML + a sprinkle of vanilla JS (no build step)
- **Footprint:** one container, ~80–120 MB RAM — friendly to a 4 GB Pi already
  running other containers
- **Mobile:** works as a PWA ("Add to Home Screen")

---

## Project layout

```
recipe/
├─ app/
│  ├─ main.py          # FastAPI routes
│  ├─ db.py            # SQLite connection + schema
│  ├─ templates/       # Jinja2 HTML
│  └─ static/          # CSS, JS, PWA manifest, service worker, icon
├─ data/               # SQLite DB lives here (created at runtime, git-ignored)
├─ requirements.txt
├─ Dockerfile
└─ docker-compose.yml
```

---

## Run locally (on your PC, for development)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open http://localhost:8000

---

## Run on the Raspberry Pi (Docker)

The Pi 5 is arm64 and the `python:3.12-slim` base image is multi-arch, so this
builds natively on the Pi.

```bash
# copy the project to the Pi, then:
cd recipe
docker compose up -d --build
```

Now open `http://<pi-ip>:8000` from any device on your LAN.
Your data is stored in `./data/recipes.db` (mounted as a volume, so it survives
rebuilds — back this file up and you've backed up all your recipes).

To update after code changes:

```bash
docker compose up -d --build
```

---

## Add it to your iPhone home screen (PWA)

1. Open the site in **Safari** (must be Safari on iOS).
2. Tap **Share → Add to Home Screen**.
3. It launches full-screen like a native app.

> A native App Store app can come later. Because the app is a normal web app,
> the same backend can serve a future native shell (or a React Native / Capacitor
> wrapper) without rewriting the server.

---

## Remote access & security

You mentioned you already use **Tailscale** — that's the easy, secure option.

### Option A — Tailscale (recommended, already what you have)
Tailscale creates an encrypted WireGuard tunnel between your devices. Traffic to
the Pi never touches the public internet, so **plain HTTP over Tailscale is
already end-to-end encrypted**. Just browse to the Pi's Tailscale IP:

```
http://100.x.y.z:8000
```

Nothing else to expose, no ports opened on your router. This is genuinely secure
for a personal app.

### Option B — Add real HTTPS (nice-to-have)
If you later want a proper `https://recipes.yourname.ts.net` with a valid cert:

1. **Tailscale HTTPS** (simplest): enable MagicDNS + HTTPS certs in the Tailscale
   admin console, then run on the Pi:
   ```bash
   tailscale serve https / http://localhost:8000
   ```
   Tailscale terminates TLS with a real Let's Encrypt cert on your `*.ts.net`
   name — no reverse proxy to manage.

2. **Reverse proxy** (if you also expose other services): put
   [Caddy](https://caddyserver.com/) in front — it auto-provisions HTTPS certs.
   Example `Caddyfile`:
   ```
   recipes.example.com {
       reverse_proxy localhost:8000
   }
   ```

**Recommendation:** stay on Tailscale (Option A) to start. Add Tailscale HTTPS
(Option B.1) when you want the padlock and to silence any "not secure" warnings.
Only expose it to the public internet if you truly need to — and if so, add
authentication first.

---

## Notes / roadmap ideas

- The recipe DB is a single `recipes` table with free-text ingredients and
  instructions (one item per line). Simple, fast, easy to edit — perfect for a
  personal collection of hundreds of recipes.
- Easy future additions: import a recipe from a URL, photo upload, meal planner,
  shopping list, login/auth if you ever expose it publicly.
