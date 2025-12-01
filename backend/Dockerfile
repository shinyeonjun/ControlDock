FROM python:3.10-slim

WORKDIR /app

# 시스템 패키지 업데이트 및 필요한 도구 설치
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Python 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 코드 복사 (.dockerignore에 의해 .venv 등은 제외됨)
COPY database/ ./database/
COPY server/ ./server/
COPY main.py .

# 포트 노출
# 8000: HTTP 서버
# 5500: TCP 서버 (에이전트 등록)
# 5501: UDP 서버 (하트비트)
# 5502: UDP 서버 (공지 브로드캐스트)
EXPOSE 8000 5500 5501/udp 5502/udp

# 서버 시작 (unbuffered 모드로 로그 즉시 출력)
CMD ["python", "-u", "main.py"]

