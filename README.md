# Bonefire of Panghyeon

This repository contains a Discord bot and accompanying web utilities inspired by the "Bonefire" concept. The bot tracks voice channel sessions and exposes a small API used by the web interface.

## Components

- **bonefire_logger.py** – Discord bot that records user voice sessions and provides a `/bonefire` slash command to display the current tunnel URL.
- **bonefire_flask.py** – Flask based web dashboard for managing tracked embers/pyres and viewing flame reports.
- **bonefire_tunnel.py** – Starts an ngrok tunnel, writes the public URL to `ngrok_url.txt` and automatically renews the tunnel every few hours.

The Flask dashboard and ngrok tunnel listen on port **5000**, while the Discord
logger exposes its FastAPI endpoints on port **8000**.

======
## Installation

Clone the repository and install the Python dependencies:

```bash
git clone https://github.com/Phxntxm/Bonefire.git
cd Bonefire
python3 -m pip install --upgrade -r requirements.txt
```

Create a `config.json` file in the project root after cloning. This configuration is loaded by both the Flask dashboard and the Discord logger. An example path would be `/opt/bonefire/config.json` when running the service.

