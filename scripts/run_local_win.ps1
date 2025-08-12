# 목적: Windows(초보자용) 로컬 실행 자동화 스크립트
# - 동작: Python/FFmpeg 설치 가이드, 가상환경 생성, 의존성 설치, 서버 실행
# - 관리자 PowerShell로 실행 권장

param(
  [int]$Port = 3001
)

Write-Host "[정보] yt-download 로컬 실행 스크립트 (Windows)" -ForegroundColor Cyan

# PowerShell 정책 안내
try {
  $policy = Get-ExecutionPolicy
  if ($policy -eq 'Restricted') {
    Write-Warning "실행 정책이 Restricted 입니다. 관리자 PowerShell에서 'Set-ExecutionPolicy RemoteSigned' 실행 후 다시 시도하세요."
  }
} catch {}

# Python 확인
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
  Write-Warning "Python 3.10+이 필요합니다. winget으로 설치할 수 있습니다: winget install --id Python.Python.3.10 -e"
}

# FFmpeg 확인
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
  Write-Warning "FFmpeg가 필요합니다. winget 설치: winget install --id Gyan.FFmpeg -e (또는 Microsoft Store에서 FFmpeg 검색)"
}

# 프로젝트 루트 이동
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Join-Path $ScriptDir '..'
Set-Location $ProjectRoot

# 가상환경 생성/활성화
if (-not (Test-Path .venv)) {
  Write-Host "[정보] 가상환경 생성 중..." -ForegroundColor Green
  python -m venv .venv
}
. .\.venv\Scripts\Activate.ps1

# 의존성 설치
pip install --upgrade pip >$null 2>&1
pip install -r requirements.txt

# 서버 실행
Write-Host "[정보] 서버 실행 중... http://127.0.0.1:$Port" -ForegroundColor Green
python -m uvicorn server.app:app --host 127.0.0.1 --port $Port --reload


