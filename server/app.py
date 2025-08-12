"""
FastAPI 기반 로컬 전용 백엔드 서버
- 목적: yt-dlp를 직접 사용하여 포맷 조회 및 다운로드(mp4/mp3)를 제공
- 전제: 로컬에 ffmpeg 설치 필요(오디오 mp3 변환에 사용)
"""
from fastapi import FastAPI, HTTPException, Query, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import os
import re
import uuid
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
import asyncio
import threading
import time
import json
from queue import Queue, Empty

import yt_dlp


# 기본 설정
# - 경로/출력 템플릿/기본 포맷 등 상수를 한 곳에서 관리한다.
BASE_DIR = Path(__file__).resolve().parent.parent
DOWNLOAD_DIR = BASE_DIR / "downloads"
WEB_DIR = BASE_DIR / "web"

# 파일명 템플릿: <title>_<id>.<ext>
OUTPUT_NAMING_TEMPLATE = "{title}_{id}.%(ext)s"

# yt-dlp 기본 포맷 규칙(영상/오디오)
DEFAULT_VIDEO_FMT = "best[ext=mp4]/bestvideo[ext=mp4]+bestaudio[ext=m4a]/best"
DEFAULT_AUDIO_FMT = "bestaudio/best"

DOWNLOAD_DIR.mkdir(exist_ok=True, parents=True)
WEB_DIR.mkdir(exist_ok=True, parents=True)

logger = logging.getLogger("ytserver")
logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")


def sanitize_filename(name: str) -> str:
    """파일명에 사용할 문자열을 단순 정제"""
    if not name:
        return "untitled"
    return re.sub(r'[\\/\n\r\t\0\x0B:*?"<>|]', "_", name).strip()[:180]


def ydl_base_opts() -> Dict[str, Any]:
    """yt-dlp 공통 옵션 생성(로그 최소화, 과도한 출력 억제)"""
    return {
        "quiet": True,
        "noprogress": True,
        "ignoreerrors": False,
        "no_warnings": True,
        "cachedir": False,
        # outtmpl은 다운로드 시점에 명시적으로 지정한다.
    }


def build_output_template(video_title: str, video_id: str, extra_suffix: Optional[str] = None) -> str:
    """출력 파일 템플릿 경로 생성
    - 목적: 파일명 규칙을 한 곳에서 관리하여 유지보수를 단순화
    - 반환: 절대경로 기반의 yt-dlp outtmpl 문자열
    """
    safe_title = sanitize_filename(video_title)
    template = OUTPUT_NAMING_TEMPLATE.format(title=safe_title, id=video_id)
    if extra_suffix:
        # 확장자 전에 접미사를 안전하게 삽입: ".%(ext)s"를 기준으로 처리
        suffix_marker = ".%(ext)s"
        if template.endswith(suffix_marker):
            template = template[: -len(suffix_marker)] + f"_{extra_suffix}" + suffix_marker
        else:
            # 방어적 처리: 예상 외 템플릿이면 그냥 뒤에 접미사만 추가
            template = template + f"_{extra_suffix}"
    return str(DOWNLOAD_DIR / template)


def _remove_ext_placeholder(outtmpl: str) -> str:
    """outtmpl 문자열에서 .%(ext)s 플레이스홀더를 제거한 베이스 경로 반환
    - 목적: 최종 파일 확장자를 모르는 상태에서 중복 파일 검사를 수행하기 위함
    """
    suffix = ".%(ext)s"
    if outtmpl.endswith(suffix):
        return outtmpl[: -len(suffix)]
    return outtmpl


def ensure_unique_outtmpl(outtmpl: str) -> str:
    """기존 파일과 이름 충돌 시 숫자 접미사를 붙여 유니크한 outtmpl을 생성
    - 규칙: <base>.<ext> 존재 시 <base>_2.<ext>, <base>_3.<ext> ... 순으로 탐색
    - 예외 처리: 과도한 시도 시 마지막 후보를 반환(현실적으로 발생 가능성 낮음)
    """
    try:
        base_noext_path = _remove_ext_placeholder(outtmpl)
        base_name = Path(base_noext_path).name
        # 기본이 비어있지 않다면 그대로 사용 가능 여부 검사
        if not any(DOWNLOAD_DIR.glob(f"{base_name}.*")):
            return outtmpl

        # 접미사 증가하여 가용 이름 탐색
        for idx in range(2, 1000):
            candidate_name = f"{base_name}_{idx}"
            if not any(DOWNLOAD_DIR.glob(f"{candidate_name}.*")):
                return str(DOWNLOAD_DIR / f"{candidate_name}.%(ext)s")

        # fallback: 매우 드문 케이스로, 마지막 후보 반환
        return str(DOWNLOAD_DIR / f"{base_name}_999.%(ext)s")
    except Exception:
        # 실패 시 원본 유지(추후 yt-dlp에서 overwrite 될 수 있음)
        logger.exception("ensure_unique_outtmpl 실패")
        return outtmpl


