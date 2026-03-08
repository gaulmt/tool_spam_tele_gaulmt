# 🚀 Deploy License Server lên Vercel

## Tổng quan

Server Vercel **không bao giờ ngủ** (serverless) → tool luôn xác thực license thành công.  
Data lưu trên **GitHub repo** (file `licenses.json`) → không cần database bên ngoài.

---

## Bước 1: Push code lên GitHub

```bash
cd "d:\tool spam tele\license_server_vercel"
git init
git add .
git commit -m "License server for Vercel"
git remote add origin https://github.com/YOUR_USERNAME/tool-tele.git
git push -u origin main
```

---

## Bước 2: Deploy lên Vercel

1. Vào **https://vercel.com** → **Add New Project** → Import repo `tool-tele`
2. Settings:
   - **Framework Preset**: `Flask`
   - **Root Directory**: `./`
   - **Build Command**: None
   - **Install Command**: `pip install -r requirements.txt`

---

## Bước 3: Thêm Environment Variables

Vào **Vercel Dashboard** → Project → **Settings** → **Environment Variables**:

| Name | Value | Mô tả |
|------|-------|-------|
| `GITHUB_TOKEN` | `ghp_xxxxx...` | GitHub Personal Access Token |
| `GITHUB_REPO` | `YOUR_USERNAME/tool-tele` | Tên repo GitHub |

### Cách tạo GitHub Token:
1. GitHub → **Settings** → **Developer settings** → **Personal access tokens** → **Fine-grained tokens**
2. **Generate new token**:
   - **Name**: `vercel-license-server`
   - **Repository access**: Only select `tool-tele`
   - **Permissions**: Contents → **Read and write**
3. Copy token → paste vào Vercel env var `GITHUB_TOKEN`

---

## Bước 4: Redeploy

Sau khi thêm env vars → vào **Deployments** → **Redeploy** lại.

---

## Bước 5: Kiểm tra

Mở trình duyệt:
```
https://tool-tele.vercel.app/
```

Phải thấy:
```json
{"status": "ok", "message": "Gaulmt License Server (Vercel)", "version": "2.0"}
```

---

## Bước 6: Migrate licenses cũ

```bash
python migrate_to_vercel.py
```

(Nhớ sửa `VERCEL_URL` trong file thành `https://tool-tele.vercel.app`)

---

## ✅ Xong!

- Server **không bao giờ ngủ** ✅
- Data lưu trên **GitHub** ✅  
- Không cần database bên ngoài ✅
