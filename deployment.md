# Deploying the Recipe App — the complete beginner walkthrough

> The goal: after reading this once, you can deploy **without asking anyone**.
> Three targets: Render (public demo), Pi + Tailscale (private daily use),
> Pi + Cloudflare Tunnel (public, your own domain).

---

## 1. Mental model first

Six "places" are involved. Deployment（部署）is nothing more than **copying your
code to another computer and starting it there**.

| Place | Whose computer? | What lives there | You touch it via |
|---|---|---|---|
| Your PC | yours | the code you edit | VS Code, terminal |
| GitHub | Microsoft's | a **copy** of your code (the hub) | `git push` |
| Render | Render's | a **running copy** of your app (demo) | their website |
| Your Pi | yours | the **real** app + your real recipe data | SSH / keyboard |
| Tailscale network | virtual | an encrypted "invisible cable" between *your* devices | Tailscale app |
| Cloudflare | Cloudflare's | the public front door to your Pi | their website |

> **The single key insight:** GitHub is the hub. Your PC *pushes* code up to it;
> Render and the Pi each *pull* code down from it. You never copy files directly
> from PC → server. If something is wrong on a server, fix it on your PC,
> push, and pull again.

```
                 ┌──────────┐
   git push ───► │  GitHub  │ ◄─── git pull (Pi)
                 └────┬─────┘
                      │ auto-pull on every push
                      ▼
                  ┌────────┐
                  │ Render │  ➜ https://recipe-manager-xxxx.onrender.com
                  └────────┘
```

---

## 2. What each thing IS

| Item | Literal meaning (中文 gloss) | What it touches | One-sentence job |
|---|---|---|---|
| Render | cloud platform（云平台） | your GitHub repo | Runs your app on their servers and gives you a free `https://` link. |
| Docker | container engine（容器引擎） | Dockerfile, images | Packs app + Python + dependencies into one box that runs identically anywhere. |
| Dockerfile | build recipe（构建配方） | the image build | Step-by-step instructions to build that box. |
| docker compose | multi-container tool（编排工具） | docker-compose.yml | Starts the box with the right port, volume and .env, in one command. |
| `.env` | environment file（环境变量文件） | SECRET_KEY, SMTP_* | Holds secrets; never enters git (it is in `.gitignore`). |
| Tailscale | private mesh VPN（私有虚拟网络） | all your devices | Gives each device a private `100.x.y.z` address only you can reach. |
| Cloudflare Tunnel | reverse tunnel（反向隧道） | the Pi ↔ Cloudflare | Lets the public reach your Pi **without opening router ports**. |
| domain | internet name（域名） | Cloudflare DNS | Human-readable address (`recipes.you.com`) that points at the tunnel. |
| HTTPS | encrypted HTTP（加密传输） | browser ↔ server | The padlock; Render/Cloudflare provide it automatically. |

---

## 3. How it WORKS internally

| Item | What actually happens under the hood | 中文说明 |
|---|---|---|
| `git push` | Uploads your new commits to GitHub over HTTPS. | 把本地提交上传到 GitHub |
| Render deploy | Render clones your repo, sees the Dockerfile, runs `docker build`, then starts the container and injects env vars (incl. `PORT`). | Render 拉代码→构建镜像→注入环境变量→启动容器 |
| `Dockerfile` CMD | `uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}` — uses Render's `PORT` if given, else 8000. | 优先用 Render 的端口，否则用 8000 |
| `docker compose up` | Builds the image on the Pi, mounts `./data` into the box (so the SQLite file survives rebuilds), reads `.env`. | 挂载数据目录，数据库不会因重建而丢失 |
| `tailscale up` | Registers the Pi to your account; every device gets a fixed private IP; traffic is WireGuard-encrypted device-to-device. | 设备间点对点加密，无需路由器设置 |
| `cloudflared` | The Pi makes an **outgoing** connection to Cloudflare and keeps it open; visitor traffic flows backwards through it. | 树莓派主动连出去，公网流量沿隧道回来 |

