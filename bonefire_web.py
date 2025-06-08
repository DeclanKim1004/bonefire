from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import uvicorn

app = FastAPI(title="Bonefire of Panghyeon")


@app.get("/")
async def read_root():
    return HTMLResponse("<h1>Bonefire server is running</h1>")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)
