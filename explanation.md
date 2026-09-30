# How this project works — the complete learning guide

> Read top-to-bottom once, then use it as a reference. Every section is scannable.
> Line numbers were checked against the real code (e.g. `app/db.py:33`).

---

## 1. Mental model first

The app is a **server-rendered website**: the server builds finished HTML pages
and the browser just displays them. There is no React/Vue — a small JS file adds
extra comfort (live search, portion scaling) on top.

| Layer | File(s) | Analogy（比喻） |
|---|---|---|
| 1. Entry / wiring | `app/main.py` | the electrical fuse box |
| 2. Routes (URL handlers) | `app/routes/*.py` | the waiters taking orders |
| 3. Data access | `app/repository.py` | the storeroom clerk |
| 4. Database | `app/db.py` + `data/recipes.db` | the storeroom itself |
| 5. Templates (HTML) | `app/templates/*.html` | the plating of the dish |
| 6. Static assets | `app/static/` | cutlery on every table |
| 7. Cross-cutting helpers | `security.py`, `emailer.py`, `templating.py` | kitchen tools |

> **The single key insight:** every request follows ONE fixed path —
> **route → repository → database → template → HTML** — and each layer only
> talks to its direct neighbour. When you look for a bug, first ask: *which
> layer does this belong to?*

```
Browser ──HTTP──► main.py ──► routes/recipes.py ──► repository.py ──► db.py ──► recipes.db
                                    │                                              
                                    ▼                                              
                            templates/*.html  ──────────► finished HTML ──► Browser
```

---

## 2. The request lifecycle, concretely

What happens when you open `/recipe/2`:

| Step | Where | What happens |
|---|---|---|
| 1 | browser | sends `GET /recipe/2` |
| 2 | `main.py:34` | the `FastAPI` app receives it; SessionMiddleware decodes the signed cookie |
| 3 | `routes/recipes.py:81` `detail()` | path `{rid}` becomes the int `2` |
| 4 | `repository.py:44` `get_recipe()` | runs `SELECT * FROM recipes WHERE id = ?` |
| 5 | `templating.py:12` `_auth_context()` | injects `user` (logged in or `None`) into the template |
| 6 | `templates/recipe.html` | Jinja fills `{{ r.title }}`, loops ingredients |
| 7 | browser | displays HTML; `app.js` activates the portion scaler |

---

## 3. File by file — backend (Python)

### `app/main.py` — wiring only (45 lines)

```python
load_dotenv()                      # read .env into os.environ FIRST
init_db()                          # create tables if missing
app = FastAPI(title="Recipes")     # the application object  (main.py:34)
app.add_middleware(SessionMiddleware, secret_key=..., same_site="lax", max_age=30 days)
app.mount("/static", StaticFiles(...))   # serve css/js/icons from disk
app.include_router(recipes.router)       # plug in the three route modules
```

| Line(s) | Concept | Why |
|---|---|---|
| `load_dotenv()` before other imports use env | order matters（顺序重要） | `SECRET_KEY` must exist before `get_secret_key()` runs |
| `SessionMiddleware` | signed cookie（签名 Cookie） | "logged in" state that the client cannot forge |
| `include_router` | modularity | keeps main.py at ~45 lines instead of 240 |

### `app/db.py` — connection + schema

| Where | What | Explanation |
|---|---|---|
| `db.py:33` `DB_PATH` | `.../data/recipes.db` | resolved relative to the source file, so it works from any working directory |
| `db.py:39` `SCHEMA` | 3 × `CREATE TABLE IF NOT EXISTS` | safe to run on EVERY startup — creates once, no-op afterwards（幂等） |
| `db.py:74` `get_db()` | opens a connection | `row_factory = sqlite3.Row` → access columns by name: `row["title"]` |
| inside `get_db()` | `PRAGMA journal_mode=WAL` | lets reads happen during a write; fewer "database is locked" errors |
| `db.py:93` `init_db()` | runs the schema | called once in main.py at startup |

The three tables:

| Table | Purpose | Interesting columns |
|---|---|---|
| `recipes` | one row per recipe | `ingredients` = one item per line; `tags` = comma-separated string |
| `users` | one row per account | `email UNIQUE COLLATE NOCASE` (case-insensitive), `password_hash`, `verified` |
| `email_codes` | pending verification code | `code_hash` (sha256, never the code itself), `expires_at`, `attempts` |

> Design note: ingredients as plain text (not a separate table) is a deliberate
> trade-off — simple code, easy editing. "Normalize it" is the first step if the
> app ever becomes multi-user at scale.

### `app/repository.py` — every SQL query lives here

