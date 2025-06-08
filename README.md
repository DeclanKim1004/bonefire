# Bonfire of Panghyeon

This repository contains a Discord bot and accompanying web utilities inspired by the "Bonfire" concept. The bot tracks voice channel sessions and exposes a small API used by the web interface.

## Components

- **bonfire_logger.py** – Discord bot that records user voice sessions and provides a `/bonfire` slash command to display the current tunnel URL.
- **bonfire_flask.py** – Flask based web dashboard for managing tracked users/channels and viewing usage reports.
- **bonfire_web.py** – Small FastAPI server placeholder.
- **bonfire_tunnel.py** – Utility to start an ngrok tunnel and write the public URL to `ngrok_url.txt`.

Run `bonfire_tunnel.py` first to expose the FastAPI server, then execute `bonfire_logger.py` and finally start `bonfire_flask.py` to access the dashboard.

