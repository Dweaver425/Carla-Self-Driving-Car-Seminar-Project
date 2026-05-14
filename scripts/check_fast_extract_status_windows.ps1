param(
    [string]$DestinationRoot = "",
    [string]$DatasetName = "carla_weekend_combined",
    [string]$StatePath = "",
    [string]$LogPath = "",
    [int]$LogTail = 12
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($DestinationRoot)) {
    $DestinationRoot = Join-Path $repoRoot "data\raw\$DatasetName"
}
if ([string]::IsNullOrWhiteSpace($StatePath)) {
    $StatePath = Join-Path $DestinationRoot "fast_extract_state.json"
}
if ([string]::IsNullOrWhiteSpace($LogPath)) {
    $LogPath = Join-Path $DestinationRoot "fast_extract_segment31.log"
}

Write-Output "Fast extraction status"
Write-Output "Destination: $DestinationRoot"

$pythonProcesses = Get-Process python -ErrorAction SilentlyContinue | Select-Object Id, CPU, StartTime, Responding
if ($pythonProcesses) {
    Write-Output "python processes:"
    $pythonProcesses | Format-Table -AutoSize | Out-String | Write-Output
} else {
    Write-Output "python processes: none"
}

if (Test-Path -LiteralPath $StatePath) {
    Write-Output "latest fast extractor state:"
    Get-Content -LiteralPath $StatePath | Write-Output
} else {
    Write-Output "latest fast extractor state: none"
}

if (Test-Path -LiteralPath $LogPath) {
    Write-Output "log tail:"
    Get-Content -LiteralPath $LogPath -Tail $LogTail | Write-Output
}
