from .core import upload_file, upload_bytes, upload_url, BadBox
import os

# Default server — set via env var or override in code
SERVER = os.getenv("BADBOX_SERVER", "https://sukh.online")

__version__ = "1.0.0"
__all__ = ["upload_file", "upload_bytes", "upload_url", "BadBox", "SERVER"]
