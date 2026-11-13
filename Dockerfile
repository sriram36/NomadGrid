# NomadGrid - Build My Holiday
# One container: FastAPI serves the API, the catalog images and (if present) the built React frontend.
#
# Frontend: when frontend/package.json exists, build it in the first stage; until then this stage is skipped.
FROM node:24-alpine AS frontend
WORKDIR /frontend
COPY frontend/ ./
RUN if [ -f package.json ]; then npm ci && npm run build; else mkdir -p dist; fi

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app
COPY --from=frontend /frontend/dist ./frontend_dist
ENV DATA_DIR=/app/data IMAGES_DIR=/app/images DB_PATH=/app/storage/nomadgrid.sqlite \
    FRONTEND_DIST=/app/frontend_dist PORT=8000
RUN useradd --create-home appuser && mkdir -p /app/storage && chown -R appuser /app/storage
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')"
CMD ["python", "-m", "app"]
