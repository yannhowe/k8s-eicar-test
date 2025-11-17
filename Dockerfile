FROM python:3.11-alpine

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UPLOAD_DIR=/data/uploads \
    PORT=8080

WORKDIR /app

RUN apk add --no-cache bash curl

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

RUN adduser -D -h /home/appuser appuser \
    && mkdir -p ${UPLOAD_DIR} \
    && chown -R appuser:appuser /app ${UPLOAD_DIR}

USER appuser

EXPOSE 8080

CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:8080", "app.main:app"]
