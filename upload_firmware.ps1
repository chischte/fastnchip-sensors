# Upload firmware to Portenta via WiFi OTA
# Usage: .\upload_firmware.ps1
#
# Requires: pio run  (builds firmware.bin AND firmware.ota via make_ota.py)

$ota = "$PSScriptRoot\.pio\build\portenta_h7_m7\firmware.ota"
$bin = "$PSScriptRoot\.pio\build\portenta_h7_m7\firmware.bin"
$url = "http://192.168.31.168/update"

# OTA requires the packaged .ota file; a raw .bin is not a valid fallback.
if (Test-Path $ota) {
    $file = $ota
} else {
    Write-Host "firmware.ota not found. Run 'pio run' first." -ForegroundColor Red
    exit 1
}

$size   = (Get-Item $file).Length
$sizeKB = [math]::Round($size / 1024)
$name   = Split-Path $file -Leaf

Write-Host ""
Write-Host "  File : $name  ($sizeKB KB)"
Write-Host "  Target: $url"
Write-Host ""

# curl --progress-bar shows a live transfer bar in the terminal
# -w adds transfer stats after completion
$result = & curl.exe `
    --progress-bar `
    -X POST $url `
    -F "firmware=@$file" `
    --max-time 300 `
    -w "`n  Speed: %{speed_upload} B/s   Time: %{time_total}s" `
    2>&1

Write-Host ""
Write-Host $result
if ($LASTEXITCODE -ne 0 -or $result -match "failed|error|Invalid|Incomplete") {
    Write-Host "Upload failed; the device was not restarted." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Done. Device is rebooting..." -ForegroundColor Green
