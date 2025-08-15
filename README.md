# mc-server-bot

Two-container setup:
- **banner**: Flask app that pings your Minecraft server and renders a PNG banner.
- **discord-refresher**: Sidecar that edits a Discord webhook message every N seconds to force Discord to fetch a fresh image URL (`?v=<timestamp>`).

## Quick start

1. Copy `.env.example` to `.env` and set `WEBHOOK_URL`.
2. Edit `docker-compose.yml` → set `SERVER_ADDRESS` and `SERVER_NAME`.
3. (Optional) Put a 128x128 PNG in `banner/assets/icon.png`.
4. Start:
   - Windows: `run.bat`
   - Linux/macOS: `chmod +x run.sh && ./run.sh`

Banner URL: `http://localhost:8080/banner.png`  
Discord refresher targets `BANNER_URL` from `.env` (default to the banner service inside compose).

## Notes
- Discord aggressively caches images. The refresher updates the embed with `?v=<timestamp>` so it re-fetches.
- Persisted message id lives in the `refresher_state` volume; restarts continue editing the same message.
