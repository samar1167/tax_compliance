FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend /app
COPY knowledge_base /knowledge_base

EXPOSE 9010

CMD ["sh", "-c", "python manage.py migrate && python manage.py sync_kb_snapshot && python manage.py runserver 0.0.0.0:9010"]
