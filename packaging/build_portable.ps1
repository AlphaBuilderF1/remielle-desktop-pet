[CmdletBinding()]
param(
    [string]$Version = "0.3.0"
)

$ErrorActionPreference = "Stop"
$ProjectDir = Split-Path -Parent $PSScriptRoot
$AppName = -join ([char[]](0x857e, 0x7c73, 0x57c3, 0x5c14, 0x684c, 0x5ba0))
$ReadmeName = (-join ([char[]](0x4f7f, 0x7528, 0x8bf4, 0x660e))) + ".txt"
$PackageName = "$AppName-v$Version-Windows-x64"
$BuildDir = Join-Path $ProjectDir "build"
$DistDir = Join-Path $ProjectDir "dist"
$ReleaseDir = Join-Path $ProjectDir "release"
$PackageDir = Join-Path $ReleaseDir $PackageName
$ZipPath = Join-Path $ReleaseDir "$PackageName.zip"
$HashPath = "$ZipPath.sha256.txt"

function Assert-ProjectChild([string]$Path) {
    $fullProject = [IO.Path]::GetFullPath($ProjectDir).TrimEnd('\') + '\'
    $fullTarget = [IO.Path]::GetFullPath($Path)
    if (-not $fullTarget.StartsWith($fullProject, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to operate outside project directory: $fullTarget"
    }
}

foreach ($path in @($BuildDir, $DistDir, $ReleaseDir, $PackageDir, $ZipPath, $HashPath)) {
    Assert-ProjectChild $path
}

Set-Location $ProjectDir
python -m PyInstaller --version | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller is not installed. Run: python -m pip install pyinstaller"
}

python main.py --self-test
if ($LASTEXITCODE -ne 0) { throw "Project self-test failed." }

$PyInstallerArgs = @(
    "--noconfirm",
    "--clean",
    "--windowed",
    "--onedir",
    "--contents-directory", "_internal",
    "--name", $AppName,
    "--icon", (Join-Path $ProjectDir "assets\remielle.ico"),
    "--version-file", (Join-Path $ProjectDir "packaging\version_info.txt"),
    "--add-data", ((Join-Path $ProjectDir "assets\remielle-v5-open-hand-five-fingers-display.png") + ";assets"),
    "--add-data", ((Join-Path $ProjectDir "assets\remielle-anim-blink.png") + ";assets"),
    "--distpath", $DistDir,
    "--workpath", $BuildDir,
    "--specpath", $BuildDir,
    "main.py"
)
python -m PyInstaller @PyInstallerArgs
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed." }

if (Test-Path -LiteralPath $PackageDir) {
    Remove-Item -LiteralPath $PackageDir -Recurse -Force
}
New-Item -ItemType Directory -Path $PackageDir -Force | Out-Null
$BuiltAppDir = Join-Path $DistDir $AppName
Get-ChildItem -LiteralPath $BuiltAppDir -Force | Copy-Item -Destination $PackageDir -Recurse
Copy-Item -LiteralPath (Join-Path $ProjectDir "packaging\portable_readme.txt") -Destination (Join-Path $PackageDir $ReadmeName)

if (Test-Path -LiteralPath $ZipPath) { Remove-Item -LiteralPath $ZipPath -Force }
if (Test-Path -LiteralPath $HashPath) { Remove-Item -LiteralPath $HashPath -Force }
Compress-Archive -LiteralPath $PackageDir -DestinationPath $ZipPath -CompressionLevel Optimal
$hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $ZipPath).Hash.ToLowerInvariant()
"$hash  $PackageName.zip" | Set-Content -LiteralPath $HashPath -Encoding ascii

Write-Host "Portable package created:"
Write-Host $ZipPath
Write-Host "SHA-256: $hash"
