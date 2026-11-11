import uvicorn
from fastapi import FastAPI

app = FastAPI(title="nicto")


def start() -> None:
    """Start the web application."""
    uvicorn.run("nicto.main:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    start()
