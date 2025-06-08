# Bonefire of Panghyeon

This repository contains a Discord bot and accompanying web utilities inspired by the "Bonefire" concept. The bot tracks voice channel sessions and exposes a small API used by the web interface.

## Components

- **bonefire_logger.py** – Discord bot that records user voice sessions and provides a `/bonefire` slash command to display the current tunnel URL.
- **bonefire_flask.py** – Flask based web dashboard for managing tracked embers/pyres and viewing flame reports.
- **bonefire_web.py** – Small FastAPI server placeholder.
- **bonefire_tunnel.py** – Starts an ngrok tunnel, writes the public URL to `ngrok_url.txt` and automatically renews the tunnel every few hours.

======
## Installation

Clone the repository and install the Python dependencies:

```bash
git clone https://github.com/Phxntxm/Bonefire.git
cd Bonefire
python3 -m pip install --upgrade -r requirements.txt
```
## Systemd Setup
Service files for running the logger, web dashboard and ngrok tunnel with `systemctl` live in the `systemd/` directory. The `install_systemd.sh` helper copies and enables them:

```bash
./install_systemd.sh
```

Edit the service files if your project path differs from `/opt/bonefire` and then run the script with root privileges.


