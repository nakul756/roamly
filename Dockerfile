FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# the app runs as an unprivileged user; it needs to write the databases (/data) and, on first start, the trained models
RUN useradd --system --uid 10001 --no-create-home app \
 && mkdir -p /data \
 && chown -R app:app /app /data
# databases live in a volume so they survive restarts; the ranking model is trained on first start (about 15 s)
ENV TRAVEL_DATA_DIR=/data
VOLUME /data
USER app
EXPOSE 8000
WORKDIR /app/backend
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
