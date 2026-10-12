FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONIOENCODING=utf-8
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /opt/studio
COPY production/tubeforge_base/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY production /opt/studio/production
COPY services /opt/studio/services
COPY skills/facelessos /opt/studio/skills/facelessos
COPY output/imagegen/survivor-grounded-bags-2026-10-12/characters /opt/studio/output/imagegen/survivor-grounded-bags-2026-10-12/characters
COPY output/imagegen/survivor-launch-2026-10-12/references /opt/studio/output/imagegen/survivor-launch-2026-10-12/references
COPY output/imagegen/survivor-full-production-2026-10-12/characters /opt/studio/output/imagegen/survivor-full-production-2026-10-12/characters
COPY output/imagegen/survivor-full-production-2026-10-12/masters /opt/studio/output/imagegen/survivor-full-production-2026-10-12/masters
COPY output/imagegen/survivor-full-production-2026-10-12/objects /opt/studio/output/imagegen/survivor-full-production-2026-10-12/objects
COPY output/imagegen/patch-green-zombies-2026-10-12/characters /opt/studio/output/imagegen/patch-green-zombies-2026-10-12/characters
COPY output/imagegen/patch-supermarket-pilot-2026-10-12/masters /opt/studio/output/imagegen/patch-supermarket-pilot-2026-10-12/masters
RUN python production/tubeforge_setup.py --sources-only \
    && python -m venv --system-site-packages /opt/studio/venv \
    && useradd --uid 10001 --create-home tubeforge \
    && chown -R tubeforge:tubeforge /opt/studio/work
USER 10001:10001
WORKDIR /opt/studio/work/TubeForge
EXPOSE 8766
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8766/healthz', timeout=4)"
CMD ["python", "-m", "uvicorn", "app.server:app", "--host", "0.0.0.0", "--port", "8766", "--workers", "1", "--proxy-headers", "--forwarded-allow-ips", "*"]
