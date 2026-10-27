# Downbeat

A personal classroom app for a secondary music teacher: seating plans, two-tap notes, lesson plans that carry forward, criteria-based formative observations, and report export. Django on a laptop, PWA on an iPad, pupil data kept local.

See `docs/BUILD_ORDER.md` for the data model and phases, `docs/UX.md` for navigation and screens, and `docs/DECISIONS.md` for choices made during the build.

## Running it

```
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python manage.py migrate
.venv\Scripts\python manage.py runserver
```

Tests: `.venv\Scripts\python -m pytest`.

## Demo data

A disposable school for building and trying things out, kept in its own database so the real one stays empty:

```
$env:DOWNBEAT_DB = "demo.sqlite3"
.venv\Scripts\python manage.py migrate
.venv\Scripts\python manage.py seed_demo
.venv\Scripts\python manage.py runserver
```

`seed_demo --reset` wipes and rebuilds it (it refuses to run on `db.sqlite3`). Close the terminal, or `Remove-Item Env:DOWNBEAT_DB`, to go back to the real database.

The theme in `static/theme/` is built from LooseLeaf's tokens by `node tools/build-theme.mjs ../looseleaf-ui static/theme`; a bundle exported from the LooseLeaf configurator can replace it.
