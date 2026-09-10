FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /srv

COPY shared /srv/shared
RUN pip install --no-cache-dir /srv/shared

COPY services/engine/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/engine/app /srv/app
COPY services/engine/data /srv/data
CMD ["python", "-m", "app.main"]
