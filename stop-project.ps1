$ErrorActionPreference = "SilentlyContinue"

$ports = 3000, 8000
$pids = @()

foreach ($port in $ports) {
    $matches = netstat -ano | Select-String ":$port"
    foreach ($match in $matches) {
        $parts = ($match.Line -split "\s+") | Where-Object { $_ }
        if ($parts.Length -ge 5) {
            $pid = [int]$parts[-1]
            if ($pid -gt 0 -and $pids -notcontains $pid) {
                $pids += $pid
            }
        }
    }
}

if (-not $pids) {
    Write-Host "No local project processes found on ports 3000 or 8000."
    exit 0
}

Stop-Process -Id $pids -Force
Write-Host "Stopped processes: $($pids -join ', ')"
