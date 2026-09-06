$ErrorActionPreference = "Stop"

$loggerScript = Join-Path $PSScriptRoot "logger\logger.py"
$viewerScript = Join-Path $PSScriptRoot "logger\viewer.py"
$pythonw = (Get-Command pythonw.exe -ErrorAction Stop).Source

$escapedLoggerPath = [regex]::Escape($loggerScript)
$loggerIsRunning = Get-CimInstance Win32_Process | Where-Object {
    $_.Name -match '^python(w)?\.exe$' -and
    $_.CommandLine -match $escapedLoggerPath
}

if (-not $loggerIsRunning) {
    Start-Process `
        -FilePath $pythonw `
        -ArgumentList "`"$loggerScript`"" `
        -WorkingDirectory $PSScriptRoot `
        -WindowStyle Hidden
}

Start-Process `
    -FilePath $pythonw `
    -ArgumentList "`"$viewerScript`"" `
    -WorkingDirectory $PSScriptRoot
