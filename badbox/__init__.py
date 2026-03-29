from .core import upload_file, upload_bytes, upload_url, BadBox
import os

# Default server — set via env var or override in code
SERVER = os.getenv("BADBOX_SERVER", "http://54.254.215.45:8000")

__version__ = "1.0.0"
__all__ = ["upload_file", "upload_bytes", "upload_url", "BadBox", "SERVER"]
