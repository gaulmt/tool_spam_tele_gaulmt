"""
License Server API - Flask (Vercel + GitHub Storage)
Lưu licenses.json trực tiếp trên GitHub repo - không cần database ngoài!
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime, timedelta
import urllib.request
import base64
import hashlib
import json
import os

app = Flask(__name__)
CORS(app)  # Cho phép gọi API từ admin.html local (Cross-Origin)

# Secret key
SECRET_KEY = "GDZ8PaKHoYtqEzXxLl1krTM0sh7yWAQu3FIVOCd2"

# GitHub config (set trong Vercel Environment Variables)
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPO = os.environ.get("GITHUB_REPO", "gaulmt/tool_spam_tele_gaulmt")  # format: "username/repo-name"
LICENSE_FILE_PATH = "licenses.json"

# Cache để giảm API calls
_cache = {"licenses": None, "sha": None, "time": 0}


def github_api(url, method="GET", data=None):
    """Gọi GitHub API"""
    req = urllib.request.Request(url, method=method)
    req.add_header("Authorization", f"token {GITHUB_TOKEN}")
    req.add_header("Accept", "application/vnd.github.v3+json")
    if data:
        req.add_header("Content-Type", "application/json")
        req.data = json.dumps(data).encode("utf-8")
    resp = urllib.request.urlopen(req, timeout=15)
    return json.loads(resp.read())


def load_licenses():
    """Load licenses từ GitHub repo"""
    import time
    now = time.time()

    # Dùng cache nếu còn mới (30 giây)
    if _cache["licenses"] is not None and (now - _cache["time"]) < 30:
        return _cache["licenses"], _cache["sha"]

    try:
        url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{LICENSE_FILE_PATH}"
        result = github_api(url)

        content = base64.b64decode(result["content"]).decode("utf-8")
        sha = result["sha"]
        licenses = json.loads(content)

        _cache["licenses"] = licenses
        _cache["sha"] = sha
        _cache["time"] = now

        return licenses, sha
    except Exception as e:
        print(f"GitHub load error: {e}")
        if _cache["licenses"] is not None:
            return _cache["licenses"], _cache["sha"]
        return {}, None


def save_licenses(licenses, sha):
    """Lưu licenses lên GitHub repo"""
    import time
    try:
        content_str = json.dumps(licenses, indent=2, ensure_ascii=False)
        content_b64 = base64.b64encode(content_str.encode("utf-8")).decode("utf-8")

        url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{LICENSE_FILE_PATH}"
        data = {
            "message": "Update licenses",
            "content": content_b64,
            "sha": sha
        }
        result = github_api(url, method="PUT", data=data)

        # Cập nhật cache
        _cache["licenses"] = licenses
        _cache["sha"] = result["content"]["sha"]
        _cache["time"] = time.time()

        return True
    except Exception as e:
        print(f"GitHub save error: {e}")
        return False


def generate_license_key(user_id, months):
    """Tạo license key"""
    expire_date = datetime.now() + timedelta(days=months * 30)
    data = f"{user_id}|{expire_date.strftime('%Y-%m-%d')}"
    signature = hashlib.sha256((data + SECRET_KEY).encode()).hexdigest()
    license_key = f"{user_id}_{signature[:16]}"
    return license_key, expire_date.strftime("%Y-%m-%d")


@app.route("/")
def home():
    return jsonify({
        "status": "ok",
        "message": "Gaulmt License Server (Vercel)",
        "version": "2.0"
    })


@app.route("/verify", methods=["POST"])
def verify_license():
    """Verify license key với Hardware ID binding"""
    try:
        data = request.get_json()
        license_key = data.get("license_key", "").strip()
        hardware_id = data.get("hardware_id", "").strip()

        if not license_key:
            return jsonify({"valid": False, "message": "License key không được để trống!"})

        licenses, sha = load_licenses()

        if license_key not in licenses:
            return jsonify({"valid": False, "message": "License key không tồn tại!"})

        license_info = licenses[license_key]
        need_save = False

        # Kiểm tra Hardware ID binding
        stored_hwid = license_info.get("hardware_id", None)

        if stored_hwid is None:
            license_info["hardware_id"] = hardware_id
            license_info["first_activation"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            licenses[license_key] = license_info
            need_save = True
        elif stored_hwid != hardware_id:
            return jsonify({
                "valid": False,
                "message": "License key đã được kích hoạt trên máy khác!\n\nMỗi license chỉ dùng được cho 1 máy.\nVui lòng mua license mới hoặc liên hệ hỗ trợ."
            })

        # Kiểm tra hạn
        expire_date = datetime.strptime(license_info["expire_date"], "%Y-%m-%d")
        days_left = (expire_date - datetime.now()).days

        if days_left < 0:
            return jsonify({
                "valid": False,
                "message": "License key đã hết hạn!",
                "expire_date": license_info["expire_date"]
            })

        # Cập nhật last_check (chỉ save nếu đã có thay đổi khác)
        licenses[license_key]["last_check"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if need_save:
            save_licenses(licenses, sha)

        return jsonify({
            "valid": True,
            "message": f"License hợp lệ. Còn {days_left} ngày.",
            "days_left": days_left,
            "expire_date": license_info["expire_date"],
            "user_id": license_info["user_id"]
        })

    except Exception as e:
        return jsonify({"valid": False, "message": f"Lỗi: {str(e)}"})


@app.route("/admin/create", methods=["POST"])
def admin_create_license():
    """Tạo license mới"""
    try:
        data = request.get_json()
        if data.get("admin_key", "") != SECRET_KEY:
            return jsonify({"success": False, "message": "Admin key không hợp lệ!"})

        user_id = data.get("user_id", "USER001")
        months = int(data.get("months", 1))
        plan = data.get("plan", "basic")
        notes = data.get("notes", "")

        license_key, expire_date = generate_license_key(user_id, months)

        licenses, sha = load_licenses()
        licenses[license_key] = {
            "user_id": user_id,
            "expire_date": expire_date,
            "created_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "last_check": None,
            "months": months,
            "plan": plan,
            "status": "active",
            "check_count": 0,
            "notes": notes
        }

        if save_licenses(licenses, sha):
            return jsonify({
                "success": True,
                "license_key": license_key,
                "expire_date": expire_date,
                "user_id": user_id,
                "months": months
            })
        else:
            return jsonify({"success": False, "message": "Không thể lưu lên GitHub!"})

    except Exception as e:
        return jsonify({"success": False, "message": f"Lỗi: {str(e)}"})


@app.route("/admin/list", methods=["POST"])
def admin_list_licenses():
    """Xem danh sách licenses"""
    try:
        data = request.get_json()
        if data.get("admin_key", "") != SECRET_KEY:
            return jsonify({"success": False, "message": "Admin key không hợp lệ!"})

        licenses, _ = load_licenses()

        result = []
        for key, info in licenses.items():
            expire_date = datetime.strptime(info["expire_date"], "%Y-%m-%d")
            days_left = (expire_date - datetime.now()).days
            result.append({
                "license_key": key,
                "user_id": info["user_id"],
                "expire_date": info["expire_date"],
                "days_left": days_left,
                "is_valid": days_left >= 0 and info.get("status") != "revoked",
                "last_check": info.get("last_check", "Chưa dùng"),
                "hardware_id": info.get("hardware_id", "Chưa kích hoạt"),
                "first_activation": info.get("first_activation", "Chưa kích hoạt"),
                "plan": info.get("plan", "basic"),
                "status": info.get("status", "active"),
                "months": info.get("months", 1),
                "notes": info.get("notes", ""),
                "check_count": info.get("check_count", 0)
            })

        return jsonify({"success": True, "total": len(result), "licenses": result})

    except Exception as e:
        return jsonify({"success": False, "message": f"Lỗi: {str(e)}"})


@app.route("/admin/reset_hardware", methods=["POST"])
def admin_reset_hardware():
    """Reset Hardware ID"""
    try:
        data = request.get_json()
        if data.get("admin_key", "") != SECRET_KEY:
            return jsonify({"success": False, "message": "Admin key không hợp lệ!"})

        license_key = data.get("license_key", "").strip()
        if not license_key:
            return jsonify({"success": False, "message": "License key không được để trống!"})

        licenses, sha = load_licenses()
        if license_key not in licenses:
            return jsonify({"success": False, "message": "License key không tồn tại!"})

        licenses[license_key]["hardware_id"] = None
        licenses[license_key]["first_activation"] = None

        if save_licenses(licenses, sha):
            return jsonify({"success": True, "message": f"Đã reset Hardware ID cho: {license_key}"})
        else:
            return jsonify({"success": False, "message": "Không thể lưu lên GitHub!"})

    except Exception as e:
        return jsonify({"success": False, "message": f"Lỗi: {str(e)}"})


@app.route("/admin/extend", methods=["POST"])
def admin_extend_license():
    """Gia hạn license"""
    try:
        data = request.get_json()
        if data.get("admin_key", "") != SECRET_KEY:
            return jsonify({"success": False, "message": "Admin key không hợp lệ!"})

        license_key = data.get("license_key", "").strip()
        months = int(data.get("months", 1))

        if not license_key:
            return jsonify({"success": False, "message": "License key không được để trống!"})

        licenses, sha = load_licenses()
        if license_key not in licenses:
            return jsonify({"success": False, "message": "License key không tồn tại!"})

        current_expire = datetime.strptime(licenses[license_key]["expire_date"], "%Y-%m-%d")
        if current_expire < datetime.now():
            new_expire = datetime.now() + timedelta(days=months * 30)
        else:
            new_expire = current_expire + timedelta(days=months * 30)

        licenses[license_key]["expire_date"] = new_expire.strftime("%Y-%m-%d")

        if save_licenses(licenses, sha):
            return jsonify({
                "success": True,
                "message": f"Đã gia hạn {months} tháng",
                "new_expire_date": new_expire.strftime("%Y-%m-%d")
            })
        else:
            return jsonify({"success": False, "message": "Không thể lưu lên GitHub!"})

    except Exception as e:
        return jsonify({"success": False, "message": f"Lỗi: {str(e)}"})


@app.route("/admin/delete", methods=["POST"])
def admin_delete_license():
    """Xóa license"""
    try:
        data = request.get_json()
        if data.get("admin_key", "") != SECRET_KEY:
            return jsonify({"success": False, "message": "Admin key không hợp lệ!"})

        license_key = data.get("license_key", "").strip()
        if not license_key:
            return jsonify({"success": False, "message": "License key không được để trống!"})

        licenses, sha = load_licenses()
        if license_key not in licenses:
            return jsonify({"success": False, "message": "License key không tồn tại!"})

        del licenses[license_key]

        if save_licenses(licenses, sha):
            return jsonify({"success": True, "message": f"Đã xóa license: {license_key}"})
        else:
            return jsonify({"success": False, "message": "Không thể lưu lên GitHub!"})

    except Exception as e:
        return jsonify({"success": False, "message": f"Lỗi: {str(e)}"})


@app.route("/admin/revoke", methods=["POST"])
def admin_revoke_license():
    """Vô hiệu hóa license (không xóa)"""
    try:
        data = request.get_json()
        if data.get("admin_key", "") != SECRET_KEY:
            return jsonify({"success": False, "message": "Admin key không hợp lệ!"})

        license_key = data.get("license_key", "").strip()
        if not license_key:
            return jsonify({"success": False, "message": "License key không được để trống!"})

        licenses, sha = load_licenses()
        if license_key not in licenses:
            return jsonify({"success": False, "message": "License key không tồn tại!"})

        licenses[license_key]["status"] = "revoked"

        if save_licenses(licenses, sha):
            return jsonify({"success": True, "message": f"Đã vô hiệu hóa: {license_key}"})
        else:
            return jsonify({"success": False, "message": "Không thể lưu lên GitHub!"})

    except Exception as e:
        return jsonify({"success": False, "message": f"Lỗi: {str(e)}"})


@app.route("/admin/bulk_create", methods=["POST"])
def admin_bulk_create():
    """Tạo nhiều license cùng lúc"""
    try:
        data = request.get_json()
        if data.get("admin_key", "") != SECRET_KEY:
            return jsonify({"success": False, "message": "Admin key không hợp lệ!"})

        count = min(int(data.get("count", 5)), 50)
        plan = data.get("plan", "basic")
        months = int(data.get("months", 1))

        licenses, sha = load_licenses()
        created_keys = []

        for i in range(count):
            user_id = f"BULK_{plan.upper()}_{i+1}"
            license_key, expire_date = generate_license_key(user_id, months)
            licenses[license_key] = {
                "user_id": user_id,
                "expire_date": expire_date,
                "created_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "last_check": None,
                "months": months,
                "plan": plan,
                "status": "active",
                "check_count": 0,
                "notes": f"Bulk create ({count} keys)"
            }
            created_keys.append(license_key)

        if save_licenses(licenses, sha):
            return jsonify({
                "success": True,
                "message": f"Đã tạo {count} license keys",
                "keys": created_keys,
                "count": count
            })
        else:
            return jsonify({"success": False, "message": "Không thể lưu lên GitHub!"})

    except Exception as e:
        return jsonify({"success": False, "message": f"Lỗi: {str(e)}"})


@app.route("/admin/stats", methods=["POST"])
def admin_stats():
    """Thống kê tổng quan"""
    try:
        data = request.get_json()
        if data.get("admin_key", "") != SECRET_KEY:
            return jsonify({"success": False, "message": "Admin key không hợp lệ!"})

        licenses, _ = load_licenses()
        
        total = len(licenses)
        active = 0
        expired = 0
        pending = 0
        revoked = 0

        for key, info in licenses.items():
            if info.get("status") == "revoked":
                revoked += 1
                continue
            
            expire_date = datetime.strptime(info["expire_date"], "%Y-%m-%d")
            days_left = (expire_date - datetime.now()).days
            
            if days_left < 0:
                expired += 1
            elif info.get("hardware_id") is None:
                pending += 1
            else:
                active += 1

        return jsonify({
            "success": True,
            "stats": {
                "total": total,
                "active": active,
                "expired": expired,
                "pending": pending,
                "revoked": revoked
            }
        })

    except Exception as e:
        return jsonify({"success": False, "message": f"Lỗi: {str(e)}"})
