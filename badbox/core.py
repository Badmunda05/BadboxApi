import os
import requests
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _server() -> str:
    import badbox
    return badbox.SERVER.rstrip("/")


def _post_file(data: bytes, filename: str) -> str:
    r = requests.post(
        f"{_server()}/api/upload",
        files={"file": (filename, data)},
        timeout=60,
    )
    r.raise_for_status()
    url = r.text.strip()
    if not url.startswith("http"):
        raise ValueError(f"Unexpected server response: {url}")
    return url


# ---------------------------------------------------------------------------
# Public functions  (simple — just call and get URL)
# ---------------------------------------------------------------------------

def upload_file(file_path: str) -> str:
    """
    Upload a local file and return its direct URL.

    Args:
        file_path: Path to the file on disk.

    Returns:
        str: Direct URL to the uploaded file.

    Example:
        from badbox import upload_file
        url = upload_file("photo.jpg")
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    with open(path, "rb") as f:
        return _post_file(f.read(), path.name)


def upload_bytes(data: bytes, filename: str) -> str:
    """
    Upload raw bytes and return the direct URL.
    Useful for Telegram bots where you have file bytes directly.

    Args:
        data:     Raw bytes of the file.
        filename: Filename with extension (e.g. "photo.jpg").

    Returns:
        str: Direct URL to the uploaded file.

    Example:
        from badbox import upload_bytes
        url = upload_bytes(bytes_data, "photo.jpg")
    """
    return _post_file(data, filename)


def upload_url(image_url: str) -> str:
    """
    Re-upload a file from a remote URL to your BadBox server.

    Args:
        image_url: Remote file URL.

    Returns:
        str: Direct URL on your server.

    Example:
        from badbox import upload_url
        url = upload_url("https://example.com/image.jpg")
    """
    r = requests.post(
        f"{_server()}/upload-url",
        data={"url": image_url},
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["url"]


def delete(filename: str) -> bool:
    """
    Delete a file from the server.

    Args:
        filename: Filename to delete (e.g. "k9xm2pqr.jpg").

    Returns:
        bool: True if deleted successfully.
    """
    r = requests.delete(f"{_server()}/delete/{filename}", timeout=30)
    return r.status_code == 200


def list_files() -> list:
    """
    List all files on the server.

    Returns:
        list: List of file dicts with url, size, uploaded_at.
    """
    r = requests.get(f"{_server()}/files", timeout=30)
    r.raise_for_status()
    return r.json()["files"]


# ---------------------------------------------------------------------------
# Class-based interface (optional)
# ---------------------------------------------------------------------------

class BadBox:
    """
    Class-based interface for BadBox.

    Example:
        bb = BadBox(server="http://your-vps:8000")
        url = bb.upload_file("photo.jpg")
    """

    def __init__(self, server: Optional[str] = None):
        self._server = (server or _server()).rstrip("/")

    def upload_file(self, file_path: str) -> str:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        with open(path, "rb") as f:
            return self._post(f.read(), path.name)

    def upload_bytes(self, data: bytes, filename: str) -> str:
        return self._post(data, filename)

    def upload_url(self, image_url: str) -> str:
        r = requests.post(f"{self._server}/upload-url", data={"url": image_url}, timeout=60)
        r.raise_for_status()
        return r.json()["url"]

    def delete(self, filename: str) -> bool:
        r = requests.delete(f"{self._server}/delete/{filename}", timeout=30)
        return r.status_code == 200

    def _post(self, data: bytes, filename: str) -> str:
        r = requests.post(
            f"{self._server}/api/upload",
            files={"file": (filename, data)},
            timeout=60,
        )
        r.raise_for_status()
        return r.text.strip()
