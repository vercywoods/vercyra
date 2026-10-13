$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

$distPath = Join-Path $projectRoot "dist"
$buildPath = Join-Path $projectRoot "build"

python -m PyInstaller `
  --noconfirm `
  --windowed `
  --onefile `
  --name "WorkflowDesktopApp" `
  --distpath $distPath `
  --workpath $buildPath `
  --specpath $projectRoot `
  --add-data "app/db/schema.sql;app/db" `
  "$projectRoot\main.py"

Write-Host "Build complete. Output: $distPath\WorkflowDesktopApp.exe"