def _make_suffix_from_info(info: Dict[str, Any], dlt_type: str, format_id: Optional[str]) -> Optional[str]:
    """포맷 정보로부터 파일명 접미사 생성
    - 영상: <width>x<height>_<format_id>
    - 오디오: audio_<format_id>
    - format_id가 없으면 None 반환
    """
    if not format_id:
        return None


def _cleanup_downloads_dir() -> None:
    """downloads 폴더 내의 파일들을 제거하는 정리 작업
    - 목적: 브라우저 다운로드 전송이 끝난 뒤 디스크 사용량을 최소화
    - 예외 처리: 삭제 실패는 로깅만 수행
    """
    try:
        for p in DOWNLOAD_DIR.glob("*"):
            try:
                if p.is_file():
                    p.unlink(missing_ok=True)
            except Exception:
                logger.exception("파일 삭제 실패: %s", p)
    except Exception:
        logger.exception("downloads 정리 작업 실패")


def _cleanup_job(job_id: str) -> None:
    """완료된 작업 정보를 메모리에서 제거"""
    try:
        _JOBS.pop(job_id, None)
    except Exception:
        logger.exception("작업 정리 실패: %s", job_id)


app = FastAPI(title="yt-dlp local server", version="1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> Dict[str, str]:
    """헬스 체크 엔드포인트"""
    return {"status": "ok"}


@app.get("/api/formats")
def list_formats(url: str = Query(..., description="YouTube URL")) -> Dict[str, Any]:
    """포맷 목록 조회
    - 목적: 프런트에서 사용자에게 선택지를 보여주기 위해 포맷 메타 제공
    """
    try:
        opts = ydl_base_opts()
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
        title = info.get("title") or ""
        vid = info.get("id") or str(uuid.uuid4())
        duration = info.get("duration")
        formats = info.get("formats") or []

        # 영상: avc1 코덱 + mp4 컨테이너만 유지하고, 해상도별로 하나(최고 tbr)만 노출
        # 오디오: 비트레이트(tbr) 기준으로 하나씩만 노출(가급적 m4a 우선)
        video_by_res: Dict[str, Dict[str, Any]] = {}
        audio_by_bitrate: Dict[int, Dict[str, Any]] = {}

        for f in formats:
            ext = f.get("ext")
            acodec = f.get("acodec")
            vcodec = f.get("vcodec")
            width = f.get("width")
            height = f.get("height")
            tbr = f.get("tbr")

            # 영상 필터: mp4 컨테이너 + avc1 계열만 유지
            if vcodec and vcodec != "none" and ext == "mp4" and str(vcodec).startswith("avc1") and width and height:
                key = f"{int(width)}x{int(height)}"
                prev = video_by_res.get(key)
                # 더 높은 tbr을 우선 선택
                if prev is None or (tbr or 0) > (prev.get("tbr") or 0):
                    video_by_res[key] = {
                        "format_id": f.get("format_id"),
                        "ext": ext,
                        "hasAudio": (acodec not in (None, "none")),
                        "width": width,
                        "height": height,
                        "fps": f.get("fps"),
                        "tbr": tbr,
                        "vcodec": vcodec,
                        "acodec": acodec,
                    }

            # 오디오 필터: 오디오가 존재하고 비트레이트가 있는 항목만 사용
            if acodec and acodec != "none" and (tbr is not None):
                try:
                    key_br = int(round(float(tbr)))
                except Exception:
                    continue
                prev = audio_by_bitrate.get(key_br)
                # m4a(ext==m4a)를 우선, 그 다음 높은 tbr/안정적인 코덱 우선
                prefer_new = False
                if prev is None:
                    prefer_new = True
                else:
                    if (ext == "m4a") and (prev.get("ext") != "m4a"):
                        prefer_new = True
                    elif (tbr or 0) > (prev.get("tbr") or 0):
                        prefer_new = True
                if prefer_new:
                    audio_by_bitrate[key_br] = {
                        "format_id": f.get("format_id"),
                        "ext": ext,
                        "hasAudio": True,
                        "width": None,
                        "height": None,
                        "fps": None,
                        "tbr": tbr,
                        "vcodec": vcodec,
                        "acodec": acodec,
                    }

        # 정렬: 영상은 해상도(넓이*높이) 오름차순, 오디오는 비트레이트 오름차순
        video_list = sorted(
            video_by_res.values(), key=lambda x: (int(x.get("width") or 0) * int(x.get("height") or 0), x.get("tbr") or 0)
        )
        audio_list = [audio_by_bitrate[k] for k in sorted(audio_by_bitrate.keys())]

        return {
            "id": vid,
            "title": title,
            "durationSec": duration,
            "video": video_list,
            "audio": audio_list,
        }
    except Exception as e:
        logger.exception("/api/formats 실패")
        raise HTTPException(status_code=502, detail="포맷 조회에 실패했습니다. 잠시 후 다시 시도해 주세요.") from e


# ============================
# 다운로드 진행률(SSE) 지원 구현
# ============================

# Job 상태 저장용 자료구조
# - 메모리 저장(서버 재시작 시 초기화됨)
_JOBS: Dict[str, Dict[str, Any]] = {}

def _create_job(url: str, dlt_type: str, format_id: Optional[str]) -> str:
    """다운로드 작업을 생성하고 백그라운드 스레드에서 yt-dlp를 실행
    - 목적: 프런트에서 SSE로 진행률을 받을 수 있도록 작업 큐/상태를 구성
    - 반환: job_id(UUID4)
    """
    job_id = str(uuid.uuid4())
    _JOBS[job_id] = {
        # 표준 스레드 안전 큐로 진행 이벤트 전달
        "queue": Queue(),
        "is_done": False,
        "is_error": False,
        "error_message": None,
        "file_path": None,
        "meta": {"url": url, "type": dlt_type, "format_id": format_id},
        "created_at": time.time(),
    }

    # 백엔드 다운로드 실행 함수
    def _run_download():
        """스레드에서 실행되는 실제 다운로드 수행 함수
        - yt-dlp progress_hooks를 사용하여 진행률을 job_queue로 전달
        - 완료 후 파일 경로를 탐색하여 상태 업데이트
        """
        try:
            # 사전 정보 추출(제목/ID 확보)
            base_opts = ydl_base_opts()
            with yt_dlp.YoutubeDL(base_opts) as ydl:
                pre = ydl.extract_info(url, download=False)
            vid = pre.get("id") or str(uuid.uuid4())
            title = sanitize_filename(pre.get("title") or vid)

            # 파일명 접미사(해상도_format_id / audio_format_id)
            extra_suffix = _make_suffix_from_info(pre, dlt_type, format_id)
            outtmpl_base = build_output_template(title, vid, extra_suffix)
            outtmpl_base = ensure_unique_outtmpl(outtmpl_base)

            if dlt_type == "video":
                fmt = format_id or DEFAULT_VIDEO_FMT
                dl_opts = {
                    **base_opts,
                    "format": fmt,
                    "outtmpl": outtmpl_base,
                    "merge_output_format": "mp4",
                }
            else:
                fmt = format_id or DEFAULT_AUDIO_FMT
                dl_opts = {
                    **base_opts,
                    "format": fmt,
                    "outtmpl": outtmpl_base,
                    "postprocessors": [
                        {
                            "key": "FFmpegExtractAudio",
                            "preferredcodec": "mp3",
                            "preferredquality": "192",
                        }
                    ],
                }

            # 진행률 콜백
            def _hook(d: Dict[str, Any]):
                # 복잡한 상태를 단순화하여 전송(진행률, 속도, ETA 등)
                try:
                    status = d.get("status")
                    total = d.get("total_bytes") or d.get("total_bytes_estimate")
                    downloaded = d.get("downloaded_bytes")
                    speed = d.get("speed")
                    eta = d.get("eta")
                    percent = None
                    if total and downloaded is not None and total > 0:
                        percent = max(0.0, min(100.0, (downloaded / total) * 100.0))

                    payload = {
                        "type": "progress",
                        "status": status,
                        "downloadedBytes": downloaded,
                        "totalBytes": total,
                        "percent": percent,
                        "speed": speed,
                        "eta": eta,
                    }
                    # 스레드 안전 큐에 바로 적재
                    _JOBS[job_id]["queue"].put(payload)
                except Exception:
                    # 훅 내부 오류는 로깅만 수행
                    logger.exception("progress hook error")

            # 후처리 훅: 병합/리멕스/오디오 추출 완료 시 최종 파일 경로 확보
            final_path_holder = {"path": None}

            def _post_hook(d: Dict[str, Any]):
                try:
                    if d.get("status") == "finished":
                        info = d.get("info_dict") or {}
                        # yt-dlp는 filepath 또는 filename 키를 제공할 수 있음
                        fp = info.get("filepath") or info.get("filename") or info.get("_filename")
                        if fp and os.path.exists(fp):
                            final_path_holder["path"] = fp
                except Exception:
                    logger.exception("postprocessor hook error")

            dl_opts["progress_hooks"] = [_hook]
            dl_opts["postprocessor_hooks"] = [_post_hook]

            # 실제 다운로드 수행
            with yt_dlp.YoutubeDL(dl_opts) as ydl:
                ydl.download([url])

            # 최종 파일 경로 결정: 훅에서 받은 경로 우선, 없으면 템플릿 기반 탐색
            file_path = final_path_holder.get("path")
            if not file_path:
                search_base = Path(_remove_ext_placeholder(outtmpl_base)).name
                candidates = sorted(
                    DOWNLOAD_DIR.glob(f"{search_base}.*"),
                    key=lambda p: p.stat().st_mtime,
                    reverse=True,
                )
                if not candidates:
                    raise FileNotFoundError("출력 파일을 찾지 못했습니다.")
                file_path = str(candidates[0])

            _JOBS[job_id]["file_path"] = str(file_path)
            _JOBS[job_id]["is_done"] = True

            # 완료 이벤트 알림
            filename_only = os.path.basename(file_path)
            complete_payload = {
                "type": "completed",
                "filename": filename_only,
            }
            _JOBS[job_id]["queue"].put(complete_payload)
        except Exception as e:
            logger.exception("백그라운드 다운로드 실패")
            _JOBS[job_id]["is_error"] = True
            _JOBS[job_id]["error_message"] = str(e)
            # 파일이 이미 존재하면 에러 대신 완료로 처리(일부 훅 미발화 대비)
            try:
                # 템플릿 기반으로 한 번 더 탐색
                search_base = Path(_remove_ext_placeholder(outtmpl_base)).name
                candidates = sorted(
                    DOWNLOAD_DIR.glob(f"{search_base}.*"),
                    key=lambda p: p.stat().st_mtime,
                    reverse=True,
                )
                if candidates:
                    fp = str(candidates[0])
                    _JOBS[job_id]["file_path"] = fp
                    _JOBS[job_id]["is_done"] = True
                    complete_payload = {"type": "completed", "filename": Path(fp).name}
                    _JOBS[job_id]["queue"].put(complete_payload)
                    return
            except Exception:
                pass

            error_payload = {"type": "error", "message": "다운로드 중 문제가 발생했습니다."}
            try:
                _JOBS[job_id]["queue"].put(error_payload)
            except Exception:
                pass

    t = threading.Thread(target=_run_download, daemon=True)
    t.start()
    _JOBS[job_id]["thread"] = t
    return job_id


@app.post("/api/download/start")
def start_download(
    url: str = Query(..., description="YouTube URL"),
    type: str = Query("video", pattern="^(video|audio)$"),
    format_id: Optional[str] = Query(None),
) -> JSONResponse:
    """다운로드 작업을 시작하고 job_id를 반환
    - 프런트는 job_id로 `/api/progress/{job_id}` SSE를 구독하고, 완료 후 결과를 받는다
    """
    try:
        job_id = _create_job(url=url, dlt_type=type, format_id=format_id)
        return JSONResponse({"job_id": job_id})
    except Exception as e:
        logger.exception("/api/download/start 실패")
        raise HTTPException(status_code=500, detail="작업 시작에 실패했습니다. 매개변수를 확인하세요.") from e


@app.get("/api/progress/{job_id}")
async def stream_progress(request: Request, job_id: str):
    """SSE로 진행률을 스트리밍 전송
    - 클라이언트는 EventSource로 구독
    - 연결 유지를 위해 주기적 heartbeat 전송
    """
    job = _JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="존재하지 않는 작업입니다.")

    q: Queue = job["queue"]

    async def event_generator():
        # 주기적으로 하트비트를 전송하여 연결 유지
        HEARTBEAT_INTERVAL_SEC = 15
        last_sent = time.time()
        try:
            while True:
                # 클라이언트 연결 종료 체크
                if await request.is_disconnected():
                    break

                try:
                    # 논블로킹으로 큐 소비
                    item = q.get_nowait()
                    data = json.dumps(item, ensure_ascii=False)
                    yield f"data: {data}\n\n"
                    last_sent = time.time()
                except Empty:
                    # 큐가 비어있으면 잠시 대기 후 하트비트
                    await asyncio.sleep(0.5)
                    if time.time() - last_sent > HEARTBEAT_INTERVAL_SEC:
                        yield "event: heartbeat\ndata: ping\n\n"
                        last_sent = time.time()

                # 작업이 끝났고 큐도 비어 있으면 종료
                if job.get("is_done") or job.get("is_error"):
                    if q.empty():
                        break
        except Exception:
            # 제너레이터 내부 예외는 스트림 종료
            logger.exception("SSE 전송 중 오류")

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/api/download/result/{job_id}")
def download_result(job_id: str, background_tasks: BackgroundTasks) -> FileResponse:
    """작업 결과 파일을 전송
    - 완료된 작업의 결과물을 파일 응답으로 반환
    """
    job = _JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="존재하지 않는 작업입니다.")
    if job.get("is_error"):
        raise HTTPException(status_code=500, detail="작업 처리 중 오류가 발생했습니다.")
    file_path = job.get("file_path")
    if not file_path:
        raise HTTPException(status_code=202, detail="아직 파일이 준비되지 않았습니다.")

    filename = os.path.basename(file_path)
    # 응답 전송 후 백그라운드로 폴더 정리 + 잡 정리 수행
    background_tasks.add_task(_cleanup_downloads_dir)
    background_tasks.add_task(_cleanup_job, job_id)
    return FileResponse(path=file_path, filename=filename, media_type="application/octet-stream")


