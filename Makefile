# 목적: uv 기반 개발 편의 명령 제공

.PHONY: uv-sync uv-run uv-serve dev clean

uv-sync:
	@echo "[uv] 종속성 동기화"
	uv sync

uv-run:
	@echo "[uv] 임포트 검사"
	uv run python - <<'PY'
import importlib
for m in ['fastapi','uvicorn','yt_dlp']:
    importlib.import_module(m)
print('deps_ok')
PY

uv-serve:
	@echo "[uv] 개발 서버 실행(127.0.0.1:3001)"
	uv run uvicorn server.app:app --host 127.0.0.1 --port 3001 --reload

dev: uv-sync uv-serve

clean:
	@echo "[clean] 캐시/빌드 아티팩트 제거"
	rm -rf __pycache__ .pytest_cache .ruff_cache .mypy_cache


