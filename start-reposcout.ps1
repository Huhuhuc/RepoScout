$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw '创建 Python 环境失败' }
}
& '.venv\Scripts\python.exe' -c 'import fastapi, uvicorn, httpx, pydantic' 2>$null
if ($LASTEXITCODE -ne 0) {
    & '.venv\Scripts\python.exe' -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw '依赖安装失败，请检查网络后重试 pip install -r requirements.txt' }
}
Write-Host 'RepoScout: http://127.0.0.1:8011'
& '.venv\Scripts\python.exe' -m uvicorn reposcout.app:app --host 127.0.0.1 --port 8011
