# CommunityBridge

A neighborhood mutual-aid platform — people post things they **need**
help with or things they can **offer**, organized by neighborhood and
urgency, so neighbors can find and help each other directly.

## What it does

- **Post a need or an offer** — e.g. "Flooded basement, need a pump"
  or "Extra home-cooked meals available" — tagged by category and an
  urgency level (normal / urgent / emergency)
- **Browse posts** filtered by neighborhood and category, with
  emergency posts surfaced first
- **Respond to posts** and say thanks once help is given
- **User profiles** listing each person's skills and neighborhood
- **Admin dashboard** for moderating posts

## Tech stack

- **Backend:** Python, Flask
- **Database:** SQLite (a single local file, no separate database
  server needed)
- **Frontend:** server-rendered HTML templates (Jinja2), vanilla CSS/JS
- **Auth:** session-based login, passwords hashed with Werkzeug's
  `generate_password_hash` (scrypt), never stored in plain text

## Setup

```bash
python -m venv venv
source venv/Scripts/activate      # Windows Git Bash
# venv\Scripts\activate           # Windows CMD/PowerShell
pip install -r requirements.txt
python app.py
```

Open `http://localhost:5001`. The database (`communitybridge.db`)
comes seeded with a few sample users and posts so the app isn't empty
on first run — register your own new account to actually log in and
try posting, since the seed accounts' original passwords aren't known.

### If the server seems to exit right after starting

On some Windows + Git Bash setups, Flask's auto-reloader can fail
silently and the process exits right after printing its startup
banner. If that happens, open `app.py`, find the last line:
```python
app.run(debug=True, host="0.0.0.0", port=5001)
```
and add `use_reloader=False`:
```python
app.run(debug=True, host="0.0.0.0", port=5001, use_reloader=False)
```
(the trade-off: you'll need to restart the server manually after
editing code, instead of it reloading automatically)

## Project structure

```
communitybridge/
├── app.py                  routes and request handling
├── database.py               schema + seed data
├── communitybridge.db          the SQLite database file
├── templates/                    Jinja2 HTML templates
├── static/
│   ├── css/style.css
│   └── js/app.js
└── requirements.txt
```

## Honest notes

- The `app.secret_key` in `app.py` is a hardcoded placeholder, fine
  for local use but something you'd replace with a real, private
  secret before ever deploying this anywhere public.
- This is a demo/portfolio project with fictional seed data, not a
  real, moderated community platform - things like abuse reporting,
  identity verification, and real moderation tooling would need to be
  built out further before this could be used for real.