| Function | Line | SQL idea |
|---|---|---|
| `search_recipes(q, tag)` | :21 | builds `WHERE` clauses dynamically, **always** with `?` placeholders |
| `get_recipe(rid)` | :44 | single `SELECT ... WHERE id = ?` |
| `create_recipe(values)` | :52 | `INSERT`, returns `cur.lastrowid` (the new id) |
| `update_recipe(rid, values)` | :66 | `UPDATE ... updated_at=datetime('now')` |
| `delete_recipe(rid)` | :78 | `DELETE` |
| `all_tags()` | :86 | splits all comma-strings in Python, de-duplicates with a `set` |
| `get_user_by_email/id` | :106/:113 | login lookups |
| `set_email_code` | :142 | SQLite **UPSERT**: `ON CONFLICT(user_id) DO UPDATE` — one pending code per user |
| `get_valid_email_code` | :156 | validity enforced *in SQL*: `expires_at > datetime('now') AND attempts < 5` |

**The security rule of this file:** user input NEVER goes into the SQL string.

```python
# repository.py:27 — CORRECT: ? placeholders, values passed separately
clauses.append("(title LIKE ? OR ingredients LIKE ? OR tags LIKE ? OR description LIKE ?)")
params += [like, like, like, like]
# WRONG (SQL injection): f"... WHERE title LIKE '%{q}%'"
```

### `app/security.py` — passwords and sessions

| Function | Line | Under the hood | 中文 |
|---|---|---|---|
| `hash_password` | :21 | bcrypt: slow on purpose + random salt per password | 慢哈希+随机盐 |
| `verify_password` | :25 | re-hashes the attempt and compares | 验证密码 |
| `get_secret_key` | :32 | env var `SECRET_KEY` → else a key file next to the DB | 会话签名密钥 |
| `current_user` | :51 | reads `user_id` from the session cookie → fetches the user row | 当前登录用户 |

Why bcrypt and not sha256 for passwords? sha256 is *fast* — an attacker can try
billions per second. bcrypt is deliberately slow (~100ms), making brute force
impractical. (sha256 **is** fine for the 6-digit email codes because they also
expire in 15 min and allow only 5 attempts.)

### `app/emailer.py` — sending mail

| Function | Line | Behaviour |
|---|---|---|
| `send_email` | :15 | no `SMTP_HOST` set → **dev mode**: prints to console. Otherwise SMTP with STARTTLS (port 587) or SSL (port 465) |
| `send_verification_code` | :49 | formats the 6-digit code email |

### `app/templating.py` — shared Jinja engine

```python
def _auth_context(request):          # templating.py:12
    return {"user": current_user(request)}
templates = Jinja2Templates(directory=..., context_processors=[_auth_context])
```

A **context processor** runs before every template render and injects `user`
automatically — so no route needs to pass it manually, and `base.html` can always
check `{% if user %}`.

---

## 4. File by file — routes

### `app/routes/recipes.py` — recipe pages

| Route | Line | Method + URL | Job |
|---|---|---|---|
| `index` | :17 | GET `/` | search (`?q=`), tag filter (`?tag=`); `?partial=1` returns only the list fragment for live search |
| `new_form` / `create` | :44/:54 | GET/POST `/recipe/new` | blank form / insert row |
| `detail` | :81 | GET `/recipe/{rid}` | one recipe page |
| `edit_form` / `update` | :90/:103 | GET/POST `/recipe/{rid}/edit` | pre-filled form / update row |
| `delete` | :130 | POST `/recipe/{rid}/delete` | remove |

Two patterns worth memorising:

| Pattern | Code | Why |
|---|---|---|
| guard clause（守卫语句） | `if current_user(request) is None: return RedirectResponse("/login", 303)` | all write routes are login-protected; reads stay public |
| Post/Redirect/Get | `return RedirectResponse(f"/recipe/{rid}", status_code=303)` after POST | pressing F5 after saving does NOT re-submit the form |

### `app/routes/auth.py` — login / register / verify

| Route | Line | Flow |
|---|---|---|
| `login` | :51 | check password → verified? log in. Not verified? send code → `/verify` |
| `register` | :76 | validate → `create_user` → send code → `/verify` (NOT logged in yet) |
| `verify` | :116 | compare sha256 of typed code with stored hash → `mark_verified` → log in |
| `resend` | :141 | new code for the pending user |
| `logout` | :158 | `request.session.clear()` |

Security details baked in:

| Detail | Where | Prevents |
|---|---|---|
| same error for unknown email & wrong password | auth.py:51 `login` | attackers probing which emails exist |
| `secrets.compare_digest` | auth.py:116 `verify` | timing attacks（计时攻击） |
| `pending_uid` ≠ `user_id` in session | `_start_verification` :36 | being "half logged in" before verifying |
| 5-attempt cap + 15-min expiry | repository.py:156 | brute-forcing 000000–999999 |

### `app/routes/pwa.py` — installable-app plumbing

`/manifest.webmanifest` and `/sw.js` must be served from the **site root** (not
`/static/`) so the service worker may control the whole site — that's why they
get their own routes with explicit `media_type`.

---

## 5. File by file — frontend

### `app/templates/` (Jinja2)

