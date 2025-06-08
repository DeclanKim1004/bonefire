# Bonfire of Panghyeon

This repository contains a simple Discord bot and web server inspired by the "Bonfire" concept. The bot tracks voice channel sessions and exposes a minimal FastAPI application.

## Components

- **bonfire_logger.py** – Discord bot that records user voice sessions and provides a `/bonfire` slash command to display the current tunnel URL.
- **bonfire_web.py** – Small FastAPI server placeholder.
- **bonfire_tunnel.py** – Utility to start an ngrok tunnel and write the public URL to `ngrok_url.txt`.

Run `bonfire_tunnel.py` first to expose the FastAPI server, then execute `bonfire_logger.py`.
