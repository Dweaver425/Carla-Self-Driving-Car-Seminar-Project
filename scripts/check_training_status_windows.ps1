param(
    [string]$LogPath = "data\training\carla_weekend_tar_index_cuda_4pass.log",
    [string]$ErrorLogPath = "data\training\carla_weekend_tar_index_cuda_4pass.err.log",
    [int]$Tail = 30
)

$ErrorActionPreference = "Stop"

Write-Output "Training status"

$pythonProcesses = Get-Process python -ErrorAction SilentlyContinue | Select-Object Id, CPU, StartTime, Responding
if ($pythonProcesses) {
    Write-Output "python processes:"
    $pythonProcesses | Format-Table -AutoSize | Out-String | Write-Output
} else {
    Write-Output "python processes: none"
}

$nvidiaSmi = Get-Command nvidia-smi.exe -ErrorAction SilentlyContinue
if ($nvidiaSmi) {
    Write-Output "gpu:"
    & $nvidiaSmi.Source --query-gpu=name,utilization.gpu,utilization.memory,memory.used,memory.total,temperature.gpu,power.draw,power.limit --format=csv,noheader,nounits
} else {
    Write-Output "gpu: nvidia-smi not found"
}

if (Test-Path -LiteralPath $LogPath) {
    Write-Output "training log tail:"
    Get-Content -LiteralPath $LogPath -Tail $Tail | Write-Output
} else {
    Write-Output "training log: none at $LogPath"
}

if (Test-Path -LiteralPath $ErrorLogPath) {
    $errorTail = Get-Content -LiteralPath $ErrorLogPath -Tail $Tail
    if ($errorTail) {
        Write-Output "error log tail:"
        $errorTail | Write-Output
    }
}
