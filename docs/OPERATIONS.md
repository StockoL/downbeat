# Operations

Running Downbeat day to day on the laptop, reaching it from the iPad, and looking after the data.

## Installing

Needs Python 3.12 and the LooseLeaf-UI repository checked out beside this one (`../looseleaf-ui`), since the `django-looseleaf` package is installed from it.

```
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

## Serving

```
.\tools\serve.ps1
```

This applies any migrations, collects static files, runs Django's deployment checks and serves Downbeat with waitress at http://127.0.0.1:8000, with debug off. It listens on the laptop only; nothing on the school network can reach the port.

The first visit opens the first-run setup: your account, the timetable and its periods, note types, a first room, and optionally flags and checklist items. Nothing is pre-filled; the app holds no personal values until you type them.

To start the server whenever you sign in to Windows, run once:

```
.\tools\install-server-task.ps1
```

`serve.ps1 -Port 8765` serves on another port.

To have Downbeat as an app in its own window with a taskbar icon, install it from Edge: [INSTALL.md](INSTALL.md#on-the-windows-laptop).

## The iPad

The iPad reaches the laptop through Tailscale, which works across school Wi-Fi that isolates devices and gives the laptop a real HTTPS certificate, without which iOS won't install an offline web app. [TAILSCALE.md](TAILSCALE.md) sets that up, and [INSTALL.md](INSTALL.md) installs the app on the iPad (and on the laptop) step by step.

Once installed, the room view works with Wi-Fi off. Captures are saved on the iPad and sent when the laptop is reachable; the bottom bar says "3 saved on this device" while any are waiting. A session lasts 120 days, so the iPad doesn't ask for the password mid-lesson. Signing out empties the iPad's cache.

## Backups

```
.venv\Scripts\python manage.py backup
```

Copies the live database with SQLite's online backup API (consistent even mid-write), checks the copy's integrity and keeps the newest 30 in `backups\`. For a nightly copy to OneDrive, run once:

```
.\tools\install-backup-task.ps1 -Dest "$env:OneDrive\Downbeat backups"
```

The scheduled task also runs at the next start-up if the laptop was off at the time. Settings → Data has "Back up now" as well.

### Restoring

Stop the server, copy a backup over `db.sqlite3`, start the server.

## Export and delete

- **Download everything** (Settings → Data) or `manage.py export_json` writes every row as JSON that `manage.py loaddata` reads back.
- **Everything held about one pupil**: "Download everything held about …" on their pupil page, for a subject access request.
- **Recordings that may no longer be kept** (past a pupil's delete-by date, or without permission) are listed on Settings → Data with "Remove these references", or by `manage.py purge_recordings --dry-run` and `manage.py purge_recordings`. Downbeat holds paths, not files, so delete the listed files from their folder too.
- **Delete everything** (Settings → Data) wipes every Downbeat row and signs every device out, after you type "delete everything". The account is kept and the app returns to first-run setup. Backup files are separate and left for you to remove.

## Settings reference

All optional; the defaults suit a single laptop.

| Variable | Default | Effect |
| --- | --- | --- |
| `DOWNBEAT_DB` | `db.sqlite3` | Database file. Point at `demo.sqlite3` for the demo school |
| `DOWNBEAT_DEBUG` | off | `1` turns on Django's debug mode (development only) |
| `DOWNBEAT_LOCAL_DIR` | `local\` | Where the per-install secret key, host list and logs live |
| `DOWNBEAT_SECRET_KEY` | generated into `local\secret_key` | Overrides the generated key |
| `DOWNBEAT_HOSTS` | read from `local\hosts.txt` | The Tailscale host name(s); turns on secure cookies, HSTS and CSRF trust for them |
| `DOWNBEAT_BACKUP_DIR` | `backups\` | Where backups go |
| `DOWNBEAT_BACKUP_KEEP` | `30` | How many backups to keep |

Warnings and errors are logged to `local\logs\downbeat.log`, rotated.

## Housekeeping

- Sessions are generated a half term at a time (Settings → Timetable → Generate, or `manage.py generate_sessions`). Generating over the same dates never duplicates or overwrites.
- **Before a new school year**, Settings → Rollover archives last year's classes (kept, read-only), moves pupils up or marks them as left, reviews flags and keep-aparts, and closes or carries open actions. It takes a backup first. Then set up the new timetable's slots and classes; pasting class lists reuses the pupils who stay.
