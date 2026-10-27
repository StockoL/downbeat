<#
Runs Downbeat for real use: migrations applied, static files collected, debug off, served by
waitress on this laptop only (127.0.0.1). The iPad reaches it through `tailscale serve`, which
adds HTTPS; nothing on the school network can reach it directly.
    .\tools\serve.ps1            # port 8000
    .\tools\serve.ps1 -Port 8080
#>
param([int]$Port = 8000)

$ErrorActionPreference = "Stop"
$repo = Resolve-Path (Join-Path $PSScriptRoot "..")
$python = Join-Path $repo ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { throw "No virtual environment at $python. Create it first (see README)." }

Set-Location $repo
Remove-Item Env:DOWNBEAT_DEBUG -ErrorAction SilentlyContinue
& $python manage.py migrate --noinput
& $python manage.py collectstatic --noinput --verbosity 0
& $python manage.py check --deploy --fail-level ERROR
Write-Host "Downbeat on http://127.0.0.1:$Port  (Ctrl+C to stop)"
& $python -m waitress --listen="127.0.0.1:$Port" --threads=8 downbeat.wsgi:application
