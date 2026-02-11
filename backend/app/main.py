from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import router as api_router


app = FastAPI(title="Growth")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"] ,
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(api_router, prefix="/api")


def _mount_frontend(app_instance: FastAPI):
    dist_dir = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    if not dist_dir.exists():
        return

    app_instance.mount("/", StaticFiles(directory=str(dist_dir), html=True), name="static")


_mount_frontend(app)
