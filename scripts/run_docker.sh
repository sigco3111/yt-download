#!/usr/bin/env bash
# 목적: Docker로 yt-download 서버를 손쉽게 빌드/실행하는 스크립트(초보자용)
# - 동작: 이미지 빌드 → 컨테이너 실행 → 브라우저 자동 열기
# - 전제: Docker Desktop(또는 Docker Engine)이 설치되어 실행 중이어야 함

set -euo pipefail

# 프로젝트 루트 계산
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

PORT="3001"
IMAGE_NAME="yt-download:local"
CONTAINER_NAME="yt-download"

# 필수 체크: docker
if ! command -v docker >/dev/null 2>&1; then
  echo "[오류] Docker가 설치되어 있지 않습니다. Docker Desktop을 설치 후 다시 실행하세요." >&2
  echo "다운로드: https://www.docker.com/products/docker-desktop" >&2
  exit 1
fi

# 다운로드 디렉토리 준비
mkdir -p "$PROJECT_ROOT/downloads"

echo "[정보] Docker 이미지 빌드 중… ($IMAGE_NAME)"
docker build -t "$IMAGE_NAME" .

echo "[정보] 컨테이너 실행: 포트 $PORT, 볼륨 마운트 downloads -> /app/downloads"
set +e
docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
set -e
docker run --name "$CONTAINER_NAME" --rm -p "$PORT:3001" \
  -v "$PROJECT_ROOT/downloads:/app/downloads" \
  "$IMAGE_NAME" &

# 간단 대기 후 브라우저 열기
sleep 1
if command -v open >/dev/null 2>&1; then
  open "http://127.0.0.1:$PORT" || true
elif command -v xdg-open >/dev/null 2>&1; then
  xdg-open "http://127.0.0.1:$PORT" || true
fi

echo "[완료] 브라우저에서 http://127.0.0.1:$PORT 접속하세요. 종료는 Ctrl+C 또는 컨테이너 정지."


