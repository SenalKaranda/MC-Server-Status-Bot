FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY refresh_webhook.py .
RUN chmod +x /app/refresh_webhook.py

VOLUME ["/state"]

ENV INTERVAL=60
ENV STATE_FILE=/state/message_id.txt

CMD ["python", "/app/refresh_webhook.py"]
