# BadBox

Self-hosted file hosting library — upload files, get direct URLs.

## Installation

```bash
pip3 install badbox
```

## Quick Start

```python
from badbox import upload_file

url = upload_file("photo.jpg")
print(url)
# → http://your-server.com/uploads/k9xm2pqr.jpg
```

## Usage

```python
# Upload a file
from badbox import upload_file
url = upload_file("photo.jpg")

# Upload from URL
from badbox import upload_url
url = upload_url("https://example.com/image.jpg")

# Upload raw bytes (Telegram bots)
from badbox import upload_bytes
url = upload_bytes(bytes_data, "photo.jpg")
```

## Telegram Bot Example

```python
from badbox import upload_bytes

async def handle_photo(update, context):
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    data = await file.download_as_bytearray()
    url = upload_bytes(bytes(data), "photo.jpg")
    await update.message.reply_text(url)
```

## Custom Server

Set your own BadBox server:

```bash
export BADBOX_SERVER="http://your-vps-ip:8000"
```

Or in code:

```python
import badbox
badbox.SERVER = "http://your-vps-ip:8000"
```

## License

MIT
