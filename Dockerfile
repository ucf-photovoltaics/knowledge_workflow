# Read-only dashboard for Cloud Run: saved results only, no runs, no saved settings (DPV_VIEWER=1).
# Which outputs are shipped is set in .gcloudignore. Cached PDFs are never included.
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 DPV_VIEWER=1 TMPDIR=/tmp TEMP=/tmp TMP=/tmp
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt shiny pandas "uvicorn[standard]"
COPY . .
RUN mkdir -p dashboard-documentation && cp -a outputs/development/codebase-docs/webvowl/. dashboard-documentation/
RUN find outputs -iname "*.pdf" -delete && rm -rf outputs/cache outputs/dashboard/private
# DPV_ACCESS_CONFIG points to a private runtime-mounted JSON file; never bake credentials into the image.
# DPV_VIEWER remains independent: team login does not enable execution in this read-only deployment.
CMD exec uvicorn dpv_dashboard.app:app --host 0.0.0.0 --port ${PORT:-8080}
