#!/usr/bin/env bash
# 목적: macOS(초보자용) 로컬 실행 자동화 스크립트
# - 동작: ffmpeg 설치 안내, 가상환경 생성, 의존성 설치, 서버 실행

set -euo pipefail

PORT="3001"

echo "[정보] yt-download 로컬 실행 스크립트 (macOS)"

# 프로젝트 루트 계산
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

# ffmpeg 확인
if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "[안내] ffmpeg가 설치되어 있지 않습니다. Homebrew로 설치 권장:"
  echo "       /bin/bash -c \"$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
  echo "       brew install ffmpeg"
fi

python3 -m venv .venv || true
source .venv/bin/activate
pip install --upgrade pip >/dev/null 2>&1 || true
pip install -r requirements.txt

echo "[정보] 서버 실행 중... http://127.0.0.1:$PORT"
python -m uvicorn server.app:app --host 127.0.0.1 --port "$PORT" --reload


