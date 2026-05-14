param(
    [string]$DestinationRoot = "",
    [string]$DatasetName = "carla_weekend_combined",
    [int]$TarPid = 0,
    [int]$SampleSeconds = 60,
    [string]$StatePath = ""
)

$ErrorActionPreference = "Stop"

function Get-FreeBytes {
    param([string]$Path)
    $resolved = Resolve-Path -LiteralPath $Path
    $root = [System.IO.Path]::GetPathRoot($resolved.Path)
    $drive = New-Object System.IO.DriveInfo($root)
    return [ordered]@{
        root = $root
        freeBytes = [int64]$drive.AvailableFreeSpace
    }
}

function Get-TarProcess {
    param([int]$TargetProcessId)
    if ($TargetProcessId -gt 0) {
        return Get-Process -Id $TargetProcessId -ErrorAction Stop
    }

    $processes = @(Get-Process tar -ErrorAction SilentlyContinue | Sort-Object StartTime -Descending)
    if ($processes.Count -eq 0) {
        return $null
    }
    return $processes[0]
}

$repoRoot = Split-Path -Parent $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($DestinationRoot)) {
    $DestinationRoot = Join-Path $repoRoot "data\raw\$DatasetName"
}
if ([string]::IsNullOrWhiteSpace($StatePath)) {
    $StatePath = Join-Path $DestinationRoot "extract_state.json"
}

Write-Output "Extraction speed sample"
Write-Output "Destination: $DestinationRoot"
Write-Output "Sample seconds: $SampleSeconds"

$process = Get-TarProcess -TargetProcessId $TarPid
if ($null -eq $process) {
    Write-Output "tar process: none"
    if (Test-Path -LiteralPath $StatePath) {
        Write-Output "latest monitor state:"
        Get-Content -LiteralPath $StatePath | Write-Output
    }
    exit 1
}

$process.Refresh()
$startTime = Get-Date
$startFree = Get-FreeBytes -Path $DestinationRoot
$startCpu = $process.TotalProcessorTime.TotalSeconds

Write-Output ("tar PID: {0}" -f $process.Id)
Write-Output ("free before: {0} GB" -f [Math]::Round($startFree.freeBytes / 1GB, 1))

Start-Sleep -Seconds $SampleSeconds

$processStillRunning = $true
try {
    $process.Refresh()
    if ($process.HasExited) {
        $processStillRunning = $false
    }
} catch {
    $processStillRunning = $false
}

$finishTime = Get-Date
$finishFree = Get-FreeBytes -Path $DestinationRoot
$elapsedSeconds = [Math]::Max(1.0, ($finishTime - $startTime).TotalSeconds)
$writtenBytes = [Math]::Max(0, $startFree.freeBytes - $finishFree.freeBytes)
$writtenMB = $writtenBytes / 1MB
$writeMBps = $writtenMB / $elapsedSeconds

$finishCpu = $startCpu
if ($processStillRunning) {
    $finishCpu = $process.TotalProcessorTime.TotalSeconds
}
$cpuSeconds = [Math]::Max(0, $finishCpu - $startCpu)
$cpuCorePercent = ($cpuSeconds / $elapsedSeconds) * 100.0
$mbPerCpuSecond = $null
if ($cpuSeconds -gt 0) {
    $mbPerCpuSecond = $writtenMB / $cpuSeconds
}

$result = [ordered]@{
    timestamp = $finishTime.ToString("o")
    tarPid = $process.Id
    running = $processStillRunning
    elapsedSeconds = [Math]::Round($elapsedSeconds, 1)
    intervalMBps = [Math]::Round($writeMBps, 2)
    intervalWrittenGB = [Math]::Round($writtenBytes / 1GB, 2)
    intervalCpuCorePercent = [Math]::Round($cpuCorePercent, 1)
    intervalCpuSeconds = [Math]::Round($cpuSeconds, 1)
    mbPerCpuSecond = if ($null -ne $mbPerCpuSecond) { [Math]::Round($mbPerCpuSecond, 2) } else { $null }
    freeGB = [Math]::Round($finishFree.freeBytes / 1GB, 1)
}

Write-Output ("running: {0}" -f $result.running)
Write-Output ("write speed: {0} MB/s over {1}s" -f $result.intervalMBps, $result.elapsedSeconds)
Write-Output ("written this sample: {0} GB" -f $result.intervalWrittenGB)
Write-Output ("tar CPU: {0}% of one CPU core" -f $result.intervalCpuCorePercent)
Write-Output ("efficiency: {0} MB written per CPU-second" -f $result.mbPerCpuSecond)
Write-Output ("free after: {0} GB" -f $result.freeGB)

Write-Output "json:"
$result | ConvertTo-Json | Write-Output
