# The app has no third-party dependencies, so this image is just Python + source.
FROM python:3.12-slim

# Faster, quieter Python in containers.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Copy the application. .dockerignore keeps local data and secrets out.
COPY . .

# The SQLite database and email outbox live here. Mount a persistent volume on
# /app/data in production, or every redeploy will wipe your bookings.
RUN mkdir -p /app/data/outbox

# Most hosts inject $PORT; this is only the fallback for `docker run`.
ENV PORT=8000
EXPOSE 8000

# Run as a non-root user.
RUN useradd --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app
USER appuser

CMD ["python3", "run.py"]
