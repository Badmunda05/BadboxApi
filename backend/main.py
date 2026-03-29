import os
import uuid
import httpx
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# ─── CONFIG ───────────────────────────────────────────────────────────────────
# backend/main.py ਤੋਂ ਉੱਪਰ ਵਾਲਾ folder (root) ਲੱਭੋ
ROOT_DIR = Path(__file__).parent.parent  # filehost2/
UPLOAD_DIR = ROOT_DIR / "uploads"
TEMPLATE_DIR = ROOT_DIR / "templates"
STATIC_DIR = ROOT_DIR / "static"

UPLOAD_DIR.mkdir(exist_ok=True)

MAX_SIZE_BYTES = 200 * 1024 * 1024  # 200MB

BLOCKED_EXT = {"exe", "scr", "cpl", "jar", "bat", "php", "sh"}

# ─── APP ──────────────────────────────────────────────────────────────────────
app = FastAPI(title="DropZone API", version="1.0.0")

app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

# ─── HELPERS ──────────────────────────────────────────────────────────────────
def get_base_url(request: Request) -> str:
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    return f"{proto}://{request.url.netloc}"

def validate_ext(filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
    if ext in BLOCKED_EXT:
        raise HTTPException(400, f".{ext} files allowed nahi hain")
    return ext

def unique_name(original: str) -> str:
    ext = original.rsplit(".", 1)[-1].lower() if "." in original else "bin"
    return f"{uuid.uuid4().hex}.{ext}"

def fmt_size(b: int) -> str:
    if b < 1024: return f"{b} B"
    if b < 1024**2: return f"{b/1024:.1f} KB"
    return f"{b/1024**2:.1f} MB"

# ─── ROUTES ───────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def homepage(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/upload")
async def upload_file(request: Request, file: UploadFile = File(...)):
    ext = validate_ext(file.filename)
    filename = unique_name(file.filename)
    save_path = UPLOAD_DIR / filename

    total = 0
    with open(save_path, "wb") as f:
        while chunk := await file.read(65536):  # 64KB chunks
            total += len(chunk)
            if total > MAX_SIZE_BYTES:
                save_path.unlink(missing_ok=True)
                raise HTTPException(400, "File bahut badi hai! Max 200MB")
            f.write(chunk)

    url = f"{get_base_url(request)}/uploads/{filename}"
    return JSONResponse({
        "success": True,
        "url": url,
        "filename": filename,
        "original_name": file.filename,
        "size": fmt_size(total),
        "ext": ext,
        "uploaded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })


@app.post("/upload-url")
async def upload_from_url(request: Request, url: str = Form(...)):
    if not url.startswith(("http://", "https://")):
        raise HTTPException(400, "Valid URL deo")

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
            r = await client.get(url)
            r.raise_for_status()
    except Exception as e:
        raise HTTPException(400, f"URL fetch nahi hoi: {e}")

    # Filename ਕੱਢੋ
    raw_name = url.split("?")[0].rstrip("/").split("/")[-1] or "file"
    if "." not in raw_name:
        ct = r.headers.get("content-type", "")
        ext = ct.split("/")[-1].split(";")[0].strip() or "bin"
        raw_name = f"file.{ext}"

    ext = validate_ext(raw_name)
    filename = unique_name(raw_name)
    save_path = UPLOAD_DIR / filename

    content = r.content
    if len(content) > MAX_SIZE_BYTES:
        raise HTTPException(400, "File bahut badi hai! Max 200MB")

    with open(save_path, "wb") as f:
        f.write(content)

    file_url = f"{get_base_url(request)}/uploads/{filename}"
    return JSONResponse({
        "success": True,
        "url": file_url,
        "filename": filename,
        "original_name": raw_name,
        "size": fmt_size(len(content)),
        "ext": ext,
        "uploaded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })


@app.get("/files")
async def list_files(request: Request):
    base = get_base_url(request)
    files = []
    for f in sorted(UPLOAD_DIR.iterdir(), reverse=True):
        if f.is_file() and f.name != ".gitkeep":
            stat = f.stat()
            files.append({
                "filename": f.name,
                "url": f"{base}/uploads/{f.name}",
                "size": fmt_size(stat.st_size),
                "uploaded_at": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
            })
    return JSONResponse({"files": files, "total": len(files)})


@app.delete("/delete/{filename}")
async def delete_file(filename: str):
    filename = Path(filename).name  # path traversal block
    path = UPLOAD_DIR / filename
    if not path.exists():
        raise HTTPException(404, "File nahi mili")
    path.unlink()
    return JSONResponse({"success": True, "message": f"{filename} delete ho gai"})


@app.get("/health")
async def health():
    files = [f for f in UPLOAD_DIR.iterdir() if f.is_file() and f.name != ".gitkeep"]
    total_size = sum(f.stat().st_size for f in files)
    return {
        "status": "✅ running",
        "total_files": len(files),
        "total_size": fmt_size(total_size)
    }
