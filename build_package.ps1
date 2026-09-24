# MapYou Package Builder
# Avoid Chinese path issues by using C:\MapYou_Build

$ErrorActionPreference = "Stop"

Write-Host "================================" -ForegroundColor Cyan
Write-Host "MapYou Package Builder" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan

# Define paths
$sourcePath = $PSScriptRoot
$buildPath = "C:\MapYou_Build"
$finalPath = Join-Path $sourcePath "dist"

Write-Host "`n[Step 1/6] Creating temporary build folder..." -ForegroundColor Yellow
if (Test-Path $buildPath) {
    Remove-Item -Recurse -Force $buildPath
}
New-Item -ItemType Directory -Force -Path $buildPath | Out-Null
Write-Host "Build folder: $buildPath" -ForegroundColor Gray

Write-Host "`n[Step 2/6] Copying files to build folder..." -ForegroundColor Yellow
Copy-Item -Path "$sourcePath\*" -Destination $buildPath -Recurse -Force -Exclude @("dist", "build", "__pycache__", ".venv", "*.pyc")
Write-Host "Files copied successfully" -ForegroundColor Gray

Write-Host "`n[Step 3/6] Setting up clean Python environment..." -ForegroundColor Yellow
# Create virtual environment in build folder (avoid Chinese path)
python -m venv "$buildPath\.venv_temp" --clear
& "$buildPath\.venv_temp\Scripts\Activate.ps1"
python -m pip install --upgrade pip --quiet
pip install -r "$buildPath\requirements.txt" -i https://pypi.tuna.tsinghua.edu.cn/simple --quiet
if ($LASTEXITCODE -ne 0) {
    Write-Host "Warning: Some dependencies failed to install" -ForegroundColor Yellow
}

Write-Host "`n[Step 4/6] Cleaning old build artifacts..." -ForegroundColor Yellow
Set-Location $buildPath
if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }

Write-Host "`n[Step 5/6] Building executable (5-10 minutes)..." -ForegroundColor Yellow
Write-Host "Please wait patiently..." -ForegroundColor Gray
& "$buildPath\.venv_temp\Scripts\pyinstaller.exe" "$buildPath\MapYou.spec" --clean --noconfirm

if ($LASTEXITCODE -ne 0) {
    Write-Host "`nBuild failed!" -ForegroundColor Red
    Set-Location $sourcePath
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "`n[Step 6/6] Copying exe to original folder..." -ForegroundColor Yellow
# PyInstaller outputs to build folder's dist
$buildExePath = Join-Path $buildPath "dist\MapYou-福州社区便利度分析.exe"
$finalExePath = Join-Path $sourcePath "dist\MapYou-福州社区便利度分析.exe"

if (Test-Path $buildExePath) {
    # Create dist folder in source if not exists
    if (-not (Test-Path (Join-Path $sourcePath "dist"))) {
        New-Item -ItemType Directory -Path (Join-Path $sourcePath "dist") | Out-Null
    }
    Copy-Item -Path $buildExePath -Destination $finalExePath -Force
    
    $size = (Get-Item $finalExePath).Length / 1MB
    
    Write-Host "`n================================" -ForegroundColor Green
    Write-Host "BUILD SUCCESSFUL!" -ForegroundColor Green
    Write-Host "================================" -ForegroundColor Green
    Write-Host "Executable: $finalExePath" -ForegroundColor Cyan
    Write-Host "File size: $($size.ToString('0.00')) MB" -ForegroundColor Cyan
    
    Write-Host "`n================================" -ForegroundColor Yellow
    Write-Host "How to use:" -ForegroundColor Yellow
    Write-Host "1. Send the exe file to users" -ForegroundColor White
    Write-Host "2. Users double-click to run" -ForegroundColor White
    Write-Host "3. Browser will open automatically" -ForegroundColor White
    Write-Host "================================" -ForegroundColor Yellow
    
    # Cleanup
    Write-Host "`nCleaning up temporary build folder..." -ForegroundColor Gray
    Set-Location $sourcePath
    Remove-Item -Recurse -Force $buildPath
    Write-Host "Cleanup complete" -ForegroundColor Gray
    
} else {
    Write-Host "`nBuild failed: exe not found" -ForegroundColor Red
    Set-Location $sourcePath
}

Write-Host "`nPress Enter to exit..."
Read-Host
