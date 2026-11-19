FROM python:3.12.16-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ .

USER 65534:65534
EXPOSE 8000
# One worker, as under Apache: the status cache lives in the process.
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "1", "--threads", "8", "--worker-tmp-dir", "/dev/shm", "app:app"]
