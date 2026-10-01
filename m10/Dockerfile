FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app/m10:/app/src OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 M10_DATA_DIR=/data M10_SOURCE_DIR=/sources
WORKDIR /app
COPY m10/requirements-lock.txt /tmp/requirements-lock.txt
RUN pip install --no-cache-dir -r /tmp/requirements-lock.txt
COPY pyproject.toml README.md LICENSE AUTHORS.rst ./
COPY src ./src
COPY ModelFiles ./ModelFiles
COPY profiles ./profiles
COPY configs ./configs
COPY m10/requirements-lock.txt ./m10/requirements-lock.txt
COPY m10/metabocore ./m10/metabocore
COPY m10/web ./m10/web
COPY m10/config ./m10/config
RUN pip install --no-deps . && useradd --uid 10001 --create-home m10 && mkdir /data && chown m10:m10 /data
USER 10001
EXPOSE 8050
HEALTHCHECK --interval=30s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8050/healthz')"
CMD ["python","-m","uvicorn","metabocore.api:app","--host","0.0.0.0","--port","8050","--no-access-log"]
