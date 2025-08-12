# yt-download (로컬 YouTube MP4/MP3 다운로더)

로컬 환경에서 YouTube 영상을 MP4로 저장하거나, 오디오만 추출해 MP3로 저장할 수 있는 경량 도구입니다. FastAPI 서버가 yt-dlp를 통해 포맷 조회/다운로드를 수행하고, 단일 HTML 기반의 Web UI를 함께 제공합니다.

## 주요 기능
- YouTube 영상(MP4) 다운로드 및 오디오(MP3) 추출
  - 영상: `mp4` 컨테이너, `avc1` 코덱 기준으로 해상도별 대표 포맷만 노출
  - 오디오: 비트레이트별 대표 포맷만 노출(m4a 우선)
- 포맷 조회 및 선택 다운로드(Web UI)
- 다운로드 진행률 표시(SSE 기반): 작업 시작 → 진행률 구독 → 완료 시 자동 다운로드
- 파일명 규칙: `제목_영상ID_해상도_formatId.ext` (오디오는 `audio_formatId` 접미사)
- 중복 파일 자동 처리: 동일 파일명 존재 시 `_2`, `_3` … 접미사 부여
- 다운로드 완료 후 `downloads/` 폴더 자동 정리(파일 삭제)

## 기술 스택
- Backend: FastAPI, Uvicorn
- Downloader: yt-dlp (+ FFmpeg 필요: MP3 변환/병합)
- Frontend: 순수 HTML/JS (EventSource 기반 SSE 진행률 표시)
- Infra(Optional): Docker

## 빠른 시작
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python server/app.py  # http://localhost:3001
```

## uv로 실행(선택, 프로젝트 빌드 없이 패키지 설치만)
uv는 빠른 패키지 설치 도구입니다. 본 프로젝트는 폴더 구조상 "프로젝트 빌드(uv sync/run)"가 실패할 수 있으므로, 설치 전용으로 사용하세요.

1) uv 설치
```bash
curl -Ls https://astral.sh/uv/install.sh | sh
```
2) 가상환경 생성 및 활성화
```bash
uv venv
. .venv/bin/activate   # Windows: .venv\Scripts\activate
```
3) 필요한 패키지 설치(프로젝트 빌드/설치 아님)
```bash
uv pip install fastapi uvicorn yt-dlp
```
4) 실행
```bash
python -m uvicorn server.app:app --host 127.0.0.1 --port 3001 --reload
```
5) 접속
```bash
open http://127.0.0.1:3001
```

## Docker 실행(선택)
ffmpeg가 포함된 컨테이너로 손쉽게 실행할 수 있습니다.

```bash
docker build -t yt-download:local .
docker run --rm -p 3001:3001 \
  -v "$(pwd)/downloads:/app/downloads" \
  --name yt-download yt-download:local
```
접속: http://127.0.0.1:3001
```

## 구조(요약)
- `server/app.py` — FastAPI + yt-dlp 백엔드(API + 정적 UI 서빙, SSE 진행률, 파일명/중복 처리, 결과 전송 후 폴더 정리)
- `web/index.html` — 단일 파일 Web UI(포맷 조회/선택, 진행률/속도/ETA 표시)
- `downloads/` — 출력 파일 저장 위치(완료 후 백그라운드 정리)

## 사용법(요약)
1) URL 입력 후 "포맷 조회" 클릭 → 해상도(영상) / 비트레이트(오디오)별 대표 포맷 목록 표시
2) 원하는 항목의 "다운로드" 클릭 → 진행률 바(%)·속도·ETA가 표시됩니다
3) 100%가 되면 브라우저가 자동으로 파일 저장을 시작하고, 서버는 `downloads/` 폴더를 정리합니다
   - 영상: MP4 저장(필요 시 포맷 병합)
   - 오디오: MP3(기본 192kbps) 변환(FFmpeg 필요)

## API

### GET /api/health
- 설명: 서버 상태 확인
- 응답 예:
```json
{"status":"ok"}
```

### GET /api/formats?url=<youtube_url>
- 설명: 대상 URL의 영상/오디오 포맷 메타데이터 조회
- 서버 규칙:
  - 영상: `mp4+avc1`만, 해상도별 대표 1개(`tbr` 최대)
  - 오디오: 비트레이트별 대표 1개(`m4a` 우선)
- 응답 필드: `id`, `title`, `durationSec`, `video[]`, `audio[]`

### GET /api/download?url=<youtube_url>&type=video|audio&format_id=<format_id>
- 설명: 지정 포맷으로 다운로드 수행(기존 동작 유지, 즉시 파일 응답)
- 동작: `type=video` → MP4, `type=audio` → MP3(192kbps)

### POST /api/download/start?url=<youtube_url>&type=video|audio&format_id=<format_id>
- 설명: 다운로드 작업을 생성하고 `job_id` 반환
- 응답 예: `{ "job_id": "..." }`

### GET /api/progress/{job_id}
- 설명: SSE(Server-Sent Events)로 진행률 스트림 전송
- 이벤트 데이터 예: `{ type: 'progress', percent, downloadedBytes, totalBytes, speed, eta }`
- 완료 이벤트: `{ type: 'completed', filename }`

### GET /api/download/result/{job_id}
- 설명: 완료된 작업의 결과 파일 다운로드

## 파일명 규칙
- 출력 템플릿: `<title>_<id>.<ext>` (예: `My_Video_abcd1234.mp4`)
- 제목의 금지 문자는 안전 문자(`_`)로 치환됩니다.
- 오디오는 기본 192kbps MP3로 변환됩니다.

## 정책/법적 고지
- 본 도구는 개인적/합법적 사용 범위에서만 이용하십시오.
- 저작권이 있는 컨텐츠의 무단 다운로드/배포는 금지되며 모든 책임은 사용자에게 있습니다.

## PRD 문서
- docs/PRD.md 를 참고하세요.

## 배포 주의
- 본 서버는 로컬 전용으로 사용하세요(외부에 노출하지 마십시오).
- 서버는 미디어 바이트를 중계하지 않습니다.

## 문제해결(트러블슈팅)
1) 오디오(MP3) 변환 실패/없음
   - ffmpeg가 설치되어 있는지 확인하세요.
   - macOS: `brew install ffmpeg` 후 터미널을 재시작하거나 PATH를 재로드하세요.
2) 네트워크/권한 오류(403/404/Timeout)
   - URL이 유효한지 확인하고, 네트워크 상태를 점검하세요.
   - 일시적 문제일 수 있으니 잠시 후 다시 시도하세요.
3) 저장 공간 부족/권한 문제
   - `downloads/` 폴더의 여유 공간과 쓰기 권한을 확인하세요.
4) 원하는 MP4 포맷이 보이지 않음 또는 다운로드 실패
   - 다른 `format_id`를 선택해 시도하거나, 오디오가 포함된 MP4가 없으면 자동 병합 규칙으로 시도됩니다.
5) yt-dlp 버전 이슈/포맷 추출 실패
   - `pip install -U yt-dlp`로 최신 버전으로 업데이트하세요.
6) 기타 알 수 없는 오류
   - 다시 시도한 뒤에도 반복되면 네트워크/URL/ffmpeg 설치를 순서대로 점검하세요.


