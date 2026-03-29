# DropZone — Self-Hosted File Server

Catbox ਵਰਗਾ, ਪਰ **ਤੁਹਾਡੇ ਆਪਣੇ server ਤੇ**।

## Files Structure
```
filehost/
├── main.py          ← FastAPI backend (API)
├── requirements.txt
├── Procfile         ← Heroku ਲਈ
├── runtime.txt      ← Python version
├── uploads/         ← ਇੱਥੇ files save ਹੁੰਦੀਆਂ ਹਨ
└── templates/
    └── index.html   ← Website frontend
```

## Data ਕਿੱਥੇ Save ਹੁੰਦਾ ਹੈ?
```
User → /upload → uploads/abc123xyz.jpg  (Disk ਤੇ)
                → URL: yourapp.com/uploads/abc123xyz.jpg
```

---

## Option 1: Heroku ਤੇ Deploy

```bash
# 1. Heroku CLI install (jei nahi hai)
curl https://cli-assets.heroku.com/install.sh | sh

# 2. Login
heroku login

# 3. App banao
heroku create your-app-name

# 4. Git setup
git init
git add .
git commit -m "first commit"

# 5. Deploy
git push heroku main

# 6. Open
heroku open
```

**⚠️ Heroku Note:** Free tier ਤੇ files **restart ਤੋਂ ਬਾਅਦ delete** ਹੋ ਜਾਂਦੀਆਂ ਹਨ
(ephemeral filesystem)। Permanent storage ਲਈ VPS ਵਧੀਆ ਹੈ।

---

## Option 2: Ubuntu VPS ਤੇ Deploy (Recommended)

```bash
# 1. Server ਤੇ SSH ਕਰੋ
ssh root@YOUR_VPS_IP

# 2. Python install
apt update && apt install python3 python3-pip nginx -y

# 3. Files copy karo (local ਤੋਂ)
scp -r filehost/ root@YOUR_VPS_IP:/var/www/filehost

# 4. VPS ਤੇ
cd /var/www/filehost
pip3 install -r requirements.txt

# 5. Run karo (background)
nohup uvicorn main:app --host 0.0.0.0 --port 8000 &

# ਜਾਂ systemd service (recommended)
```

### Systemd Service (Auto-restart ਲਈ)
```bash
cat > /etc/systemd/system/filehost.service << EOF
[Unit]
Description=DropZone File Host
After=network.target

[Service]
WorkingDirectory=/var/www/filehost
ExecStart=uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
EOF

systemctl enable filehost
systemctl start filehost
```

### Nginx Config
```nginx
server {
    listen 80;
    server_name yourdomain.com;
    client_max_body_size 200M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

## API Endpoints

| Method | URL | Description |
|--------|-----|-------------|
| GET | `/` | Website |
| POST | `/upload` | File upload |
| POST | `/upload-url` | URL ਤੋਂ upload |
| GET | `/files` | Saari files list |
| DELETE | `/delete/{filename}` | File delete |
| GET | `/health` | Server status |
| GET | `/docs` | API docs (Swagger) |

## Example API Call
```bash
# File upload
curl -X POST https://yourapp.com/upload \
  -F "file=@photo.jpg"

# Response
{"url": "https://yourapp.com/uploads/abc123.jpg", "size": "1.2 MB"}
```
