$ErrorActionPreference = "Stop"

$backend = Start-Process kubectl -ArgumentList @(
    "port-forward", "service/backend", "8000:8000", "--namespace", "localrag"
) -PassThru -WindowStyle Hidden
$frontend = Start-Process kubectl -ArgumentList @(
    "port-forward", "service/frontend", "5173:5173", "--namespace", "localrag"
) -PassThru -WindowStyle Hidden

Write-Host "Web interface: http://localhost:5173"
Write-Host "API documentation: http://localhost:8000/docs"
Write-Host "Press Enter to stop port forwarding."
Read-Host

Stop-Process -Id $backend.Id, $frontend.Id -ErrorAction SilentlyContinue