Key flags you will actually meet:

| Flag | 中文 | Meaning | What happens if I omit it |
|---|---|---|---|
| `-d` (compose up) | 后台运行 | run detached, in the background | terminal is blocked; closing it stops the app |
| `--build` | 重新构建 | rebuild the image from current code | old code keeps running after you `git pull` |
| `-y` (apt) | 自动确认 | auto-answer "yes" | apt stops and asks you interactively |
| `-4` (tailscale ip) | 只要 IPv4 | print only the IPv4 address | you also get a long IPv6 you don't need |

---

## 4. WHY use it — what breaks if I skip it

| Item | Why it exists | If you skip it… | 中文 |
|---|---|---|---|
| GitHub as hub | one source of truth | PC and Pi versions drift apart; "works on my machine" chaos | 版本不一致 |
| Docker | identical environment everywhere | app works on your PC (Python 3.12) but crashes on the Pi (different Python/libs) | 环境不一致导致崩溃 |
| `.env` outside git | secrets stay private | your `SECRET_KEY` is public on GitHub → anyone can forge login cookies | 密钥泄露，登录可被伪造 |
| fresh SECRET_KEY per server | limits damage | one leaked key unlocks *all* your deployments | 一处泄露，处处失守 |
| volume `./data` | data outlives the container | every redeploy **deletes all recipes** | 重建容器=数据清零 |
| Tailscale | encryption + no exposure | plain HTTP over the public internet → passwords readable by anyone in between | 明文密码被窃听 |
| Cloudflare Tunnel | no open router ports | port-forwarding exposes your home network to constant bot attacks | 家庭网络暴露给扫描机器人 |
| Cloudflare Access policy | gate before the app | the whole internet can reach your login page and brute-force it | 公网可无限尝试登录 |

---

## 5. How they STICK TOGETHER

```
 YOUR PC                GITHUB               RENDER (demo)
 ┌──────────┐  push   ┌─────────┐  auto    ┌──────────────────┐
 │ edit code├────────►│  repo   ├─────────►│ build ► run      │──► https://xxx.onrender.com
 └──────────┘         └────┬────┘          │ env: SECRET_KEY  │        (HTTPS by Render)
                           │ pull          └──────────────────┘
                           ▼
 YOUR PI ──────────────────────────────────────────────────────
 ┌────────────────────────────────────────────┐
 │ git pull ► docker compose up -d --build    │
 │ .env (SECRET_KEY, SMTP)   data/recipes.db  │
 └────────┬──────────────────────┬────────────┘
          │ tailscale (private)  │ cloudflared (public)
          ▼                      ▼
   http://100.x.y.z:8000   https://recipes.you.com
   (only your devices)     (world, behind Access check)
```

**In one sentence:** you push code to GitHub; Render rebuilds automatically and
serves a public demo, while the Pi pulls the same code and serves your real data —
privately via Tailscale and/or publicly via a Cloudflare Tunnel.

**Where things fail *silently*:**

| Silent failure | Symptom | Cause |
|---|---|---|
| pushed but Pi never pulled | Pi runs old version forever | there is **no auto-update on the Pi** — pulling is manual |
| `compose up` without `--build` | Pi pulled new code but behaves old | image was not rebuilt |
| forgot env var on Render | app crashes only *there* | Render doesn't read your local `.env` |
| service worker cache | browser shows old UI after deploy | hard-refresh (Ctrl+Shift+R) or bump the SW cache version |

---

## 6. The shortcut

**One-time-only (never again):** Render signup + service creation, `tailscale up`
on each device, Cloudflare domain + tunnel + Access policy, creating `.env` on the Pi.

**Day-to-day — this is ALL you actually type:**

```powershell
# on your PC, after changing code:
git add -A
git commit -m "describe the change"
git push          # ← Render redeploys by itself, nothing else to do
```