| Template | Extends | Shows |
|---|---|---|
| `base.html` | — | shared shell: `<head>`, PWA tags, topbar (`{% if user %}` → +Add/Logout, else Login), `{% block content %}` |
| `index.html` | base | search box, tag chips, includes `partials/list.html` |
| `partials/list.html` | — | ONLY the recipe cards — also returned alone for live search (`?partial=1`) |
| `recipe.html` | base | detail page; portion scaler UI; Edit/Delete only `{% if user %}` |
| `form.html` | base | one form for BOTH new and edit: `r=None` → blank, `r=row` → pre-filled |
| `login/register/verify.html` | base | auth pages; `verify` uses `autocomplete="one-time-code"` so iPhones autofill the code |

Jinja syntax cheat-sheet:

| Syntax | Meaning | Example in repo |
|---|---|---|
| `{{ x }}` | print value (auto-HTML-escaped → XSS-safe) | `{{ r.title }}` |
| `{% if %}...{% endif %}` | condition | `{% if user %}` in base.html |
| `{% for %}` | loop | ingredients list in recipe.html |
| `{% extends %}` / `{% block %}` | inheritance | every page fills base.html's `content` block |
| `{% include %}` | paste another template | index.html includes the list partial |

### `app/static/js/app.js` — the only JavaScript (~110 lines)

| Part | Lines | How it works |
|---|---|---|
| service-worker registration | top | enables offline/installable behaviour |
| live search | middle | on typing (debounced 200 ms): `fetch("/?q=...&partial=1")` → replace `#recipe-list`'s HTML. The *server* still renders — JS only swaps the fragment |
| portion scaler | bottom | reads `data-original` from each `<li>`, parses the leading quantity (`2`, `1.5`, `1/2`, `1 1/2`, `½`), multiplies, re-formats (`0.5` → `½`). Always recomputes from the original → factors never compound |

### `app/static/js/sw.js`, `manifest.webmanifest`, `style.css`

| File | Job |
|---|---|
| `sw.js` | service worker: caches the app shell for offline use |
| `manifest.webmanifest` | name, icon, colours → makes "Add to Home Screen" behave like an app |
| `style.css` | plain CSS with variables (`--accent`, `--radius`) defined at the top — change the theme in one place |

---

## 6. File by file — infrastructure

| File | Job | Key detail |
|---|---|---|
| `requirements.txt` | Python dependencies, pinned versions | reproducible installs（可复现） |
| `Dockerfile` | build recipe for the container | CMD uses `${PORT:-8000}` → works on Render AND the Pi |
| `docker-compose.yml` | run config for the Pi | `./data` volume = DB survives rebuilds; `env_file: .env` |
| `.env` / `.env.example` | secrets / committed template | `.env` is git-ignored |
| `.gitignore` | keeps junk & secrets out of git | `data/`, `.env`, `__pycache__`, `*.db` |
| `.dockerignore` | keeps junk out of the image | smaller, faster builds |

---

## 7. How it STICKS TOGETHER (failure map)

```
            ┌─ templates missing a var ──► Jinja error page (loud)
            │
Browser ─► route ─► repository ─► SQLite
   ▲          │          │
   │          │          └─ bad SQL → exception (loud)
   │          └─ forgot login guard → SILENT security hole
   │
   ├─ stale service-worker cache → SILENTLY shows old UI  (Ctrl+Shift+R)
   └─ JS error in app.js → page still works, scaler/search SILENTLY dead (F12 console)
```

The three *silent* failure spots are the ones to remember: a missing login guard,
a stale service-worker cache, and a JS exception.

---

## 8. Answers you'll want later

**"Where do I add a new page?"**
1. Route function in `app/routes/` (or a new module + `include_router` in main.py)
2. Query in `repository.py` if it needs data
3. Template in `app/templates/` extending base.html

**"Where do I add a new field to recipes?"**
1. `db.py` SCHEMA (new installs) + a one-off `ALTER TABLE` for your existing DB
2. `repository.py:15` `FIELDS` tuple
3. `form.html` input + `routes/recipes.py` `Form(...)` parameter
4. show it in `recipe.html`

---

## 「没看懂的话」

- **一条固定链路**：路由 → repository → 数据库 → 模板 → HTML。找 bug 先判断在哪一层，别到处乱找。
- **写操作全部有守卫**：`if current_user(request) is None → redirect /login`；读操作公开。忘加守卫 = 无声的安全漏洞。
- **模板自动有 `user`**：`templating.py` 的 context processor 每次渲染都注入，所以 `base.html` 直接 `{% if user %}` 就行，路由不用传。

## Vocabulary

| Word / phrase | 中文 | Example sentence |
|---|---|---|
| server-rendered | 服务端渲染 | This app is server-rendered: the server sends finished HTML. |
| middleware | 中间件 | SessionMiddleware runs before every route and decodes the cookie. |
| placeholder (`?`) | 占位符 | Always pass user input through `?` placeholders to prevent SQL injection. |
| guard clause | 守卫语句 | The guard clause redirects anonymous users to /login. |
| idempotent | 幂等的 | `CREATE TABLE IF NOT EXISTS` is idempotent — safe to run every startup. |
