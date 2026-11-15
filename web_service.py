import os
import re
import shutil
import uvicorn
from contextlib import asynccontextmanager
from urllib.parse import quote
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import Column, Integer, Text, event, func, select, text
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base
from starlette.concurrency import run_in_threadpool

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")
DB_PATH = os.path.join(BASE_DIR, "videos.db")
DATABASE_URL = "sqlite+aiosqlite:///" + DB_PATH.replace("\\", "/")
MEDIA_TYPES = {".webm": "video/webm", ".mp4": "video/mp4", ".ogv": "video/ogg"}

engine = create_async_engine(DATABASE_URL, connect_args = {"timeout": 30})
SessionLocal = async_sessionmaker(engine, expire_on_commit = False)
Base = declarative_base()


@event.listens_for(engine.sync_engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=30000")
    cursor.close()


class Video(Base):
    __tablename__ = "videos"
    __table_args__ = {"sqlite_autoincrement": True}

    id = Column(Integer, primary_key = True, autoincrement = True)
    company_name = Column(Text, nullable = False, unique = True)
    file_path = Column(Text, nullable = False)
    video_url = Column(Text, nullable = False)
    created_at = Column(Text, nullable = False, server_default = text("(datetime('now'))"))
    updated_at = Column(Text, nullable = False, server_default = text("(datetime('now'))"))


class VideoResponse(BaseModel):
    company_name: str
    video_url: str


class VideoRepository:
    def __init__(self, session):
        self.session = session

    async def get_by_company_name(self, company_name):
        result = await self.session.execute(select(Video).where(Video.company_name == company_name))
        return result.scalar_one_or_none()

    async def get_all(self):
        result = await self.session.execute(select(Video).order_by(Video.id))
        return result.scalars().all()

    async def upsert(self, company_name, file_path, video_url):
        stmt = insert(Video).values(company_name = company_name, file_path = file_path, video_url = video_url)
        stmt = stmt.on_conflict_do_update(
            index_elements = ["company_name"],
            set_ = {
                "file_path": stmt.excluded.file_path,
                "video_url": stmt.excluded.video_url,
                "updated_at": func.datetime("now"),
            },
        )
        await self.session.execute(stmt)
        await self.session.commit()


async def get_db():
    async with SessionLocal() as session:
        yield session


def make_filename(company_name, original_name):
    safe_name = re.sub(r"[^\w\-]+", "_", company_name).strip("_")
    if not safe_name:
        safe_name = "video"
    extension = os.path.splitext(original_name or "")[1].lower()
    if extension not in MEDIA_TYPES:
        extension = ".webm"
    return safe_name + extension


async def save_video_file(file, file_path):
    with open(file_path, "wb") as buffer:
        await run_in_threadpool(shutil.copyfileobj, file.file, buffer)


def build_video_url(request, filename):
    return f"{request.base_url}media/{quote(filename)}"


@asynccontextmanager
async def lifespan(app):
    os.makedirs(UPLOADS_DIR, exist_ok = True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(lifespan = lifespan)


@app.post("/upload", response_model = VideoResponse)
async def upload_video(
    request: Request,
    file: UploadFile = File(...),
    company_name: str = Form(...),
    db = Depends(get_db),
):
    company_name = company_name.strip()
    if not company_name:
        raise HTTPException(status_code = 400, detail = "company_name is empty")

    filename = make_filename(company_name, file.filename)
    file_path = os.path.join(UPLOADS_DIR, filename)
    await save_video_file(file, file_path)

    video_url = build_video_url(request, filename)
    await VideoRepository(db).upsert(company_name, file_path, video_url)
    return VideoResponse(company_name = company_name, video_url = video_url)


@app.get("/get_video_url", response_model = VideoResponse)
async def get_video_url(company_name: str, db = Depends(get_db)):
    video = await VideoRepository(db).get_by_company_name(company_name.strip())
    if video is None:
        raise HTTPException(status_code = 404, detail = "Company not found")
    return VideoResponse(company_name = video.company_name, video_url = video.video_url)


@app.get("/media/{filename}")
async def get_media(filename: str):
    file_path = os.path.join(UPLOADS_DIR, filename)
    if os.path.basename(filename) != filename or not os.path.isfile(file_path):
        raise HTTPException(status_code = 404, detail = "File not found")
    extension = os.path.splitext(filename)[1].lower()
    return FileResponse(file_path, media_type = MEDIA_TYPES.get(extension, "video/webm"))


@app.get("/videos")
async def get_videos(db = Depends(get_db)):
    videos = await VideoRepository(db).get_all()
    return [
        {
            "id": video.id,
            "company_name": video.company_name,
            "file_path": video.file_path,
            "video_url": video.video_url,
            "created_at": video.created_at,
            "updated_at": video.updated_at,
        }
        for video in videos
    ]


if __name__ == "__main__":
    uvicorn.run(
        app,
        host = os.getenv("FLASK_HOST", "0.0.0.0"),
        port = int(os.getenv("FLASK_PORT", "8000")),
    )