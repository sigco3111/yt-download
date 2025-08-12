#!/usr/bin/env bash
# 목적: uv 환경에서 FastAPI 서버를 실행하는 스크립트
# 사용 방법:
#   1) uv 설치 후 종속성 동기화:  uv sync
#   2) 서버 실행:                 ./scripts/serve_uv.sh

set -euo pipefail

# uv 설치 확인
if ! command -v uv >/dev/null 2>&1; then
  echo "[오류] uv 명령을 찾을 수 없습니다. 설치 후 다시 실행하세요." >&2
  echo "설치: curl -Ls https://astral.sh/uv/install.sh | sh" >&2
  exit 1
fi

# 프로젝트 루트 기준 실행(스크립트 위치에서 상위로 이동)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

# uv 환경 동기화(필요 시)
uv sync

# 서버 실행(개발 편의: --reload)
uv run uvicorn server.app:app --host 127.0.0.1 --port 3001 --reload


