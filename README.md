# Reseller OS — purchase/inventory/sales manager

A web app version of your spreadsheet: Dashboard, Purchases, Inventory,
Sales, Business Expenses, Vendors, Settings (dropdown lists + marketplace
fees), Deal Calculator, and Analytics — with username/password accounts.

**Multi-user:** anyone who creates an account gets their own completely
separate set of data (vendors, inventory, sales, etc.) — nobody can see
anyone else's numbers.

This version is built to deploy to **Render** (or any host that gives you a
Postgres database), so it's reachable from any device, anywhere — not just
your home network.

---

## Deploy to Render (recommended)

1. Push this folder to a new GitHub repository.
2. In the [Render Dashboard](https://dashboard.render.com), click **New →
   Blueprint**, and connect that repository. Render will read `render.yaml`
   in this folder automatically and set up two things for you:
   - A **web service** running this app
   - A small **managed Postgres database**, already wired to the app via
     the `DATABASE_URL` environment variable
3. Render also auto-generates a random `SESSION_SECRET` for you (see
   `render.yaml` — `generateValue: true`), so there's nothing to fill in
   there.
4. Click **Apply**. First deploy takes a few minutes. When it's done,
   you'll get a URL like `https://reseller-os.onrender.com` — that's the
   site. Share it with whoever needs an account; each person registers
   their own username/password from the login page.

**Cost:** the `starter` plan in `render.yaml` runs about $7/mo for the web
service and $7/mo for the tiny Postgres instance (~$14/mo total), with no
usage-based surprises. To test for free first, change both `plan: starter`
lines in `render.yaml` to `plan: free` before connecting the repo — free web
services sleep after 15 minutes of inactivity (30-50s to wake back up), and
the free Postgres expires after 30 days, so it's only meant for trying
things out before switching to `starter`.

### Locking down sign-ups

Once everyone who needs an account has one, go to your web service in the
Render Dashboard → **Environment**, and set:
```
ALLOW_REGISTRATION=false
```
Existing accounts keep working; the `/register` page just stops accepting
new sign-ups. Flip it back any time to add someone new.

### Custom domain (optional)

Render → your web service → **Settings → Custom Domains**. Point your
domain's DNS at Render per their instructions; HTTPS is issued and renewed
automatically.

---

## Running it locally (for development/testing)

No Postgres needed for this — it automatically falls back to a local
SQLite file when `DATABASE_URL` isn't set.

```bash
pip install -r requirements.txt
python -c "import secrets; print(secrets.token_hex(32))"   # generate a session secret
```

Create a `.env` file:
```
SESSION_SECRET=<paste the generated value>
ALLOW_REGISTRATION=true
```

```bash
python run.py
```

Visit http://127.0.0.1:8000, click **Create one** to register the first
account. Data is stored in `data/app.db` (SQLite) and is separate from
whatever's in your deployed Render database.

---

## Project structure

```
pim_webapp/
  render.yaml          Render Blueprint — defines the web service + database
  app/
    main.py          FastAPI app, mounts routes, secure cookies in production
    config.py         Settings (DATABASE_URL, SESSION_SECRET, ...)
    database.py        Postgres in production, SQLite locally — same code either way
    models.py           Tables (all scoped by user_id)
    auth.py               Username/password login, registration, sessions
    calculations.py        Per-item/sale derived numbers (cost basis, ROI, days held, ...)
    reports.py               Dashboard KPIs + Analytics aggregates
    seed.py                    Default dropdown values & marketplace fees for new users
    routers/pages.py            All page routes + form handling (CRUD)
  templates/            Jinja2 HTML templates (one per page)
  static/style.css      Styling
```

## Security notes

- Passwords are hashed with PBKDF2-SHA256 (260,000 iterations) + a random
  salt per user — never stored in plain text. See `app/auth.py`.
- Session cookies are `Secure` + `HttpOnly` automatically once deployed to
  Render (detected via Render's own `RENDER` environment variable) — locally
  they're not, since `http://127.0.0.1` has no HTTPS to require.
- There's no "forgot password" flow in this version — if someone loses their
  password, the fix today is deleting/recreating their row directly in the
  database (via Render's Postgres dashboard). Happy to add a real reset flow
  (e.g. emailed reset links) if that becomes a real need.
- No migrations system yet — the database schema is created automatically
  on first boot (`Base.metadata.create_all`). Fine for now; if you start
  changing the data model after real data exists, that's the point to add
  Alembic migrations rather than editing tables by hand.

## Notes on how the numbers are calculated

Nothing derived (Total Cost Basis, Quantity Remaining, Days Held, Profit,
ROI, etc.) is stored — it's recalculated from the raw fields every time a
page loads, the same way the spreadsheet's formulas worked. See
`app/calculations.py` and `app/reports.py` for the exact logic.
