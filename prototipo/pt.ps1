# Cliente de prueba: manda codigo JavaScript a Packet Tracer y espera el resultado.
# Uso:  powershell -ExecutionPolicy Bypass -File .\pt.ps1 "ipc.network().getDeviceCount()"
#       powershell -ExecutionPolicy Bypass -File .\pt.ps1 -File .\topologia_prueba.js -TimeoutSec 90
param(
    [Parameter(Position = 0)][string]$Code,
    [string]$File,
    [int]$TimeoutSec = 30
)
if ($File) { $Code = Get-Content -Raw -Encoding UTF8 $File }
if (-not $Code) { Write-Error "Falta el codigo o -File"; exit 2 }
$base = "http://127.0.0.1:54321"
$id = (Invoke-WebRequest -UseBasicParsing -Method Post -Uri "$base/run" -Body $Code).Content.Trim()
$deadline = (Get-Date).AddSeconds($TimeoutSec)
while ((Get-Date) -lt $deadline) {
    $r = Invoke-WebRequest -UseBasicParsing -Uri "$base/get?id=$id"
    if ($r.StatusCode -eq 200) { $r.Content; exit 0 }
    Start-Sleep -Milliseconds 200
}
Write-Error "timeout: Packet Tracer no respondio (revisa que el panel PT-MCP este abierto)"
exit 1
