<#
Registers a nightly Windows scheduled task that backs up Downbeat's database.
Run once from PowerShell:  .\tools\install-backup-task.ps1 -Dest "$env:OneDrive\Downbeat backups"
Runs at 21:00, or at the next start-up if the laptop was off. Remove with:
  Unregister-ScheduledTask -TaskName "Downbeat backup"
#>
param(
    [string]$Dest = "",
    [string]$At = "21:00"
)

$repo = Resolve-Path (Join-Path $PSScriptRoot "..")
$python = Join-Path $repo ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { throw "No virtual environment at $python. Create it first (see README)." }

$arguments = "manage.py backup"
if ($Dest) { $arguments += " --dest `"$Dest`"" }

$action = New-ScheduledTaskAction -Execute $python -Argument $arguments -WorkingDirectory $repo
$trigger = New-ScheduledTaskTrigger -Daily -At $At
$options = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopIfGoingOnBatteries -AllowStartIfOnBatteries
Register-ScheduledTask -TaskName "Downbeat backup" -Action $action -Trigger $trigger -Settings $options `
    -Description "Nightly copy of the Downbeat database" -Force | Out-Null
Write-Host "Nightly backup scheduled for $At. Test it now with: Start-ScheduledTask -TaskName 'Downbeat backup'"
