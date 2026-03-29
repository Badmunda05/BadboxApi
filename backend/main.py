import os
import string
import random
import httpx
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from motor.motor_asyncio import AsyncIOMotorClient

# ─── CONFIG ───────────────────────────────────────────────────────────────────
ROOT_DIR   = Path(__file__).parent.parent
UPLOAD_DIR = ROOT_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

MONGO_URI  = os.getenv("MONGO_URI", "mongodb+srv://BADMUNDA:BADMYDAD@badhacker.i5nw9na.mongodb.net/")
DB_NAME    = "dropzone"
MAX_BYTES  = 200 * 1024 * 1024   # 200 MB
BLOCKED    = {"exe","scr","cpl","jar","bat","php","sh","msi"}

# ─── SHORT ID ─────────────────────────────────────────────────────────────────
CHARS = string.ascii_lowercase + string.digits

def short_id(n=8) -> str:
    return "".join(random.choices(CHARS, k=n))

def unique_name(original: str) -> str:
    ext = original.rsplit(".", 1)[-1].lower() if "." in original else "bin"
    return f"{short_id()}.{ext}"   # e.g.  k9xm2pqr.jpg

# ─── APP ──────────────────────────────────────────────────────────────────────
app = FastAPI(title="DropZone", version="2.0")

app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")
app.mount("/static",  StaticFiles(directory=str(ROOT_DIR / "static")),  name="static")
templates = Jinja2Templates(directory=str(ROOT_DIR / "templates"))

# ─── MONGODB ──────────────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup():
    app.mongo  = AsyncIOMotorClient(MONGO_URI)
    app.db     = app.mongo[DB_NAME]
    app.files  = app.db["files"]
    # Index for fast lookup
    await app.files.create_index("filename", unique=True)
    print("✅ MongoDB connected")

@app.on_event("shutdown")
async def shutdown():
    app.mongo.close()

# ─── HELPERS ──────────────────────────────────────────────────────────────────
def base_url(req: Request) -> str:
    proto = req.headers.get("x-forwarded-proto", req.url.scheme)
    return f"{proto}://{req.url.netloc}"

def validate(filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
    if ext in BLOCKED:
        raise HTTPException(400, f".{ext} allowed nahi")
    return ext

def fmt(b: int) -> str:
    if b < 1024:      return f"{b} B"
    if b < 1024**2:   return f"{b/1024:.1f} KB"
    return f"{b/1024**2:.1f} MB"

def doc_to_dict(doc) -> dict:
    doc.pop("_id", None)
    return doc

# ─── ROUTES ───────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def home(req: Request):
    return templates.TemplateResponse("index.html", {"request": req})


# ── 1. FILE UPLOAD ────────────────────────────────────────────────────────────
@app.post("/upload")
async def upload_file(req: Request, file: UploadFile = File(...)):
    ext      = validate(file.filename)
    fname    = unique_name(file.filename)
    path     = UPLOAD_DIR / fname
    total    = 0

    with open(path, "wb") as f:
        while chunk := await file.read(65536):
            total += len(chunk)
            if total > MAX_BYTES:
                path.unlink(missing_ok=True)
                raise HTTPException(400, "200MB ਤੋਂ ਵੱਡੀ ਫਾਈਲ ਨਹੀਂ ਚੱਲੇਗੀ")
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
        "uploaded_at":   datetime.utcnow().isoformat()
    }
    await app.files.insert_one(doc)
    return JSONResponse(doc_to_dict(doc))


# ── 2. URL UPLOAD ─────────────────────────────────────────────────────────────
@app.post("/upload-url")
async def upload_url(req: Request, url: str = Form(...)):
    if not url.startswith(("http://","https://")):
        raise HTTPException(400, "Valid URL deo")

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=30) as c:
            r = await c.get(url); r.raise_for_status()
    except Exception as e:
        raise HTTPException(400, f"URL fetch nahi hoi: {e}")

    raw  = url.split("?")[0].rstrip("/").split("/")[-1] or "file"
    if "." not in raw:
        ct  = r.headers.get("content-type","")
        ext = ct.split("/")[-1].split(";")[0].strip() or "bin"
        raw = f"file.{ext}"

    ext   = validate(raw)
    fname = unique_name(raw)
    path  = UPLOAD_DIR / fname
    data  = r.content

    if len(data) > MAX_BYTES:
        raise HTTPException(400, "200MB ਤੋਂ ਵੱਡੀ ਫਾਈਲ ਨਹੀਂ ਚੱਲੇਗੀ")

    with open(path,"wb") as f: f.write(data)

    file_url = f"{base_url(req)}/uploads/{fname}"
    doc = {
        "filename":      fname,
        "original_name": raw,
        "url":           file_url,
        "size_bytes":    len(data),
        "size":          fmt(len(data)),
        "ext":           ext,
        "source":        "url",
        "uploaded_at":   datetime.utcnow().isoformat()
    }
    await app.files.insert_one(doc)
    return JSONResponse(doc_to_dict(doc))


# ── 3. LIST ALL FILES ─────────────────────────────────────────────────────────
@app.get("/files")
async def list_files(req: Request):
    cursor = app.files.find().sort("uploaded_at", -1).limit(200)
    files  = []
    base   = base_url(req)

    async for doc in cursor:
        doc.pop("_id", None)
        # URL ਨੂੰ current server ਦੇ ਨਾਲ sync ਕਰੋ
        doc["url"] = f"{base}/uploads/{doc['filename']}"
        files.append(doc)

    total_size = sum(d.get("size_bytes", 0) for d in files)
    return JSONResponse({"files": files, "total": len(files), "total_size": fmt(total_size)})


# ── 4. DELETE FILE ────────────────────────────────────────────────────────────
@app.delete("/delete/{filename}")
async def delete_file(filename: str):
    fname = Path(filename).name
    path  = UPLOAD_DIR / fname
    if path.exists(): path.unlink()
    result = await app.files.delete_one({"filename": fname})
    if result.deleted_count == 0:
        raise HTTPException(404, "File nahi mili DB ਵਿੱਚ")
    return JSONResponse({"success": True, "msg": f"{fname} delete ho gai"})


# ── 5. CATBOX-STYLE API (Python ਵਿੱਚ ਵਰਤੋ) ──────────────────────────────────
# POST /api/upload  →  returns plain text URL  (catbox.moe style)
@app.post("/api/upload")
async def api_upload(req: Request, file: UploadFile = File(...)):
    """Catbox ਵਰਗਾ — plain text URL ਵਾਪਸ ਮਿਲਦੀ ਹੈ"""
    result = await upload_file(req, file)
    import json
    data = json.loads(result.body)
    # plain text response (catbox style)
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(data["url"])


# ── 6. HEALTH ─────────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    count = await app.files.count_documents({})
    files = list(UPLOAD_DIR.iterdir())
    size  = sum(f.stat().st_size for f in files if f.is_file())
    return {"status": "✅ running", "db_files": count, "disk_files": len(files), "disk_size": fmt(size)}
