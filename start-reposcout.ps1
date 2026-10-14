param([ValidateRange(1024,65535)][int]$Port = 8011, [switch]$Check)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    python -m reposcout.doctor --python-only
    if ($LASTEXITCODE -ne 0) { throw '需要 Python 3.11 或更新版本' }
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw '创建 Python 环境失败' }
}
$repoScoutLockHash = (Get-FileHash -LiteralPath 'requirements.lock.txt' -Algorithm SHA256).Hash
$repoScoutInstalledHash = if (Test-Path -LiteralPath '.venv\dependency-hash') { (Get-Content -LiteralPath '.venv\dependency-hash' -Raw).Trim() } else { '' }
if ($repoScoutInstalledHash -ne $repoScoutLockHash) {
    & '.venv\Scripts\python.exe' -m pip install -r requirements.lock.txt
    if ($LASTEXITCODE -ne 0) { throw '依赖安装失败，请检查网络' }
    Set-Content -LiteralPath '.venv\dependency-hash' -Value $repoScoutLockHash
}
if (-not (Test-Path -LiteralPath '.env')) { Copy-Item -LiteralPath '.env.example' -Destination '.env' }
if ($Check) {
    & '.venv\Scripts\python.exe' -m reposcout.doctor
    exit $LASTEXITCODE
}
if (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) {
    Write-Host "端口 $Port 已被占用；请打开现有工作台，或用 -Port 指定其他端口。"
    exit 1
}
Write-Host "RepoScout: http://127.0.0.1:$Port"
& '.venv\Scripts\python.exe' -m uvicorn reposcout.app:app --host 127.0.0.1 --port $Port
