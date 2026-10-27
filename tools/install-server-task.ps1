<#
Starts Downbeat whenever you sign in to Windows, so it is running before the first lesson.
Run once:  .\tools\install-server-task.ps1
Remove with:  Unregister-ScheduledTask -TaskName "Downbeat server"
#>
param([int]$Port = 8000)

$repo = Resolve-Path (Join-Path $PSScriptRoot "..")
$serve = Join-Path $repo "tools\serve.ps1"
$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$serve`" -Port $Port" -WorkingDirectory $repo
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$options = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero)
Register-ScheduledTask -TaskName "Downbeat server" -Action $action -Trigger $trigger -Settings $options `
    -Description "Runs Downbeat on this laptop" -Force | Out-Null
Write-Host "Downbeat will start when you sign in. Start it now with: Start-ScheduledTask -TaskName 'Downbeat server'"
