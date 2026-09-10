FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /srv

COPY shared /srv/shared
RUN pip install --no-cache-dir /srv/shared

COPY services/webhook/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/webhook/app /srv/app
EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
