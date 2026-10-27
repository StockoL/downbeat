# Downbeat

A personal classroom app for a secondary music teacher: seating plans, two-tap notes, lesson plans that carry forward, criteria-based formative observations, and report export. Django on a laptop, PWA on an iPad, pupil data kept local.

See `docs/BUILD_ORDER.md` for the data model and phases, `docs/UX.md` for navigation and screens, and `docs/DECISIONS.md` for choices made during the build.

## Installing

```
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

## Using it

```
.\tools\serve.ps1
```

Applies any migrations, then serves Downbeat at http://127.0.0.1:8000 on this laptop only, with debug off. The first visit opens the setup, which creates your account. `.\tools\install-server-task.ps1` starts it whenever you sign in to Windows. To reach it from the iPad, follow `docs/TAILSCALE.md`.

## Developing

```
$env:DOWNBEAT_DEBUG = "1"
.venv\Scripts\python manage.py runserver
```

Tests and lint: `.venv\Scripts\python -m pip install -r requirements-dev.txt`, then `.venv\Scripts\python -m pytest` and `.venv\Scripts\ruff check .`. GitHub Actions runs both on every push.

## Backups

`.venv\Scripts\python manage.py backup` copies the database to `backups\` (or `DOWNBEAT_BACKUP_DIR`) and keeps the newest 30. For a nightly copy to OneDrive, run once:

```
.\tools\install-backup-task.ps1 -Dest "$env:OneDrive\Downbeat backups"
```

To restore, stop the server and copy a backup over `db.sqlite3`. Settings → Data also has "Back up now", a full JSON export and "Delete everything".

## Demo data

A disposable school for building and trying things out, kept in its own database so the real one stays empty:

```
$env:DOWNBEAT_DB = "demo.sqlite3"
.venv\Scripts\python manage.py migrate
.venv\Scripts\python manage.py seed_demo
.venv\Scripts\python manage.py runserver
```

Sign in as `demo` / `demo-downbeat`. `seed_demo --reset` wipes and rebuilds it (it refuses to run on `db.sqlite3`). Close the terminal, or `Remove-Item Env:DOWNBEAT_DB`, to go back to the real database.

## Theme

The theme in `static/theme/` is built from LooseLeaf's tokens by `node tools/build-theme.mjs ../looseleaf-ui static/theme`; a bundle exported from the LooseLeaf configurator can replace it.
