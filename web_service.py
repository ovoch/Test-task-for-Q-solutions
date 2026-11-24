import os
import re
import time
from urllib.parse import quote
from flask import Flask, g, jsonify, request, send_from_directory
from sqlalchemy import Column, DateTime, Integer, Text, create_engine, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import URL
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import declarative_base, sessionmaker

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")
MEDIA_TYPES = {".webm": "video/webm", ".mp4": "video/mp4", ".ogv": "video/ogg"}

DATABASE_URL = URL.create(
    "postgresql+psycopg2",
    username = os.getenv("DB_USER"),
    password = os.getenv("DB_PASSWORD"),
    host = os.getenv("DB_HOST", "localhost"),
    port = int(os.getenv("DB_PORT", "5432")),
    database = os.getenv("DB_NAME"),
)

engine = create_engine(DATABASE_URL, pool_pre_ping = True)
SessionLocal = sessionmaker(bind = engine, expire_on_commit = False)
Base = declarative_base()


class Video(Base):
    __tablename__ = "videos"

    id = Column(Integer, primary_key = True, autoincrement = True)
    company_name = Column(Text, nullable = False, unique = True)
    file_path = Column(Text, nullable = False)
    video_url = Column(Text, nullable = False)
    created_at = Column(DateTime(timezone = True), nullable = False, server_default = func.now())
    updated_at = Column(DateTime(timezone = True), nullable = False, server_default = func.now())


class VideoRepository:
    def __init__(self, session):
        self.session = session

    def get_by_company_name(self, company_name):
        return self.session.execute(select(Video).where(Video.company_name == company_name)).scalar_one_or_none()

    def get_all(self):
        return self.session.execute(select(Video).order_by(Video.id)).scalars().all()

    def upsert(self, company_name, file_path, video_url):
        stmt = insert(Video).values(company_name = company_name, file_path = file_path, video_url = video_url)
        stmt = stmt.on_conflict_do_update(
            index_elements = ["company_name"],
            set_ = {
                "file_path": stmt.excluded.file_path,
                "video_url": stmt.excluded.video_url,
                "updated_at": func.now(),
            },
        )
        self.session.execute(stmt)
        self.session.commit()


def init_db():
    for attempt in range(1, 31):
        try:
            Base.metadata.create_all(engine)
            return
        except OperationalError as e:
            print(f"Database is not ready ({attempt}/30): {e}", flush = True)
            time.sleep(2)
    raise RuntimeError("Database is not available")


def get_db():
    if "db" not in g:
        g.db = SessionLocal()
    return g.db


def make_filename(company_name, original_name):
    safe_name = re.sub(r"[^\w\-]+", "_", company_name).strip("_")
    if not safe_name:
        safe_name = "video"
    extension = os.path.splitext(original_name or "")[1].lower()
    if extension not in MEDIA_TYPES:
        extension = ".webm"
    return safe_name + extension


def build_video_url(filename):
    return f"{request.host_url}media/{quote(filename)}"


os.makedirs(UPLOADS_DIR, exist_ok = True)
init_db()

app = Flask(__name__)


@app.teardown_appcontext
def close_db(error):
    db = g.pop("db", None)
    if db is not None:
        db.close()


@app.route("/upload", methods = ["POST"])
def upload_video():
    file = request.files.get("file")
    company_name = request.form.get("company_name", "").strip()
    if file is None or not company_name:
        return jsonify({"error": "file and company_name are required"}), 400

    filename = make_filename(company_name, file.filename)
    file_path = os.path.join(UPLOADS_DIR, filename)
    file.save(file_path)

    video_url = build_video_url(filename)
    VideoRepository(get_db()).upsert(company_name, file_path, video_url)
    return jsonify({"company_name": company_name, "video_url": video_url})


@app.route("/get_video_url")
def get_video_url():
    company_name = request.args.get("company_name", "").strip()
    if not company_name:
        return jsonify({"error": "company_name is required"}), 400

    video = VideoRepository(get_db()).get_by_company_name(company_name)
    if video is None:
        return jsonify({"error": "Company not found"}), 404
    return jsonify({"company_name": video.company_name, "video_url": video.video_url})


@app.route("/media/<path:filename>")
def get_media(filename):
    extension = os.path.splitext(filename)[1].lower()
    return send_from_directory(UPLOADS_DIR, filename, mimetype = MEDIA_TYPES.get(extension, "video/webm"))


@app.route("/videos")
def get_videos():
    videos = VideoRepository(get_db()).get_all()
    return jsonify([
        {
            "id": video.id,
            "company_name": video.company_name,
            "file_path": video.file_path,
            "video_url": video.video_url,
            "created_at": video.created_at.isoformat(),
            "updated_at": video.updated_at.isoformat(),
        }
        for video in videos
    ])


if __name__ == "__main__":
    app.run(host = os.getenv("FLASK_HOST", "0.0.0.0"), port = int(os.getenv("FLASK_PORT", "8000")))