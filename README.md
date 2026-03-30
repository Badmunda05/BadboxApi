# BadBox

A simple Python library to upload files and get permanent direct links — powered by your own BadBox server.

## Installation

```bash
pip3 install badbox
```

## Quick Start

```python
from badbox import upload_file

url = upload_file("photo.jpg")
print(url)
# → https://res.cloudinary.com/...
```

## Usage

### Upload a file
```python
from badbox import upload_file

url = upload_file("photo.jpg")
```

### Upload raw bytes
```python
from badbox import upload_bytes

url = upload_bytes(bytes_data, "photo.jpg")
```

### Upload from URL
```python
from badbox import upload_url

url = upload_url("https://example.com/image.jpg")
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

## Pyrogram / UserBot Example

```python
from badbox import upload_file
import os

@Client.on_message(filters.command(["bb"], ".") & filters.me)
async def upload_to_badbox(client, message):
    if not message.reply_to_message:
        return
    m = await message.edit("`Uploading...`")
    file = await message.reply_to_message.download()
    url = upload_file(file)
    await m.edit(f"**{url}**")
    os.remove(file)
```

## Links

- **Website:** [badbox-indol.vercel.app](https://badbox-indol.vercel.app)
- **Author:** [Bad Munda](https://github.com/Badmunda05)

## License

MIT
