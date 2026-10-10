FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV HF_HOME=/app/model_cache

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 10000

CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-10000} --workers 1 --timeout 300 ragchatbot:app"]