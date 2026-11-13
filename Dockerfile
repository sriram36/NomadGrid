# NomadGrid - Build My Holiday: ONE image that runs everything (web UI + API + catalog images).
#
#   docker build -t nomadgrid .  &&  docker run -p 8000:8000 -v nomadgrid-db:/app/storage nomadgrid
#   (or: docker compose up --build)       then open http://localhost:8000
#
# Fallbacks:
#   --build-arg WITH_UI=false   skip the Node build (API-only image; "/" then shows a page explaining that)
#   the UI build also falls back to "npm install" if there is no usable lockfile, and a failed UI build never
#   stops the image from being produced when WITH_UI=false.

# ---------- stage 1: build the React UI ----------
FROM node:22-alpine AS ui
ARG WITH_UI=true
WORKDIR /ui
COPY frontend/package.json frontend/package-lock.json* ./
RUN if [ "$WITH_UI" = "true" ]; then (npm ci || npm install); fi
COPY frontend/ ./
RUN mkdir -p dist && if [ "$WITH_UI" = "true" ]; then npm run build; fi

# ---------- stage 2: the runtime ----------
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app

COPY backend/requirements.txt ./requirements.txt
RUN pip install -r requirements.txt

COPY backend/app ./app
# the provided catalog + photos travel inside the image (root-owned, so the app can never change them)
COPY hackathon-problem-1-holiday-package/data ./data
COPY hackathon-problem-1-holiday-package/images ./images
COPY --from=ui /ui/dist ./frontend_dist

ENV DATA_DIR=/app/data IMAGES_DIR=/app/images FRONTEND_DIST=/app/frontend_dist \
    DB_PATH=/app/storage/nomadgrid.sqlite HOST=0.0.0.0 PORT=8000

# reservations live here; mount a volume on it to keep them across container re-creates
RUN useradd --create-home appuser && mkdir -p /app/storage && chown appuser /app/storage
USER appuser
VOLUME ["/app/storage"]
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --start-period=5s --retries=5 \
  CMD python -c "import os,urllib.request; urllib.request.urlopen('http://localhost:%s/api/health' % os.environ.get('PORT','8000'))"
CMD ["python", "-m", "app"]
