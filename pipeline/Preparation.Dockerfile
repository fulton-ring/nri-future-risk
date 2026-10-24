FROM python:3.12-slim@sha256:a0f57064cbdcd6285fa45f51237ab0b35ea8ebaed06a1f5973e89e19dfb86704
COPY --from=ghcr.io/astral-sh/uv:0.5.4@sha256:5436c72d52c9c0d011010ce68f4c399702b3b0764adcf282fe0e546f20ebaef6 /uv /usr/local/bin/uv
WORKDIR /app
COPY pipeline/pyproject.toml pipeline/uv.lock ./pipeline/
RUN cd pipeline && uv sync --frozen --no-dev --extra preparation
COPY pipeline/fri_pipeline ./pipeline/fri_pipeline
COPY pipeline/vendor ./pipeline/vendor
COPY pipeline/reference ./pipeline/reference
COPY pipeline/export_snapshot.py ./pipeline/
COPY public/NRI_Future_Risk_Master_Datasheet_12052024.xlsx ./public/
WORKDIR /app/pipeline
ENV FRI_CACHE=/tmp/fri-cache
ENTRYPOINT ["/app/pipeline/.venv/bin/python", "-m", "fri_pipeline.prepare"]
