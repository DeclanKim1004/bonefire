# Bonfire of Panghyeon

This repository contains a simple Discord bot and web server inspired by the "Bonfire" concept. The bot tracks voice channel sessions and exposes a minimal FastAPI application.

## Components

- **bonfire_logger.py** – Discord bot that records user voice sessions and provides a `/bonfire` slash command to display the current tunnel URL.
- **bonfire_web.py** – Small FastAPI server placeholder.
- **bonfire_tunnel.py** – Starts an ngrok tunnel, writes the public URL to `ngrok_url.txt` and automatically renews the tunnel every few hours.

Set the `NGROK_AUTH_TOKEN` environment variable if you have one, then run `bonfire_tunnel.py` to expose the FastAPI server. Afterwards execute `bonfire_logger.py`.
