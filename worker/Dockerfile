FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN useradd --uid 10001 --create-home appuser
COPY --chown=10001:10001 probe.py .
USER 10001:10001
CMD ["python", "probe.py"]