```bash
# on the Pi, to take the new version (only when you want to update it):
cd ~/recipe-manager
git pull
sudo docker compose up -d --build
```

Honest notes: you can drop Walkthrough 3 entirely if you don't care about a custom
domain — Tailscale already covers personal use. And you never "maintain" Render;
it redeploys on every push.

---

## 7. My independent checklist

```bash
############################################
# A. RENDER (public demo) — one-time setup #
############################################
# 1. render.com → Get Started → sign in with GitHub → Authorize
# 2. + New → Web Service → Connect "recipe-manager"
# 3. Language: Docker (auto) | Region: Frankfurt | Instance: Free
# 4. Add env var:  SECRET_KEY = output of:
#      python -c "import secrets; print(secrets.token_hex(32))"
# 5. Deploy Web Service → wait for "Your service is live"
# Limits: sleeps after ~15 min idle; DB resets on redeploy (demo only!)

#############################################
# B. PI + TAILSCALE (private) — first time  #
#############################################
sudo apt update && sudo apt install -y docker.io docker-compose-plugin
git clone https://github.com/<YOUR-USERNAME>/recipe-manager.git
cd recipe-manager
cp .env.example .env
python3 -c "import secrets; print(secrets.token_hex(32))"   # paste into .env
nano .env                                                   # Ctrl+O save, Ctrl+X exit
sudo docker compose up -d --build
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up            # open the printed link, log in
tailscale ip -4              # note the 100.x.y.z address
# phone: install Tailscale app, same account, then open http://100.x.y.z:8000
# iPhone: Safari → Share → Add to Home Screen

#############################################
# C. UPDATE the Pi after a git push         #
#############################################
cd ~/recipe-manager && git pull && sudo docker compose up -d --build

#############################################
# D. WHEN THINGS GO WRONG                   #
#############################################
sudo docker compose logs --tail 50     # read the app's error output
sudo docker compose restart            # turn it off and on again
sudo docker compose down && sudo docker compose up -d --build   # full rebuild
git log --oneline                      # find the last good commit...
git revert <commit-hash>               # ...undo a bad commit SAFELY (makes a new commit)
cp data/recipes.db data/recipes.backup.db    # back up ALL your recipes (one file!)

#############################################
# E. CLOUDFLARE TUNNEL (optional, public)   #
#############################################
# 1. Buy domain (porkbun.com) → add to Cloudflare (Free plan)
#    → change nameservers at Porkbun to Cloudflare's two
# 2. Cloudflare → Zero Trust → Networks → Tunnels → Create → "Cloudflared"
# 3. Copy the Debian/arm64 install command → run on Pi → status "healthy"
# 4. Public hostname: recipes.<yourdomain> → HTTP → localhost:8000
# 5. MUST DO: Zero Trust → Access → Applications → Add → Self-hosted
#    → domain = recipes.<yourdomain> → Allow policy → Emails = your email
```

---

## 「没看懂的话」

- **GitHub 是中枢**：电脑改代码 → `push` 上去；Render 自动拉取，树莓派要**手动** `git pull` + `--build`，否则永远跑旧代码。
- **`.env` 永远不进 git**：每台服务器单独生成自己的 `SECRET_KEY`；泄露一个不会全部沦陷。
- **数据只在树莓派上**：Render 的数据库每次重新部署都会清空，它只是演示；真正的菜谱在 `data/recipes.db`，备份这一个文件就够了。

## Vocabulary

| Word / phrase | 中文 | Example sentence |
|---|---|---|
| deploy / deployment | 部署 | We deploy the app to Render by pushing to GitHub. |
| pull / push | 拉取 / 推送 | The Pi must pull the latest code before rebuilding. |
| environment variable | 环境变量 | `SECRET_KEY` is set as an environment variable, not written in code. |
| volume | 挂载卷 | The `./data` volume keeps the database when the container is rebuilt. |
| tunnel | 隧道 | The Cloudflare tunnel lets visitors reach the Pi without open ports. |
