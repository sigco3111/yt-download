# Development Guidelines (Shrimp Rules) — yt-download

## 목적
- 본 문서는 AI Agent 전용 개발 규칙이다. 일반 개발 지식 서술을 금지한다.
- 실제 코드베이스(server/app.py, web/index.html, README.md, docs/PRD.md)를 기준으로 작업 지침을 정의한다.

## 프로젝트 개요(요약)
- 로컬 전용 FastAPI 서버와 단일 HTML UI로 YouTube 컨텐츠를 yt-dlp/ffmpeg로 다운로드한다.
- 필수 외부 도구: ffmpeg(시스템 설치 필요), 파이썬 패키지: yt-dlp, fastapi, uvicorn.

## 아키텍처/디렉터리 규칙
- 반드시 다음 상호작용을 준수하라:
  - `server/app.py`는 API와 정적 파일 서빙을 담당한다. `web/` 디렉터리를 서빙한다.
  - `web/index.html`은 `/api/formats`, `/api/download`를 호출한다. API 파라미터/경로가 변경되면 동시 수정하라.
  - 다운로드 산출물은 루트 `downloads/`에 저장된다. 해당 경로 생성 로직은 `server/app.py`에서 유지한다.
  - 문서 변경(사용법/API 계약)은 `README.md`와 `docs/PRD.md`를 함께 갱신하라.

## 코드 작성 규칙
- 모든 함수/중요 로직 상단에 한국어 docstring/주석으로 목적을 명확히 기술하라.
- 복잡한 로직에는 단계적 주석을 추가하라. 불필요한 주석은 금지한다.
- 상수는 대문자 스네이크 케이스를 사용하라. 불리언은 `is/has/can` 접두사를 사용하라.
- 예외 처리 시:
  - 내부적으로 로거에 상세 예외를 기록하라.
  - 사용자 응답 메시지는 일반적이고 구체적이지 않게 하라.
  - 사용자가 취할 수 있는 조치를 `README.md` 문제해결 섹션에 추가/갱신하라.

## API 계약 규칙
- 현재 유효한 엔드포인트(실제 코드 기준):
  - `GET /api/health`
  - `GET /api/formats?url=...`
  - `GET /api/download?url=...&type=(video|audio)&format_id=...`
- API를 변경하거나 추가할 경우 반드시 수행하라:
  1) `web/index.html`의 fetch 호출 업데이트
  2) `README.md` 사용법/엔드포인트 표 갱신
  3) `docs/PRD.md`의 사양 일치화(차이가 있으면 PRD를 현실에 맞게 업데이트)

## 외부 도구/라이브러리 사용 규칙
- `yt-dlp` 포맷 선택 규칙은 `server/app.py`에 상수/함수로 선언하여 한곳에서 제어하라.
- `ffmpeg` 의존 기능을 추가할 때는 시스템 전제(설치 필요)를 `README.md` 전제 조건 섹션에 명시하라.
- 패키지 버전 변경은 `requirements.txt`에 반영하고 호환성 테스트 후 커밋하라.

## 워크플로우 규칙
1) 변경 전: 관련 파일 전수 조사(서로 의존하는 파일 목록 도출)
2) 구현: `server/app.py`(백엔드) → `web/index.html`(프런트) → 문서 동기화 순서로 작업하라.
3) 테스트: 로컬에서 `/api/health`, `/api/formats`, `/api/download` 기본 플로우 검증 후 커밋하라.

## 핵심 파일 동시 수정 규칙(필수)
- API 파라미터/경로 변경 → `server/app.py`, `web/index.html`, `README.md`, `docs/PRD.md`를 동시 수정하라.
- 다운로드 파일명 규칙 변경 → `server/app.py`의 산출 파일 탐색/템플릿 로직과 `README.md` 명명 규칙을 동시 수정하라.
- 저장 경로 변경 → `server/app.py` 경로 상수와 `README.md`, `docs/PRD.md`를 동시 수정하라.

## 의사결정 기준
- PRD와 코드가 상충하면 우선 코드의 현실을 따른 뒤, 즉시 PRD를 현실에 맞게 조정하라.
- 무비용 원칙 위반(유료 서비스, 외부 저장/중계)은 금지한다.
- 로컬 전용 원칙을 유지하라. 호스트 바인딩/포트 공개 설정 변경을 금지한다.

## 금지사항
- 서버가 외부 네트워크로 미디어 바이트를 중계하도록 구현하지 마라.
- 근거 없는 추측으로 스펙을 변경하지 마라. 변경 시 반드시 코드/문서 근거를 제시하라.
- 프로젝트 전반 규칙과 무관한 일반 개발 지식 서술을 금지한다.

## 수행 예시
- 해야 할 일:
  - 새로운 `/api/progress` 추가 시 `server/app.py`에 엔드포인트 구현 후 `web/index.html` 폴링 로직 추가, `README.md`/`docs/PRD.md` 스펙 갱신.
  - 파일명 규칙에 해상도 포함 필요 시 `server/app.py` 템플릿/탐색 수정 + 문서 갱신.
- 하지 말아야 할 일:
  - PRD만 바꾸고 실제 API를 갱신하지 않기.
  - web UI에서 하드코딩된 경로를 바꾸고 서버를 갱신하지 않기.

## 체크리스트(커밋 전)
- [ ] 관련 파일 동시 수정 규칙을 모두 반영했는가?
- [ ] 사용자 메시지는 일반적이며 내부 로그는 상세한가?
- [ ] 로컬 전용(127.0.0.1)과 무비용 원칙을 준수하는가?
- [ ] `requirements.txt`가 최신인가?


