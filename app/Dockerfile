FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY scanhead ./scanhead
COPY static ./static

ENV APP_PORT=8080
EXPOSE 8080

CMD ["sh", "-c", "python -m uvicorn scanhead.main:app --factory --host 0.0.0.0 --port ${APP_PORT:-8080}"]
