# 목적: FastAPI(uvicorn) + yt-dlp + ffmpeg 로컬 실행 컨테이너 이미지

FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# ffmpeg 및 필수 패키지 설치
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       ffmpeg ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 의존성 설치
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 복사
COPY . /app

EXPOSE 3001

# uvicorn으로 앱 기동
CMD ["uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "3001"]


