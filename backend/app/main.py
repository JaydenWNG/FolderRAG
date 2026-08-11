from fastapi import FastAPI

from .database import Base, engine
from .routers import folders, index


Base.metadata.create_all(bind=engine)


app = FastAPI(
	title="FolderRAG API",
	version="0.1.0",
)


app.include_router(folders.router)
app.include_router(index.router)


@app.get("/api/health")
def health():
	return {
		"status": "ok",
		"app": "FolderRAG",
	}