@app.get("/api/download")
def download(
    url: str = Query(..., description="YouTube URL"),
    type: str = Query("video", pattern="^(video|audio)$"),
    format_id: str | None = Query(None, description="yt-dlp format_id. 생략 시 기본 규칙 적용"),
) -> FileResponse:
    """다운로드/변환 수행 후 파일 응답
    - type=video => mp4 우선 규칙
    - type=audio => mp3 변환(FFmpeg 필수)
    """
    try:
        # 기본 정보 추출로 id/title 확보
        base_opts = ydl_base_opts()
        with yt_dlp.YoutubeDL(base_opts) as ydl:
            pre = ydl.extract_info(url, download=False)
        vid = pre.get("id") or str(uuid.uuid4())
        title = sanitize_filename(pre.get("title") or vid)

        # 출력 파일 템플릿: 제목_ID_res_format.ext 형태 + 중복 시 숫자 접미사
        extra_suffix = _make_suffix_from_info(pre, type, format_id)
        outtmpl_base = build_output_template(title, vid, extra_suffix)
        outtmpl_base = ensure_unique_outtmpl(outtmpl_base)

        if type == "video":
            # mp4 우선 규칙(명시 포맷이 있으면 그대로 사용)
            fmt = format_id or DEFAULT_VIDEO_FMT
            dl_opts = {
                **base_opts,
                "format": fmt,
                "outtmpl": outtmpl_base,
                "merge_output_format": "mp4",
            }
        else:
            # 오디오 mp3 추출
            fmt = format_id or DEFAULT_AUDIO_FMT
            dl_opts = {
                **base_opts,
                "format": fmt,
                "outtmpl": outtmpl_base,
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }
                ],
            }

        # 다운로드 수행
        with yt_dlp.YoutubeDL(dl_opts) as ydl:
            ydl.download([url])

        # 결과 파일 탐색(템플릿 기반, 접미사 포함 대응)
        search_base = Path(_remove_ext_placeholder(outtmpl_base)).name
        candidates = sorted(
            DOWNLOAD_DIR.glob(f"{search_base}.*"), key=lambda p: p.stat().st_mtime, reverse=True
        )
        if not candidates:
            # 훅 미발화 대비: yt-dlp가 직접 리턴한 파일 경로가 있는지 검사할 수 없으므로 502 처리
            raise FileNotFoundError("출력 파일을 찾지 못했습니다.")
        file_path = candidates[0]

        download_name = file_path.name
        return FileResponse(
            path=str(file_path),
            filename=download_name,
            media_type="application/octet-stream",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("/api/download 실패")
        raise HTTPException(status_code=500, detail="다운로드에 실패했습니다. 설정/네트워크/ffmpeg를 확인하세요.") from e


# 정적 Web UI 서빙
app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")


if __name__ == "__main__":
    import uvicorn

    # 개발 편의 실행: uvicorn server.app:app --reload --port 3001
    uvicorn.run("server.app:app", host="0.0.0.0", port=3001, reload=True)


