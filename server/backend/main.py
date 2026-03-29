import os
import string
import random
import httpx
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from motor.motor_asyncio import AsyncIOMotorClient

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
ROOT_DIR   = Path(__file__).parent.parent
UPLOAD_DIR = ROOT_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

MONGO_URI  = os.getenv("MONGO_URI", "mongodb+srv://BADMUNDA:BADMYDAD@badhacker.i5nw9na.mongodb.net/")
DB_NAME    = "badbox"
MAX_BYTES  = 200 * 1024 * 1024
BLOCKED    = {"exe", "scr", "cpl", "jar", "bat", "php", "sh", "msi"}
CHARS      = string.ascii_lowercase + string.digits

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(title="BadBox API", version="1.0.0")

app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")
app.mount("/static",  StaticFiles(directory=str(ROOT_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(ROOT_DIR / "templates"))

# ---------------------------------------------------------------------------
# MongoDB
# ---------------------------------------------------------------------------
@app.on_event("startup")
async def startup():
    app.mongo = AsyncIOMotorClient(MONGO_URI)
    app.db    = app.mongo[DB_NAME]
    app.files = app.db["files"]
    await app.files.create_index("filename", unique=True)

@app.on_event("shutdown")
async def shutdown():
    app.mongo.close()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def short_id(n=8) -> str:
    return "".join(random.choices(CHARS, k=n))

def unique_name(original: str) -> str:
    ext = original.rsplit(".", 1)[-1].lower() if "." in original else "bin"
    return f"{short_id()}.{ext}"

def base_url(req: Request) -> str:
    proto = req.headers.get("x-forwarded-proto", req.url.scheme)
    return f"{proto}://{req.url.netloc}"

def validate(filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
    if ext in BLOCKED:
        raise HTTPException(400, f".{ext} files are not allowed")
    return ext

def fmt(b: int) -> str:
    if b < 1024:    return f"{b} B"
    if b < 1048576: return f"{b/1024:.1f} KB"
    return f"{b/1048576:.1f} MB"

def clean(doc: dict) -> dict:
    doc.pop("_id", None)
    return doc

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def home(req: Request):
    return templates.TemplateResponse("index.html", {"request": req})


@app.post("/upload")
async def upload_file(req: Request, file: UploadFile = File(...)):
    ext   = validate(file.filename)
    fname = unique_name(file.filename)
    path  = UPLOAD_DIR / fname
    total = 0

    with open(path, "wb") as f:
        while chunk := await file.read(65536):
            total += len(chunk)
            if total > MAX_BYTES:
                path.unlink(missing_ok=True)
                raise HTTPException(400, "File too large. Max 200MB allowed.")
            f.write(chunk)

    url = f"{base_url(req)}/uploads/{fname}"
    doc = {
        "filename":      fname,
        "original_name": file.filename,
        "url":           url,
        "size_bytes":    total,
        "size":          fmt(total),
        "ext":           ext,
        "source":        "file",
        "uploaded_at":   datetime.utcnow().isoformat(),
    }
    await app.files.insert_one(doc)
    return JSONResponse(clean(doc))


@app.post("/upload-url")
async def upload_from_url(req: Request, url: str = Form(...)):
    if not url.startswith(("http://", "https://")):
        raise HTTPException(400, "Provide a valid http/https URL")

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=30) as c:
            r = await c.get(url)
            r.raise_for_status()
    except Exception as e:
        raise HTTPException(400, f"Failed to fetch URL: {e}")

    raw = url.split("?")[0].rstrip("/").split("/")[-1] or "file"
    if "." not in raw:
        ct  = r.headers.get("content-type", "")
        ext = ct.split("/")[-1].split(";")[0].strip() or "bin"
        raw = f"file.{ext}"

    ext   = validate(raw)
    fname = unique_name(raw)
    path  = UPLOAD_DIR / fname
    data  = r.content

    if len(data) > MAX_BYTES:
        raise HTTPException(400, "File too large. Max 200MB allowed.")

    with open(path, "wb") as f:
        f.write(data)

    file_url = f"{base_url(req)}/uploads/{fname}"
    doc = {
        "filename":      fname,
        "original_name": raw,
        "url":           file_url,
        "size_bytes":    len(data),
        "size":          fmt(len(data)),
        "ext":           ext,
        "source":        "url",
        "uploaded_at":   datetime.utcnow().isoformat(),
    }
    await app.files.insert_one(doc)
    return JSONResponse(clean(doc))


# Simple upload — plain text URL response
@app.post("/api/upload")
async def api_upload(req: Request, file: UploadFile = File(...)):
    result = await upload_file(req, file)
    import json
    data = json.loads(result.body)
    return PlainTextResponse(data["url"])


@app.get("/files")
async def list_files(req: Request):
    base   = base_url(req)
    cursor = app.files.find().sort("uploaded_at", -1).limit(500)
    files  = []
    async for doc in cursor:
        doc.pop("_id", None)
        doc["url"] = f"{base}/uploads/{doc['filename']}"
        files.append(doc)
    total_size = sum(d.get("size_bytes", 0) for d in files)
    return JSONResponse({"files": files, "total": len(files), "total_size": fmt(total_size)})


@app.delete("/delete/{filename}")
async def delete_file(filename: str):
    fname = Path(filename).name
    path  = UPLOAD_DIR / fname
    if path.exists():
        path.unlink()
    result = await app.files.delete_one({"filename": fname})
    if result.deleted_count == 0:
        raise HTTPException(404, "File not found")
    return JSONResponse({"success": True, "message": f"{fname} deleted"})


@app.get("/health")
async def health():
    count = await app.files.count_documents({})
    files = [f for f in UPLOAD_DIR.iterdir() if f.is_file()]
    size  = sum(f.stat().st_size for f in files)
    return {"status": "running", "db_files": count, "disk_files": len(files), "disk_size": fmt(size)}
