param(
    [string]$TarPath = "C:\Carla Data\carla_weekend_combined.tar",
    [string]$DestinationRoot = "",
    [string]$DatasetName = "weekendCombined_v1",
    [int]$StartSegment = 30,
    [int]$EndSegment = 52,
    [int[]]$SkipSegments = @(38),
    [int]$MonitorSeconds = 60,
    [int]$SegmentScanEveryIntervals = 0,
    [switch]$NoKeepExisting,
    [string]$StatePath = "",
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

function Quote-Argument {
    param([string]$Value)
    if ($Value -match '[\s"]') {
        return '"' + ($Value -replace '"', '\"') + '"'
    }
    return $Value
}

function Get-FreeBytes {
    param([string]$Path)
    $resolved = Resolve-Path -LiteralPath $Path
    $root = [System.IO.Path]::GetPathRoot($resolved.Path)
    $drive = New-Object System.IO.DriveInfo($root)
    return [int64]$drive.AvailableFreeSpace
}

function Get-SegmentStats {
    param(
        [string]$ImageDir,
        [int[]]$Segments
    )

    $highest = $null
    $highestCount = 0
    foreach ($segment in $Segments) {
        $filter = "segment_${segment}_*.png"
        $first = Get-ChildItem -LiteralPath $ImageDir -File -Filter $filter -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($null -ne $first) {
            $highest = $segment
        }
    }

    if ($null -ne $highest) {
        $highestCount = (Get-ChildItem -LiteralPath $ImageDir -File -Filter "segment_${highest}_*.png" -ErrorAction SilentlyContinue | Measure-Object).Count
    }

    return [ordered]@{
        highestSegment = $highest
        highestSegmentFileCount = $highestCount
    }
}

$repoRoot = Split-Path -Parent $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($DestinationRoot)) {
    $DestinationRoot = Join-Path $repoRoot "data\raw\$DatasetName"
}
if ([string]::IsNullOrWhiteSpace($StatePath)) {
    $StatePath = Join-Path $DestinationRoot "extract_state.json"
}

if (-not (Test-Path -LiteralPath $TarPath)) {
    throw "TAR archive not found: $TarPath"
}

New-Item -ItemType Directory -Force -Path $DestinationRoot | Out-Null
$datasetRoot = Join-Path $DestinationRoot $DatasetName
$imageDir = Join-Path $datasetRoot "images"
New-Item -ItemType Directory -Force -Path $imageDir | Out-Null

$segments = @($StartSegment..$EndSegment | Where-Object { $SkipSegments -notcontains $_ })
$patterns = @($segments | ForEach-Object { "$DatasetName/images/segment_${_}_*" })
$keepExisting = -not $NoKeepExisting

$tarArgs = @("-x", "-m")
if ($keepExisting) {
    $tarArgs += "-k"
}
$tarArgs += @("-f", $TarPath, "-C", $DestinationRoot)
$tarArgs += $patterns
$argumentString = ($tarArgs | ForEach-Object { Quote-Argument $_ }) -join " "

Write-Output "Resume extraction"
Write-Output "Archive: $TarPath"
Write-Output "Destination: $DestinationRoot"
Write-Output "Segments: $($segments -join ', ')"
Write-Output "Keep existing files: $keepExisting"
Write-Output "Monitor interval seconds: $MonitorSeconds"
if ($SegmentScanEveryIntervals -gt 0) {
    Write-Output "Segment scan: every $SegmentScanEveryIntervals monitor intervals"
} else {
    Write-Output "Segment scan: disabled during extraction"
}
Write-Output "State: $StatePath"
Write-Output "Command: tar $argumentString"

if ($DryRun) {
    Write-Output "Dry run only; extraction not started."
    exit 0
}

$startTime = Get-Date
$startFree = Get-FreeBytes -Path $DestinationRoot
$lastTime = $startTime
$lastFree = $startFree
$lastCpuSeconds = 0.0
$monitorTick = 0
$segmentStats = [ordered]@{
    highestSegment = $null
    highestSegmentFileCount = $null
}

$process = Start-Process -FilePath "tar.exe" -ArgumentList $argumentString -PassThru -WindowStyle Hidden
Write-Output "tar PID: $($process.Id)"

