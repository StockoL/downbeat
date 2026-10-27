<#
Checks the laptop is ready for the iPad and records its Tailscale name for Django.
Run after installing Tailscale (see docs/TAILSCALE.md):  .\tools\tailscale-check.ps1
#>
param([int]$Port = 8000)

$repo = Resolve-Path (Join-Path $PSScriptRoot "..")
$tailscale = (Get-Command tailscale -ErrorAction SilentlyContinue).Source
if (-not $tailscale) { $tailscale = "C:\Program Files\Tailscale\tailscale.exe" }
if (-not (Test-Path $tailscale)) { throw "Tailscale isn't installed. See docs/TAILSCALE.md, step 1." }

$status = & $tailscale status --json | ConvertFrom-Json
if ($status.BackendState -ne "Running") { throw "Tailscale is installed but not connected. Sign in from the tray icon." }
$name = $status.Self.DNSName.TrimEnd(".")
if (-not $name.EndsWith(".ts.net")) { throw "No MagicDNS name. Turn on MagicDNS in the Tailscale admin console (docs/TAILSCALE.md, step 3)." }

$local = Join-Path $repo "local"
New-Item -ItemType Directory -Force $local | Out-Null
Set-Content -Path (Join-Path $local "hosts.txt") -Value $name -Encoding utf8
Write-Host "Laptop name: $name (saved to local\hosts.txt)"

$serve = & $tailscale serve status 2>&1 | Out-String
if ($serve -match "127.0.0.1:$Port") {
    Write-Host "Tailscale is serving https://$name to Downbeat."
} else {
    Write-Host "Not serving yet. Run once:  tailscale serve --bg $Port"
    Write-Host "Then restart Downbeat and open https://$name on the iPad."
}
