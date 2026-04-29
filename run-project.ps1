$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = Join-Path $projectRoot "backend"
$frontendDir = Join-Path $projectRoot "frontend"
$backendPython = Join-Path $backendDir ".venv\Scripts\python.exe"
$frontendNode = "C:\Program Files\nodejs\node.exe"
$frontendNext = Join-Path $frontendDir "node_modules\next\dist\bin\next"

function Test-PortListening {
    param([int]$Port)

    $matches = netstat -ano | Select-String ":$Port"
    foreach ($match in $matches) {
        if ($match.Line -match "LISTENING") {
            return $true
        }
    }
    return $false
}

if (-not (Test-Path $backendPython)) {
    throw "Backend virtual environment not found: $backendPython"
}

if (-not (Test-Path $frontendNext)) {
    throw "Frontend dependencies not found. Run 'npm install' in the frontend folder first."
}

if (-not (Test-Path $frontendNode)) {
    throw "Node executable not found: $frontendNode"
}

$backendCommand = "Set-Location '$backendDir'; & '$backendPython' -m uvicorn app.main:app --port 8000 --env-file .env"
$frontendCommand = "Set-Location '$frontendDir'; & '$frontendNode' '$frontendNext' dev --hostname 0.0.0.0"

$backend = $null
$frontend = $null

if (Test-PortListening -Port 8000) {
    Write-Host "Backend already running on port 8000."
} else {
    $backend = Start-Process -FilePath powershell.exe `
        -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-Command", $backendCommand `
        -PassThru
}

if (Test-PortListening -Port 3000) {
    Write-Host "Frontend already running on port 3000."
} else {
    $frontend = Start-Process -FilePath powershell.exe `
        -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-Command", $frontendCommand `
        -PassThru
}

if ($backend) {
    Write-Host "Backend PID: $($backend.Id)"
}
if ($frontend) {
    Write-Host "Frontend PID: $($frontend.Id)"
}
Write-Host "Frontend: http://localhost:3000"
Write-Host "Backend:  http://127.0.0.1:8000"
Write-Host "Health:   http://127.0.0.1:8000/health"
