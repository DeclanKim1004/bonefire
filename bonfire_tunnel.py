"""Utility for exposing the local FastAPI server via ngrok."""

import logging
import os
import time
from pyngrok import ngrok
import requests


NGROK_PORT = 5000
URL_FILE = "ngrok_url.txt"
RENEW_INTERVAL = 4 * 60 * 60  # 4 hours

NGROK_AUTH_TOKEN = os.getenv("NGROK_AUTH_TOKEN")


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("bonfire_tunnel")


def warm_up(url: str) -> None:
    """Send a request to the public URL so that the first real request is fast."""
    try:
        logger.info("🔥 Warming up ngrok link...")
        requests.get(url, timeout=3)
        logger.info("✅ Warm up complete")
    except Exception as exc:  # pragma: no cover - network errors are non-critical
        logger.warning("⚠️  Warm up failed: %s", exc)


def start_tunnel(port: int = NGROK_PORT):
    if NGROK_AUTH_TOKEN:
        ngrok.set_auth_token(NGROK_AUTH_TOKEN)

    logger.info("🔗 Starting ngrok tunnel on port %s", port)
    tunnel = ngrok.connect(port, "http")
    url = tunnel.public_url

    with open(URL_FILE, "w") as f:
        f.write(url)

    logger.info("🌐 Public URL: %s", url)
    warm_up(url)
    return tunnel


def main() -> None:
    tunnel = start_tunnel()
    try:
        while True:
            time.sleep(RENEW_INTERVAL)
            logger.info("♻️  Renewing ngrok tunnel...")
            ngrok.disconnect(tunnel.public_url)
            tunnel = start_tunnel()
    except KeyboardInterrupt:
        logger.info("🛑 Stopping ngrok...")
        ngrok.kill()


if __name__ == "__main__":  # pragma: no cover - manual utility
    main()
