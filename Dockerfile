# Read-only dashboard for Cloud Run: saved results only, no runs, no saved settings (DPV_VIEWER=1).
# Which outputs are shipped is set in .gcloudignore. Cached PDFs are never included.
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 DPV_VIEWER=1 TMPDIR=/tmp TEMP=/tmp TMP=/tmp
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt shiny pandas "uvicorn[standard]"
COPY . .
RUN find outputs -iname "*.pdf" -delete && rm -rf outputs/cache outputs/dashboard/private
# No secrets in the image or service: users enter their own Gemini key under Visual Exploration -> Chat (held in memory for that session only).
CMD exec uvicorn dpv_dashboard.app:app --host 0.0.0.0 --port ${PORT:-8080}
