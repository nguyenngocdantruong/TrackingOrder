FROM python:3.11-slim
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && update-ca-certificates \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 ENV_FILE=/config/.env CONF_FILE=/config/config.conf MANAGED_RESTART=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn==23.0.0
COPY app ./app
COPY wsgi.py ./wsgi.py
EXPOSE 8084
CMD ["gunicorn", "--bind", "0.0.0.0:8084", "--workers", "1", "--threads", "4", "--timeout", "90", "wsgi:app"]
