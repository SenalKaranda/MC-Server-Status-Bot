FROM python:3.12-slim

# Fonts for better text rendering
RUN apt-get update && apt-get install -y --no-install-recommends fonts-dejavu-core && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY assets /app/assets
EXPOSE 8080

# Defaults; override via compose ENV or query params
ENV SERVER_ADDRESS=127.0.0.1:25565
ENV SERVER_NAME="My Minecraft Server"
ENV ACCENT_HEX="#40E28C"
ENV ICON_FILE="/app/assets/icon.png"

CMD ["python", "app.py"]
