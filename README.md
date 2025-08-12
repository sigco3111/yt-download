# 로컬 YouTube MP4/MP3 다운로더

로컬 환경에서 YouTube 영상을 MP4로 저장하거나, 오디오만 추출해 MP3로 저장할 수 있는 경량 도구입니다. FastAPI 서버가 yt-dlp를 통해 포맷 조회/다운로드를 수행하고, 단일 HTML 기반 Web UI를 제공합니다.

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

## 빠른 시작(개발자 간단 실행)
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

## 초보자용: 1분 설치/실행 가이드

### Windows에서 Docker Desktop 설치(사전 준비)
- 권장: Windows 10/11 64-bit, WSL2 사용
- PowerShell(관리자)에서 아래를 순서대로 실행
```powershell
# 1) WSL2 설치(재부팅 필요할 수 있음)
wsl --install

# 2) Docker Desktop 설치(winget)
winget install -e --id Docker.DockerDesktop

# 3) 재부팅 후 Docker Desktop 실행(고래 아이콘 확인)
# 4) 동작 확인
docker version
```
- 수동 설치 경로: Docker Desktop 다운로드 페이지(`https://www.docker.com/products/docker-desktop`)
- 회사 PC 등에서 WSL 설치가 제한될 경우, Docker Desktop 설정에서 Hyper-V 백엔드(Windows Pro/Enterprise) 사용 가능

### 권장 1) Docker로 한 번에 실행(Windows/macOS)
```bash
./scripts/run_docker.sh
```
- 실행 전 Docker Desktop 설치 필요. 스크립트가 이미지 빌드 → 컨테이너 실행 → 브라우저 자동 오픈을 수행합니다.

### Windows: 로컬 실행(winget + 가상환경)
```powershell
./scripts/run_local_win.ps1
```
- 필요한 경우 Python/FFmpeg 설치 가이드를 출력하고, 가상환경 생성 → 의존성 설치 → 서버 실행을 자동화합니다.

### macOS: 로컬 실행(Homebrew + 가상환경)
```bash
chmod +x ./scripts/run_local_mac.sh
./scripts/run_local_mac.sh
```
- ffmpeg 미설치 시 설치 방법을 안내하고, 가상환경 생성 → 의존성 설치 → 서버 실행을 자동화합니다.

실행 후 브라우저에서 `http://127.0.0.1:3001` 로 접속하세요.

### Windows PowerShell 스크립트 실행/문제 해결

- 관리자 PowerShell 권장. 실행 정책이 제한된 경우 아래를 먼저 실행:
```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```
- 실행 방법
```powershell
cd C:\work\yt-download   # 프로젝트 경로로 이동
./scripts/run_local_win.ps1
# 포트를 바꾸려면
./scripts/run_local_win.ps1 -Port 3002
```
- 자주 발생하는 오류와 해결
  - 실행 정책 오류(Restricted): 위의 `Set-ExecutionPolicy` 실행 후 PowerShell 재시작
  - 스크립트를 로드할 수 없습니다: 동일하게 실행 정책 완화 필요
  - 경로 문제(한글/공백 경로): 프로젝트를 `C:\work\yt-download` 같은 영문 경로로 이동하여 재시도
  - Python/FFmpeg 미설치: 아래 명령으로 설치 후 재시도
    ```powershell
    winget install --id Python.Python.3.10 -e
    winget install --id Gyan.FFmpeg -e
    ```
  - 기타: PowerShell 재시작 후 다시 시도. 문제가 지속되면 오류 메시지 전체와 함께 이슈로 남겨주세요.

## 구조(요약)
- `server/app.py` — FastAPI + yt-dlp 백엔드(API + 정적 UI 서빙, SSE 진행률, 파일명/중복 처리, 결과 전송 후 폴더 정리)
- `web/index.html` — 단일 파일 Web UI(포맷 조회/선택, 모달 진행률/속도/ETA 표시)
- `downloads/` — 출력 파일 저장 위치(완료 후 백그라운드 정리)

## 사용법(초보자용 요약)
1) 브라우저에서 `http://127.0.0.1:3001` 접속
2) 유튜브 URL 입력 → "포맷 조회" 클릭
3) 해상도/비트레이트 드롭다운에서 원하는 값 선택(기본값은 최고 품질 자동 선택)
4) "MP4 다운로드" 또는 "MP3 다운로드" 클릭
5) 다운로드 중에는 전체 화면 모달에 진행률이 표시되며, 완료 시 자동 저장됩니다

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
- `docs/PRD.md` 참고

## 배포 주의
- 본 서버는 로컬 전용으로 사용하세요(외부에 노출하지 마십시오).
- 서버는 미디어 바이트를 중계하지 않습니다.

## 문제해결(트러블슈팅)
1) ffmpeg 오류
   - Windows: winget 또는 Microsoft Store에서 FFmpeg 설치 후 PowerShell 재시작
   - macOS: `brew install ffmpeg` 후 터미널 재시작
2) 포트 충돌(3001 사용 중)
   - 다른 앱 종료 또는 실행 스크립트의 포트를 변경해 실행
3) 권한 문제(Windows PowerShell 스크립트 실행 차단)
   - 관리자 PowerShell에서 `Set-ExecutionPolicy RemoteSigned` 후 다시 시도
4) 네트워크/403 오류
   - URL 확인 → 잠시 후 재시도 → 다른 해상도/비트레이트 선택 후 시도


