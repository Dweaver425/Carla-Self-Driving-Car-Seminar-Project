param(
    [string]$DestinationRoot = "",
    [string]$DatasetName = "carla_weekend_combined",
    [int]$StartSegment = 30,
    [int]$EndSegment = 52,
    [int[]]$SkipSegments = @(38),
    [string]$StatePath = "",
    [int]$LogTail = 8,
    [switch]$ScanSegments
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($DestinationRoot)) {
    $DestinationRoot = Join-Path $repoRoot "data\raw\$DatasetName"
}
if ([string]::IsNullOrWhiteSpace($StatePath)) {
    $StatePath = Join-Path $DestinationRoot "extract_state.json"
}

$datasetRoot = Join-Path $DestinationRoot $DatasetName
$imageDir = Join-Path $datasetRoot "images"
$segments = @($StartSegment..$EndSegment | Where-Object { $SkipSegments -notcontains $_ })

Write-Output "Extraction status"
Write-Output "Destination: $DestinationRoot"
Write-Output "Image dir: $imageDir"

$tarProcesses = Get-Process tar -ErrorAction SilentlyContinue | Select-Object Id, CPU, StartTime, Responding
if ($tarProcesses) {
    Write-Output "tar processes:"
    $tarProcesses | Format-Table -AutoSize | Out-String | Write-Output
} else {
    Write-Output "tar processes: none"
}

if (Test-Path -LiteralPath $StatePath) {
    Write-Output "latest monitor state:"
    Get-Content -LiteralPath $StatePath | Write-Output
} else {
    Write-Output "latest monitor state: none"
}

$fastStatePath = Join-Path $DestinationRoot "fast_extract_state.json"
if (Test-Path -LiteralPath $fastStatePath) {
    Write-Output "latest fast extractor state:"
    Get-Content -LiteralPath $fastStatePath | Write-Output
}

try {
    $resolved = Resolve-Path -LiteralPath $DestinationRoot
    $root = [System.IO.Path]::GetPathRoot($resolved.Path)
    $drive = New-Object System.IO.DriveInfo($root)
    Write-Output ("free space on {0}: {1} GB" -f $root, [Math]::Round($drive.AvailableFreeSpace / 1GB, 1))
} catch {
    Write-Output "free space: unavailable"
}

if ($ScanSegments) {
    Write-Output "segment markers:"
    foreach ($segment in $segments) {
        $filter = "segment_${segment}_*.png"
        $first = Get-ChildItem -LiteralPath $imageDir -File -Filter $filter -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($first) {
            Write-Output "segment_$segment present"
        } else {
            Write-Output "segment_$segment missing"
        }
    }
} else {
    Write-Output "segment markers: skipped; rerun with -ScanSegments for a slower directory scan"
}
