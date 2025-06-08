from pyngrok import ngrok

NGROK_PORT = 5000
URL_FILE = "ngrok_url.txt"


def start_tunnel(port: int = NGROK_PORT) -> str:
    tunnel = ngrok.connect(port)
    url = tunnel.public_url
    with open(URL_FILE, "w") as f:
        f.write(url)
    print(f"ngrok tunnel started: {url}")
    return url


def stop_tunnel():
    ngrok.kill()


if __name__ == "__main__":
    try:
        start_tunnel()
        input("Press Enter to stop tunnel...")
    finally:
        stop_tunnel()
