import os
import uuid
import shutil
import httpx
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# ─── CONFIG ───────────────────────────────────────────────────────────────────
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

MAX_SIZE_MB = 200
MAX_SIZE_BYTES = MAX_SIZE_MB * 1024 * 1024

ALLOWED_EXTENSIONS = {
    "jpg", "jpeg", "png", "gif", "webp", "svg",
    "mp4", "webm", "mov",
    "mp3", "ogg", "wav",
    "pdf", "txt", "zip", "rar",
}

BLOCKED_EXTENSIONS = {"exe", "scr", "cpl", "jar", "bat", "sh", "php"}

# ─── APP ──────────────────────────────────────────────────────────────────────
app = FastAPI(title="FileHost API")

app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")

# ─── HELPERS ──────────────────────────────────────────────────────────────────
def get_base_url(request: Request) -> str:
    """Heroku ਜਾਂ local — automatically detect ਕਰਦਾ ਹੈ"""
    forwarded = request.headers.get("x-forwarded-proto")
    proto = forwarded if forwarded else request.url.scheme
    return f"{proto}://{request.url.netloc}"

def validate_extension(filename: str):
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext in BLOCKED_EXTENSIONS:
        raise HTTPException(400, f".{ext} files allowed nahi hain")
    return ext

def unique_filename(original: str) -> str:
    ext = original.rsplit(".", 1)[-1].lower() if "." in original else "bin"
    return f"{uuid.uuid4().hex}.{ext}"

def format_size(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    elif size < 1024 ** 2:
        return f"{size/1024:.1f} KB"
    else:
        return f"{size/1024**2:.1f} MB"

# ─── ROUTES ───────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def homepage(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/upload")
async def upload_file(request: Request, file: UploadFile = File(...)):
    """File upload karo → direct URL mildi hai"""

    # Extension check
    ext = validate_extension(file.filename)

    # Size check — stream nal
    filename = unique_filename(file.filename)
    save_path = UPLOAD_DIR / filename

    total_size = 0
    with open(save_path, "wb") as f:
        while chunk := await file.read(1024 * 64):  # 64KB chunks
            total_size += len(chunk)
            if total_size > MAX_SIZE_BYTES:
                f.close()
                save_path.unlink(missing_ok=True)
                raise HTTPException(400, f"File too large! Max {MAX_SIZE_MB}MB allowed")
            f.write(chunk)

    base = get_base_url(request)
    file_url = f"{base}/uploads/{filename}"

    return JSONResponse({
        "success": True,
        "url": file_url,
        "filename": filename,
        "original_name": file.filename,
        "size": format_size(total_size),
        "ext": ext,
        "uploaded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })


@app.post("/upload-url")
async def upload_from_url(request: Request, url: str = Form(...)):
    """URL ਤੋਂ file download karke apne server te save karo"""

    if not url.startswith(("http://", "https://")):
        raise HTTPException(400, "Valid URL deo (http/https)")

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
            r = await client.get(url)
            r.raise_for_status()
    except Exception as e:
        raise HTTPException(400, f"URL fetch nahi hoi: {str(e)}")

    # Filename from URL
    url_path = url.split("?")[0].rstrip("/")
    original_name = url_path.split("/")[-1] or "file"
    if "." not in original_name:
        # Content-Type nal guess karo
        ct = r.headers.get("content-type", "")
        ext = ct.split("/")[-1].split(";")[0].strip() or "bin"
        original_name = f"file.{ext}"

    ext = validate_extension(original_name)
    filename = unique_filename(original_name)
    save_path = UPLOAD_DIR / filename

    content = r.content
    if len(content) > MAX_SIZE_BYTES:
        raise HTTPException(400, f"File too large! Max {MAX_SIZE_MB}MB")

    with open(save_path, "wb") as f:
        f.write(content)

    base = get_base_url(request)
    file_url = f"{base}/uploads/{filename}"

    return JSONResponse({
        "success": True,
        "url": file_url,
        "filename": filename,
        "original_name": original_name,
        "size": format_size(len(content)),
        "ext": ext,
        "uploaded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })


@app.get("/files")
async def list_files(request: Request):
    """Saari uploaded files di list"""
    files = []
    base = get_base_url(request)

    for f in sorted(UPLOAD_DIR.iterdir(), reverse=True):
        if f.is_file():
            stat = f.stat()
            files.append({
                "filename": f.name,
                "url": f"{base}/uploads/{f.name}",
                "size": format_size(stat.st_size),
                "uploaded_at": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
            })

    return JSONResponse({"files": files, "total": len(files)})


@app.delete("/delete/{filename}")
async def delete_file(filename: str):
    """File delete karo"""
    # Security: sirf filename, no path traversal
    filename = Path(filename).name
    file_path = UPLOAD_DIR / filename

    if not file_path.exists():
        raise HTTPException(404, "File nahi mili")

    file_path.unlink()
    return JSONResponse({"success": True, "message": f"{filename} delete ho gai"})


@app.get("/health")
async def health():
    total_files = len(list(UPLOAD_DIR.iterdir()))
    total_size = sum(f.stat().st_size for f in UPLOAD_DIR.iterdir() if f.is_file())
    return {
        "status": "running",
        "total_files": total_files,
        "total_size": format_size(total_size)
    }