while (-not $process.HasExited) {
    Start-Sleep -Seconds $MonitorSeconds
    $process.Refresh()
    $monitorTick += 1

    $now = Get-Date
    $free = Get-FreeBytes -Path $DestinationRoot
    $cpuSeconds = $process.TotalProcessorTime.TotalSeconds
    $elapsedSeconds = [Math]::Max(1.0, ($now - $startTime).TotalSeconds)
    $intervalSeconds = [Math]::Max(1.0, ($now - $lastTime).TotalSeconds)
    $totalWritten = [Math]::Max(0, $startFree - $free)
    $intervalWritten = [Math]::Max(0, $lastFree - $free)
    $avgMbps = ($totalWritten / 1MB) / $elapsedSeconds
    $intervalMbps = ($intervalWritten / 1MB) / $intervalSeconds
    $intervalCpuPercent = (($cpuSeconds - $lastCpuSeconds) / $intervalSeconds) * 100.0

    if (($SegmentScanEveryIntervals -gt 0) -and (($monitorTick % $SegmentScanEveryIntervals) -eq 0)) {
        $segmentStats = Get-SegmentStats -ImageDir $imageDir -Segments $segments
    }

    $state = [ordered]@{
        timestamp = $now.ToString("o")
        tarPid = $process.Id
        running = -not $process.HasExited
        elapsedMinutes = [Math]::Round($elapsedSeconds / 60.0, 1)
        intervalMBps = [Math]::Round($intervalMbps, 2)
        averageMBps = [Math]::Round($avgMbps, 2)
        intervalCpuCorePercent = [Math]::Round($intervalCpuPercent, 1)
        cpuSeconds = [Math]::Round($cpuSeconds, 1)
        approxWrittenGB = [Math]::Round($totalWritten / 1GB, 2)
        freeGB = [Math]::Round($free / 1GB, 1)
        monitorTick = $monitorTick
        segmentScanEveryIntervals = $SegmentScanEveryIntervals
        highestSegment = $segmentStats.highestSegment
        highestSegmentFileCount = $segmentStats.highestSegmentFileCount
        exitCode = $null
    }
    $state | ConvertTo-Json | Set-Content -LiteralPath $StatePath -Encoding UTF8

    Write-Output ("[{0}] running={1} interval={2} MB/s avg={3} MB/s cpu_core={4}% written={5} GB free={6} GB highest_segment={7} files_in_highest={8}" -f `
        $now.ToString("yyyy-MM-dd HH:mm:ss"), `
        (-not $process.HasExited), `
        $state.intervalMBps, `
        $state.averageMBps, `
        $state.intervalCpuCorePercent, `
        $state.approxWrittenGB, `
        $state.freeGB, `
        $state.highestSegment, `
        $state.highestSegmentFileCount)

    $lastTime = $now
    $lastFree = $free
    $lastCpuSeconds = $cpuSeconds
}

$process.Refresh()
$finishTime = Get-Date
$finishFree = Get-FreeBytes -Path $DestinationRoot
$totalElapsedSeconds = [Math]::Max(1.0, ($finishTime - $startTime).TotalSeconds)
if ($SegmentScanEveryIntervals -gt 0) {
    $segmentStats = Get-SegmentStats -ImageDir $imageDir -Segments $segments
}
$finalState = [ordered]@{
    timestamp = $finishTime.ToString("o")
    tarPid = $process.Id
    running = $false
    elapsedMinutes = [Math]::Round($totalElapsedSeconds / 60.0, 1)
    intervalMBps = 0
    averageMBps = [Math]::Round((([Math]::Max(0, $startFree - $finishFree)) / 1MB) / $totalElapsedSeconds, 2)
    intervalCpuCorePercent = 0
    cpuSeconds = [Math]::Round($process.TotalProcessorTime.TotalSeconds, 1)
    approxWrittenGB = [Math]::Round(([Math]::Max(0, $startFree - $finishFree)) / 1GB, 2)
    freeGB = [Math]::Round($finishFree / 1GB, 1)
    monitorTick = $monitorTick
    segmentScanEveryIntervals = $SegmentScanEveryIntervals
    highestSegment = $segmentStats.highestSegment
    highestSegmentFileCount = $segmentStats.highestSegmentFileCount
    exitCode = $process.ExitCode
}
$finalState | ConvertTo-Json | Set-Content -LiteralPath $StatePath -Encoding UTF8
Write-Output "Extraction finished with exit code $($process.ExitCode)."
Write-Output ("Average write speed: {0} MB/s; approx written: {1} GB; highest segment: {2}" -f $finalState.averageMBps, $finalState.approxWrittenGB, $finalState.highestSegment)
exit $process.ExitCode
