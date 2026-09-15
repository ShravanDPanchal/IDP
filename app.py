import streamlit as st
import os
import re
import hashlib
import secrets
import tempfile
import json
import zipfile
import io
import subprocess
import sys
import html
from pathlib import Path
from typing import Optional, Dict, List, Any
import shutil
import base64
from datetime import datetime, timedelta
from PIL import Image

from qr_utils import decode_qr_from_image_bytes, decode_qr_from_pil, fetch_qr_details, extract_qr_from_pdf_bytes
from yolo_preview_utils import run_yolo_layout_analysis, draw_layout_annotations, get_crop_text
from streamlit_image_coordinates import streamlit_image_coordinates
from fake_invoice_detector import detect_invoice_fraud
from fraud_visualizer import draw_fraud_layout_overlay
from ai_chat_widget import get_ai_chat_widget_html
from ai_doc_engine import ask_document_ai


def safe_run_yolo_layout_analysis(*args, **kwargs):
    """Safely handles yolo layout analysis return tuple regardless of return length."""
    res = run_yolo_layout_analysis(*args, **kwargs)
    if isinstance(res, (list, tuple)):
        if len(res) >= 3:
            return res[0], res[1], res[2]
        elif len(res) == 2:
            return res[0], res[1], []
    return res, {}, []


def render_layout_box_inspector(yolo_pil_img: Image.Image, crops: List[Dict[str, Any]], key_prefix: str = "layout"):
    """Renders an interactive Layout Box Inspector with image on the left and selected box data output on the right."""
    st.markdown("""
    <style>
    .layout-panel-box {
        height: 560px;
        overflow-y: auto;
        padding: 4px 2px;
    }
    .layout-panel-box img { display:block; margin:0 auto; border-radius:8px; }
    .layout-crop-box {
        text-align: center;
        padding: 10px;
        background: #f9fafb;
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        margin-bottom: 12px;
    }
    .layout-crop-box img { max-width:100%; height:auto; border-radius:6px; }
    .layout-text-box {
        font-family: "Source Code Pro", monospace;
        font-size: 12.5px;
        white-space: pre-wrap;
        word-break: break-word;
        background: #0f172a;
        color: #e2e8f0;
        padding: 12px;
        border-radius: 8px;
        line-height: 1.5;
    }
    </style>
    """, unsafe_allow_html=True)

    if not crops:
        st.info("No layout boxes detected for the selected category.")
        st.image(yolo_pil_img, width='stretch')
        return

    st.divider()
    cur_selected_idx = st.session_state.get(f"{key_prefix}_selected_idx", None)
    if cur_selected_idx is not None and (cur_selected_idx < 0 or cur_selected_idx >= len(crops)):
        cur_selected_idx = None

    selected_crop = crops[cur_selected_idx] if cur_selected_idx is not None else None

    # Draw bounding boxes and highlight frame for selected box
    annotated_img = draw_layout_annotations(yolo_pil_img, crops, selected_crop=selected_crop)

    # 2 COLUMNS: Left = Interactive Clickable Image + Dropdown, Right = Selected Box Data Inspector Card
    col_preview, col_inspector = st.columns([1, 1], gap="medium")

    with col_preview:
        with st.container(border=True):
            st.markdown("#### 🎯 Interactive YOLO Layout Preview")
            st.caption("👆 **Click directly on any colored box on the image below** to view its data on the right!")

            # Downscale a display copy so the preview fits on one screen — click
            # coordinates are still mapped back to the full-resolution annotated_img below.
            display_img = annotated_img.copy()
            display_img.thumbnail((560, 540), Image.LANCZOS)

            # Use Streamlit's own fixed-height container (not a manual HTML div) so
            # the custom component actually renders inside a clipped/scrollable area.
            with st.container(height=560, border=False):
                click_value = streamlit_image_coordinates(
                    display_img,
                    key=f"{key_prefix}_img_coord",
                    width=display_img.width,
                    cursor="crosshair"
                )

            # Handle image click mapping
            if click_value is not None:
                last_click = st.session_state.get(f"{key_prefix}_last_click")
                if click_value != last_click:
                    st.session_state[f"{key_prefix}_last_click"] = click_value

                    x_c = click_value.get("x", 0)
                    y_c = click_value.get("y", 0)
                    w_c = click_value.get("width") or click_value.get("w") or 1
                    h_c = click_value.get("height") or click_value.get("h") or 1

                    orig_w, orig_h = annotated_img.size
                    if w_c > 0 and h_c > 0:
                        real_x = int(x_c * (orig_w / w_c))
                        real_y = int(y_c * (orig_h / h_c))

                        matching = []
                        for idx, c_info in enumerate(crops):
                            bx, by, bw, bh = c_info["box"]
                            if bx <= real_x <= bx + bw and by <= real_y <= by + bh:
                                matching.append((idx, c_info))

                        if matching:
                            best_match = min(matching, key=lambda item: item[1]["box"][2] * item[1]["box"][3])
                            new_idx = best_match[0]
                            st.session_state[f"{key_prefix}_selected_idx"] = new_idx
                            st.rerun()
                        else:
                            st.toast(f"Clicked at (x:{real_x}, y:{real_y}) — No layout box at this point.", icon="⚠️")

            # Dropdown selector synced with click state
            box_options = ["--- Select or Click a Layout Box on Image ---"]
            for i, c_info in enumerate(crops, 1):
                box_options.append(f"Box #{i}: [{c_info['class_name'].upper()}] (x:{c_info['box'][0]}, y:{c_info['box'][1]}, w:{c_info['box'][2]}, h:{c_info['box'][3]})")

            sb_index = (cur_selected_idx + 1) if (cur_selected_idx is not None and 0 <= cur_selected_idx < len(crops)) else 0

            selected_option = st.selectbox(
                "Choose Layout Box to Inspect:",
                options=box_options,
                index=sb_index,
                key=f"{key_prefix}_box_inspector_select"
            )

            if selected_option != "--- Select or Click a Layout Box on Image ---":
                box_idx = box_options.index(selected_option) - 1
                if box_idx != cur_selected_idx:
                    st.session_state[f"{key_prefix}_selected_idx"] = box_idx
                    st.rerun()

    with col_inspector:
        with st.container(border=True):
            st.markdown("#### 🔍 Selected Box Data Inspector")
            if cur_selected_idx is not None and 0 <= cur_selected_idx < len(crops):
                sel_box = crops[cur_selected_idx]
                st.success(f"🎯 **Selected Box #{cur_selected_idx + 1}** [{sel_box['class_name'].upper()}]")
                st.caption(f"Category: **{sel_box['class_name'].upper()}** | Position: x={sel_box['box'][0]}, y={sel_box['box'][1]}, w={sel_box['box'][2]}, h={sel_box['box'][3]}")

                crop_buf = io.BytesIO()
                sel_box["crop_pil"].convert("RGB").save(crop_buf, format="PNG")
                crop_b64 = base64.b64encode(crop_buf.getvalue()).decode()

                box_text = get_crop_text(sel_box).strip()
                text_html = html.escape(box_text) if box_text else "No readable text detected inside this specific layout box."

                st.markdown(
                    '<div class="layout-panel-box">'
                    '<div style="font-size:13px;font-weight:700;color:#374151;margin-bottom:6px;">🖼️ Cropped Image Snippet</div>'
                    f'<div class="layout-crop-box"><img src="data:image/png;base64,{crop_b64}" /></div>'
                    '<div style="font-size:13px;font-weight:700;color:#374151;margin-bottom:6px;">📄 Extracted Text / Data</div>'
                    f'<div class="layout-text-box">{text_html}</div>'
                    '</div>',
                    unsafe_allow_html=True
                )
            else:
                st.info("👈 **Click on any colored box on the preview image on the left** (or select from the dropdown) to view its crop image and extracted text right here!")


def get_file_preview_thumbnail_b64(file_bytes: bytes, file_name: str) -> Optional[str]:
    """Generates a small thumbnail of the uploaded image or first PDF page for real-time 3D scanning animation."""
    if not file_bytes:
        return None
    try:
        f_ext = file_name.split(".")[-1].lower() if "." in file_name else ""
        thumb_img = None
        if f_ext == "pdf":
            try:
                import pypdfium2 as pdfium
                pdf_doc = pdfium.PdfDocument(file_bytes)
                if len(pdf_doc) > 0:
                    thumb_img = pdf_doc[0].render(scale=0.5).to_pil()
            except Exception:
                pass
        elif f_ext in ["png", "jpg", "jpeg", "webp", "bmp", "tiff", "tif"]:
            try:
                thumb_img = Image.open(io.BytesIO(file_bytes))
            except Exception:
                pass

        if thumb_img is not None:
            thumb_img.thumbnail((160, 220), Image.LANCZOS)
            buf = io.BytesIO()
            thumb_img.convert("RGB").save(buf, format="JPEG", quality=85)
            b64_str = base64.b64encode(buf.getvalue()).decode("utf-8")
            return f"data:image/jpeg;base64,{b64_str}"
    except Exception:
        pass
    return None


def get_document_scanning_animation_html(
    current_file_name: str = "",
    current_idx: int = 1,
    total_files: int = 1,
    preview_b64: Optional[str] = None
) -> str:
    safe_name = html.escape(current_file_name) if current_file_name else "Document"

    # Dynamic document face inside 3D rotating card
    if preview_b64:
        doc_face_html = f'<div style="width:100%;height:100%;position:relative;background:#ffffff;border-radius:6px;box-shadow:0 4px 14px rgba(0,0,0,0.12);border:1px solid #cbd5e1;overflow:hidden;box-sizing:border-box;display:flex;align-items:center;justify-content:center;"><img src="{preview_b64}" style="width:100%;height:100%;object-fit:cover;display:block;" /></div>'
    else:
        doc_face_html = '<div style="width:100%;height:100%;position:relative;background:#ffffff;border-radius:6px;box-shadow:0 4px 12px rgba(0,0,0,0.08);border:1px solid #cbd5e1;overflow:hidden;box-sizing:border-box;"><div style="position:absolute;top:0;right:0;width:14px;height:14px;background:linear-gradient(135deg,#cbd5e1 50%,#0284c7 50%);border-bottom-left-radius:4px;"></div><div style="position:absolute;top:8px;left:8px;width:14px;height:14px;border-radius:3px;background:#0284c7;display:flex;align-items:center;justify-content:center;color:#fff;font-size:8px;font-weight:700;">📄</div><div style="position:absolute;top:11px;left:26px;width:28px;height:3px;background:#334155;border-radius:2px;"></div><div style="position:absolute;top:28px;left:8px;right:8px;display:flex;flex-direction:column;gap:3px;"><div style="height:2.5px;border-radius:1px;background:#cbd5e1;width:100%;"></div><div style="height:2.5px;border-radius:1px;background:#93c5fd;width:80%;"></div><div style="height:2.5px;border-radius:1px;background:#cbd5e1;width:90%;"></div><div style="height:2.5px;border-radius:1px;background:#cbd5e1;width:60%;"></div></div><div style="position:absolute;bottom:8px;left:8px;right:8px;height:16px;border:1px dashed #cbd5e1;border-radius:3px;background:#f8fafc;display:flex;align-items:center;justify-content:space-around;padding:0 2px;"><div style="width:10px;height:8px;background:#e2e8f0;border-radius:2px;"></div><div style="width:10px;height:8px;background:#93c5fd;border-radius:2px;"></div><div style="width:10px;height:8px;background:#e2e8f0;border-radius:2px;"></div></div></div>'

    return f"""<div style="display:flex;justify-content:center;align-items:center;width:100%;margin:8px 0 16px 0;"><div style="position:relative;width:100%;max-width:440px;background:#ffffff;border:1px solid #e2e8f0;border-radius:12px;padding:20px 16px 16px 16px;box-shadow:0 4px 16px rgba(0,0,0,0.06);display:flex;flex-direction:column;align-items:center;justify-content:center;overflow:hidden;box-sizing:border-box;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;"><div style="width:90px;height:115px;perspective:600px;position:relative;margin-bottom:14px;display:flex;align-items:center;justify-content:center;"><div style="position:absolute;top:-4px;left:-4px;width:8px;height:8px;border-left:2px solid #0284c7;border-top:2px solid #0284c7;z-index:5;"></div><div style="position:absolute;top:-4px;right:-4px;width:8px;height:8px;border-right:2px solid #0284c7;border-top:2px solid #0284c7;z-index:5;"></div><div style="position:absolute;bottom:-4px;left:-4px;width:8px;height:8px;border-left:2px solid #0284c7;border-bottom:2px solid #0284c7;z-index:5;"></div><div style="position:absolute;bottom:-4px;right:-4px;width:8px;height:8px;border-right:2px solid #0284c7;border-bottom:2px solid #0284c7;z-index:5;"></div><div style="position:absolute;left:-6px;right:-6px;height:2px;background:#0284c7;box-shadow:0 0 6px rgba(2,132,199,0.5);border-radius:1px;z-index:10;animation:reevaLaserScan 2s ease-in-out infinite alternate;"></div><div style="width:75px;height:100px;position:absolute;transform-style:preserve-3d;animation:reevaSpinDoc 5s linear infinite;">{doc_face_html}</div></div><div style="text-align:center;z-index:5;width:100%;"><div style="font-size:13.5px;font-weight:700;color:#0f172a;display:flex;align-items:center;justify-content:center;gap:7px;"><div style="width:7px;height:7px;background:#0284c7;border-radius:50%;box-shadow:0 0 6px rgba(2,132,199,0.6);animation:reevaBlinkDot 1.2s infinite alternate;"></div><span>AI Document Scanning Active</span></div><div style="font-size:12.5px;color:#475569;margin-top:4px;font-weight:500;">File {current_idx}/{total_files}: <code style="background:#f1f5f9;color:#0f172a;padding:2px 7px;border-radius:4px;border:1px solid #e2e8f0;font-weight:600;">{safe_name}</code></div><div style="font-size:11.5px;color:#64748b;margin-top:2px;">Neural OCR, Layout Segmentation & Table Extraction in progress...</div></div><style>@keyframes reevaSpinDoc{{0%{{transform:rotateY(0deg) translateY(-2px);}}50%{{transform:rotateY(180deg) translateY(2px);}}100%{{transform:rotateY(360deg) translateY(-2px);}}}}@keyframes reevaLaserScan{{0%{{top:0px;opacity:0.7;}}50%{{opacity:1;}}100%{{top:105px;opacity:0.7;}}}}@keyframes reevaBlinkDot{{0%{{opacity:0.3;}}100%{{opacity:1;}}}}</style></div></div>"""


st.set_page_config(
    page_title="Intelligent Document Processing",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- LOGIN GATE (Google via st.login, or local Email/Password accounts) ---
# Requires secrets configured in .streamlit/secrets.toml — see setup notes at the bottom
# of this file / the SETUP_LOGIN.md doc for exact steps.
#
# NOTE: Email/Password accounts are stored locally in LOCAL_USERS_DB_PATH (a plain
# JSON file next to app.py) with salted SHA-256 password hashes. This is fine for a
# single-machine / personal deployment, but it is NOT a production-grade auth system
# (no rate-limiting, no email verification, file lives unencrypted on disk). For real
# multi-user production use, swap _load_users/_save_users for a proper database.

LOCAL_USERS_DB_PATH = Path(__file__).parent / "local_users.json"
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")


def _load_local_users() -> Dict[str, Any]:
    if LOCAL_USERS_DB_PATH.exists():
        try:
            return json.loads(LOCAL_USERS_DB_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_local_users(users: Dict[str, Any]) -> None:
    try:
        LOCAL_USERS_DB_PATH.write_text(json.dumps(users, indent=2), encoding="utf-8")
    except Exception:
        pass


def _hash_password(password: str, salt: str) -> str:
    return hashlib.sha256((salt + password).encode("utf-8")).hexdigest()


def _create_local_user(email: str, name: str, password: str) -> bool:
    """Returns False if an account with this email already exists."""
    users = _load_local_users()
    key = email.strip().lower()
    if key in users:
        return False
    salt = secrets.token_hex(16)
    users[key] = {"name": name, "salt": salt, "hash": _hash_password(password, salt)}
    _save_local_users(users)
    return True


def _verify_local_user(email: str, password: str):
    """Returns (user_record, status) where status is 'ok' | 'not_found' | 'wrong_password'."""
    users = _load_local_users()
    key = email.strip().lower()
    record = users.get(key)
    if not record:
        return None, "not_found"
    if _hash_password(password, record.get("salt", "")) != record.get("hash"):
        return None, "wrong_password"
    return record, "ok"


# --- Forgot Password (local accounts) ---------------------------------------
# Self-contained reset flow: a 6-digit code (never the code itself, only a
# salted hash of it) is stored against the user in LOCAL_USERS_DB_PATH with a
# 15-minute expiry. If an [smtp] table is present in .streamlit/secrets.toml
# the code is emailed; otherwise it's shown directly on screen, which is
# consistent with this app's existing "personal/single-machine" auth model.

RESET_CODE_TTL_MINUTES = 15


def _create_password_reset_code(email: str) -> Optional[str]:
    """Generates + stores a reset code for an existing local user. Returns
    the plaintext code, or None if no local account matches this email."""
    users = _load_local_users()
    key = email.strip().lower()
    if key not in users:
        return None
    code = f"{secrets.randbelow(1_000_000):06d}"
    salt = secrets.token_hex(8)
    users[key]["reset_code_hash"] = _hash_password(code, salt)
    users[key]["reset_code_salt"] = salt
    users[key]["reset_code_expires"] = (datetime.utcnow() + timedelta(minutes=RESET_CODE_TTL_MINUTES)).isoformat()
    _save_local_users(users)
    return code


def _verify_reset_code(email: str, code: str) -> bool:
    users = _load_local_users()
    record = users.get(email.strip().lower())
    if not record or "reset_code_hash" not in record:
        return False
    expires = record.get("reset_code_expires")
    try:
        if not expires or datetime.fromisoformat(expires) < datetime.utcnow():
            return False
    except Exception:
        return False
    return _hash_password(code.strip(), record.get("reset_code_salt", "")) == record.get("reset_code_hash")


def _apply_password_reset(email: str, new_password: str) -> bool:
    users = _load_local_users()
    key = email.strip().lower()
    if key not in users:
        return False
    salt = secrets.token_hex(16)
    users[key]["salt"] = salt
    users[key]["hash"] = _hash_password(new_password, salt)
    for field in ("reset_code_hash", "reset_code_salt", "reset_code_expires"):
        users[key].pop(field, None)
    _save_local_users(users)
    return True


def _try_send_reset_email(email: str, code: str) -> bool:
    """Best-effort SMTP send using an optional [smtp] table in secrets.toml:
    [smtp]
    host = "smtp.example.com"
    port = 587
    user = "you@example.com"
    password = "app-password"
    from = "you@example.com"   # optional, defaults to user
    Returns False (silently) if not configured or if sending fails, so the
    caller can fall back to showing the code on screen."""
    try:
        smtp_cfg = dict(st.secrets["smtp"]) if "smtp" in st.secrets else None
    except Exception:
        smtp_cfg = None
    if not smtp_cfg:
        return False
    try:
        import smtplib
        from email.mime.text import MIMEText

        msg = MIMEText(
            f"Your password reset code is: {code}\n\n"
            f"This code expires in {RESET_CODE_TTL_MINUTES} minutes. "
            "If you didn't request this, you can ignore this email."
        )
        msg["Subject"] = "Your password reset code"
        msg["From"] = smtp_cfg.get("from") or smtp_cfg.get("user")
        msg["To"] = email
        with smtplib.SMTP(smtp_cfg["host"], int(smtp_cfg.get("port", 587)), timeout=10) as server:
            server.starttls()
            server.login(smtp_cfg["user"], smtp_cfg["password"])
            server.sendmail(msg["From"], [email], msg.as_string())
        return True
    except Exception:
        return False



def check_password_strength(pw: str):
    """Cosmetic-only strength meter — Weak / Medium / Strong / Very Secure."""
    if not pw:
        return 0, "", "#64748B"
    score = 0
    score += 1 if len(pw) >= 8 else 0
    score += 1 if len(pw) >= 12 else 0
    score += 1 if re.search(r"[A-Z]", pw) else 0
    score += 1 if re.search(r"[a-z]", pw) else 0
    score += 1 if re.search(r"[0-9]", pw) else 0
    score += 1 if re.search(r"[^A-Za-z0-9]", pw) else 0

    if score <= 1:
        return score, "Weak", "#ef4444"
    elif score <= 3:
        return score, "Medium", "#f59e0b"
    elif score <= 4:
        return score, "Strong", "#22c55e"
    else:
        return score, "Very Secure", "#06b6d4"


def _render_reset_password_ui():
    """Renders the local-account 'Forgot Password' flow inside the login card.
    Two stages, tracked in st.session_state['reset_stage']:
      'request' (default) -> ask for the account email, issue a reset code
      'confirm'            -> ask for the code + new password, apply the reset
    """
    stage = st.session_state.get("reset_stage", "request")

    if stage == "request":
        st.markdown(
            '<div style="color:rgba(255,255,255,0.8); font-size:0.85rem; margin-bottom:12px;">'
            'Enter your account email and we\'ll send you a 6-digit reset code.</div>',
            unsafe_allow_html=True,
        )
        st.text_input("Email", placeholder="you@example.com", key="reset_email")

        if st.button("Send Reset Code", key="reset_send", width='stretch'):
            email_val = st.session_state.get("reset_email", "").strip()
            st.session_state.pop("_auth_error", None)
            st.session_state.pop("_auth_success", None)

            if not email_val or not EMAIL_RE.match(email_val):
                st.session_state["_auth_error"] = "Please enter a valid email address."
            elif email_val.strip().lower() not in _load_local_users():
                st.session_state["_auth_error"] = "We couldn't find a local account with this email address."
            else:
                code = _create_password_reset_code(email_val)
                emailed = _try_send_reset_email(email_val, code)
                st.session_state["_reset_target_email"] = email_val
                st.session_state["reset_stage"] = "confirm"
                if emailed:
                    st.session_state["_auth_success"] = "A reset code has been emailed to you."
                else:
                    st.session_state["_auth_success"] = (
                        f"Email isn't configured for this app, so here is your reset code: {code}"
                    )
            st.rerun()

    else:  # stage == "confirm"
        target = st.session_state.get("_reset_target_email", "")
        st.markdown(
            f'<div style="color:rgba(255,255,255,0.8); font-size:0.85rem; margin-bottom:12px;">'
            f'Enter the code sent to <b>{html.escape(target)}</b> and choose a new password.</div>',
            unsafe_allow_html=True,
        )
        st.text_input("Reset Code", placeholder="123456", key="reset_code")
        st.text_input("New Password", placeholder="Enter new password", type="password", key="reset_new_password")
        st.text_input("Confirm New Password", placeholder="Re-enter new password", type="password", key="reset_confirm_password")

        if st.button("Reset Password", key="reset_confirm_btn", width='stretch'):
            code_val = st.session_state.get("reset_code", "").strip()
            new_pw = st.session_state.get("reset_new_password", "")
            confirm_pw = st.session_state.get("reset_confirm_password", "")
            st.session_state.pop("_auth_error", None)
            st.session_state.pop("_auth_success", None)

            if not code_val:
                st.session_state["_auth_error"] = "Please enter the reset code."
            elif not new_pw:
                st.session_state["_auth_error"] = "Please enter a new password."
            elif new_pw != confirm_pw:
                st.session_state["_auth_error"] = "Passwords do not match. Please try again."
            elif not _verify_reset_code(target, code_val):
                st.session_state["_auth_error"] = "That code is invalid or has expired. Please request a new one."
            else:
                _apply_password_reset(target, new_pw)
                st.session_state.login_mode = "login"
                for k in ("reset_stage", "_reset_target_email", "reset_email",
                          "reset_code", "reset_new_password", "reset_confirm_password"):
                    st.session_state.pop(k, None)
                st.session_state["_prefill_auth_email"] = target
                st.session_state["_auth_success"] = "Your password has been reset. Please log in."
            st.rerun()

        if st.button("Use a different email", key="reset_use_diff_email", width='stretch'):
            st.session_state.pop("reset_stage", None)
            st.session_state.pop("_auth_error", None)
            st.session_state.pop("_auth_success", None)
            st.rerun()


def render_login_screen():
    if "login_mode" not in st.session_state:
        st.session_state.login_mode = "login"
    is_login = st.session_state.login_mode == "login"
    is_reset = st.session_state.login_mode == "reset"

    st.markdown(f"""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Space+Grotesk:wght@500;700&family=JetBrains+Mono:wght@500;700&display=swap');

        /* Clean Modern Dark Background */
        [data-testid="stAppViewContainer"], .stApp {{
            background: #0b0f19 !important;
            background-color: #0b0f19 !important;
            font-family: 'Plus Jakarta Sans', sans-serif !important;
            overflow-x: hidden;
        }}
        [data-testid="stHeader"] {{ background: transparent !important; }}
        .block-container {{ padding-top: 2.5rem !important; max-width: 1200px !important; }}

        /* Clean Perspective Grid Background */
        .cyber-grid-floor {{
            position: fixed;
            top: 0; left: 0; width: 100vw; height: 100vh;
            background-image: 
                linear-gradient(rgba(255, 255, 255, 0.03) 1px, transparent 1px),
                linear-gradient(90deg, rgba(255, 255, 255, 0.03) 1px, transparent 1px);
            background-size: 40px 40px;
            pointer-events: none;
            z-index: 0;
            mask-image: radial-gradient(circle at 50% 50%, rgba(0,0,0,0.85) 30%, transparent 80%);
            -webkit-mask-image: radial-gradient(circle at 50% 50%, rgba(0,0,0,0.85) 30%, transparent 80%);
        }}

        /* Subtle Laser Beam */
        @keyframes laserSweep {{
            0%   {{ top: -5%; opacity: 0; }}
            10%  {{ opacity: 0.6; }}
            90%  {{ opacity: 0.6; }}
            100% {{ top: 105%; opacity: 0; }}
        }}
        .cyber-scanner-laser {{
            position: fixed;
            left: 0; width: 100vw; height: 1px;
            background: rgba(56, 189, 248, 0.5);
            box-shadow: 0 0 12px rgba(56, 189, 248, 0.4);
            pointer-events: none;
            z-index: 1;
            animation: laserSweep 7s ease-in-out infinite;
        }}

        /* Floating HUD Badges */
        @keyframes badgeFloat {{
            0%, 100% {{ transform: translateY(0px); }}
            50%      {{ transform: translateY(-6px); }}
        }}
        .hud-badge {{
            position: fixed;
            padding: 7px 14px;
            background: #0f172a;
            border: 1px solid #1e293b;
            border-radius: 999px;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.72rem;
            font-weight: 600;
            color: #94a3b8;
            letter-spacing: 0.05em;
            display: flex;
            align-items: center;
            gap: 8px;
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4);
            pointer-events: none;
            z-index: 2;
            animation: badgeFloat 6s ease-in-out infinite;
        }}
        .hud-badge-dot {{
            width: 7px; height: 7px; border-radius: 50%;
            background: #10b981;
            box-shadow: 0 0 8px #10b981;
        }}

        /* Clean Minimalist Login Card */
        .st-key-login_card {{
            position: relative !important;
            max-width: 540px !important;
            width: 100% !important;
            margin: 0 auto !important;
            background: #0f172a !important;
            border: 1px solid #1e293b !important;
            border-radius: 20px !important;
            padding: 28px 32px 32px 32px !important;
            box-shadow: 0 20px 50px rgba(0, 0, 0, 0.6) !important;
            z-index: 10 !important;
            overflow: hidden !important;
        }}

        /* Clean Brand Header with Dynamic 3D Spinning Icon */
        .mineru-brand {{
            text-align: center;
            padding: 4px 8px 16px 8px;
            position: relative;
        }}
        @keyframes iconSpinPulse {{
            0%   {{ transform: rotateY(0deg) scale(1); filter: drop-shadow(0 0 12px rgba(56, 189, 248, 0.4)); }}
            50%  {{ transform: rotateY(180deg) scale(1.08); filter: drop-shadow(0 0 24px rgba(56, 189, 248, 0.7)); }}
            100% {{ transform: rotateY(360deg) scale(1); filter: drop-shadow(0 0 12px rgba(56, 189, 248, 0.4)); }}
        }}
        .mineru-brand-icon-wrapper {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 68px;
            height: 68px;
            border-radius: 20px;
            background: #1e293b;
            border: 1px solid #334155;
            box-shadow: 0 10px 25px rgba(0, 0, 0, 0.4);
            margin-bottom: 12px;
            animation: iconSpinPulse 10s ease-in-out infinite;
        }}
        .mineru-brand-icon {{ font-size: 2.2rem; }}

        .mineru-brand-title {{
            font-family: 'Space Grotesk', sans-serif;
            font-size: clamp(1.35rem, 2.2vw, 1.75rem);
            font-weight: 700;
            letter-spacing: -0.02em;
            color: #ffffff;
            margin-top: 2px;
            line-height: 1.25;
            white-space: nowrap;
        }}
        .mineru-brand-tag {{
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 5px 14px;
            background: #1e293b;
            border: 1px solid #334155;
            border-radius: 999px;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.74rem;
            font-weight: 600;
            color: #38bdf8;
            letter-spacing: 0.04em;
            margin-top: 10px;
        }}
        .mineru-brand-sub {{
            color: #94a3b8;
            font-size: 0.86rem;
            margin-top: 8px;
            font-weight: 400;
        }}

        /* Clean Pill Switcher Tabs */
        .st-key-tab_login button, .st-key-tab_signup button {{
            border-radius: 10px !important;
            font-family: 'Plus Jakarta Sans', sans-serif !important;
            font-weight: 600 !important;
            font-size: 0.9rem !important;
            letter-spacing: 0.01em !important;
            padding: 0.6rem 1rem !important;
            transition: all 0.2s ease !important;
        }}
        .st-key-tab_login button {{
            background: {'#2563eb' if is_login else '#1e293b'} !important;
            color: {'#ffffff' if is_login else '#94a3b8'} !important;
            border: 1px solid {'#3b82f6' if is_login else '#334155'} !important;
            box-shadow: {'0 4px 12px rgba(37, 99, 235, 0.3)' if is_login else 'none'} !important;
        }}
        .st-key-tab_signup button {{
            background: {'#2563eb' if not is_login else '#1e293b'} !important;
            color: {'#ffffff' if not is_login else '#94a3b8'} !important;
            border: 1px solid {'#3b82f6' if not is_login else '#334155'} !important;
            box-shadow: {'0 4px 12px rgba(37, 99, 235, 0.3)' if not is_login else 'none'} !important;
        }}
        .st-key-tab_login button:hover, .st-key-tab_signup button:hover {{
            border-color: #60a5fa !important;
            color: #ffffff !important;
        }}

        /* Clean Crisp High-Contrast Input Fields */
        .st-key-login_card [data-testid="stTextInputRootElement"],
        .st-key-login_card [data-baseweb="input"],
        .st-key-login_card [data-baseweb="base-input"],
        .st-key-login_card [data-baseweb="input"] > div,
        .st-key-login_card div[data-baseweb="input"] {{
            background: #ffffff !important;
            background-color: #ffffff !important;
            border: 1px solid #cbd5e1 !important;
            border-radius: 10px !important;
            overflow: hidden !important;
            transition: all 0.2s ease !important;
        }}
        .st-key-login_card [data-baseweb="input"]:focus-within,
        .st-key-login_card [data-baseweb="base-input"]:focus-within {{
            background: #ffffff !important;
            background-color: #ffffff !important;
            border-color: #2563eb !important;
            box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.2) !important;
        }}

        .st-key-login_card input {{
            background: #ffffff !important;
            background-color: #ffffff !important;
            border: none !important;
            color: #0f172a !important;
            caret-color: #0f172a !important;
            -webkit-text-fill-color: #0f172a !important;
            font-size: 0.92rem !important;
            font-weight: 500 !important;
            padding: 0.7rem 0.9rem !important;
        }}
        .st-key-login_card input::placeholder {{
            color: #94a3b8 !important;
            -webkit-text-fill-color: #94a3b8 !important;
            font-weight: 400 !important;
        }}

        /* Browser Autofill Fix */
        .st-key-login_card input:-webkit-autofill,
        .st-key-login_card input:-webkit-autofill:hover,
        .st-key-login_card input:-webkit-autofill:focus,
        .st-key-login_card input:-webkit-autofill:active {{
            -webkit-box-shadow: 0 0 0 1000px #ffffff inset !important;
            -webkit-text-fill-color: #0f172a !important;
            caret-color: #0f172a !important;
            font-weight: 500 !important;
            transition: background-color 5000s ease-in-out 0s !important;
        }}

        /* Instructions & Icons */
        .st-key-login_card [data-testid="stTextInputInstructions"],
        .st-key-login_card [data-testid="stTextInputInstructions"] p {{
            color: #64748b !important;
            font-size: 0.75rem !important;
            font-weight: 500 !important;
        }}
        .st-key-login_card [data-baseweb="input"] button,
        .st-key-login_card [data-baseweb="input"] svg {{
            color: #475569 !important;
            fill: #475569 !important;
        }}
        .st-key-login_card label p {{
            color: #e2e8f0 !important;
            font-weight: 600 !important;
            font-size: 0.86rem !important;
            letter-spacing: 0.01em !important;
        }}

        /* Solid Cool Action Button */
        .st-key-auth_submit button {{
            background: #2563eb !important;
            color: #ffffff !important;
            border: 1px solid #3b82f6 !important;
            border-radius: 10px !important;
            font-family: 'Plus Jakarta Sans', sans-serif !important;
            font-weight: 600 !important;
            font-size: 0.95rem !important;
            letter-spacing: 0.01em !important;
            padding: 0.75rem 1.2rem !important;
            transition: all 0.2s ease !important;
            cursor: pointer !important;
            box-shadow: 0 4px 14px rgba(37, 99, 235, 0.3) !important;
        }}
        .st-key-auth_submit button:hover {{
            background: #1d4ed8 !important;
            border-color: #2563eb !important;
            transform: translateY(-1px) !important;
            box-shadow: 0 6px 18px rgba(37, 99, 235, 0.4) !important;
        }}

        /* Clean Google Trigger */
        .st-key-google_trigger button {{
            background: #1e293b !important;
            color: #f8fafc !important;
            border: 1px solid #334155 !important;
            border-radius: 10px !important;
            font-weight: 600 !important;
            font-size: 0.88rem !important;
            padding: 0.7rem 1rem !important;
            transition: all 0.2s ease !important;
        }}
        .st-key-google_trigger button:hover {{
            background: #334155 !important;
            border-color: #475569 !important;
            color: #ffffff !important;
            transform: translateY(-1px) !important;
        }}

        .st-key-forgot_pw button, .st-key-reset_back_login button {{
            background: transparent !important;
            border: none !important;
            color: #94a3b8 !important;
            font-size: 0.82rem !important;
            font-weight: 500 !important;
            transition: color 0.2s ease !important;
        }}
        .st-key-forgot_pw button:hover, .st-key-reset_back_login button:hover {{
            color: #38bdf8 !important;
        }}

        .st-key-reset_use_diff_email button {{
            background: transparent !important;
            border: none !important;
            color: #94a3b8 !important;
            font-size: 0.78rem !important;
        }}
        .st-key-reset_send button, .st-key-reset_confirm_btn button {{
            background: #2563eb !important;
            color: #ffffff !important;
            border: 1px solid #3b82f6 !important;
            border-radius: 10px !important;
            font-weight: 600 !important;
            padding: 0.75rem 1rem !important;
            box-shadow: 0 4px 14px rgba(37, 99, 235, 0.3) !important;
        }}

        .mineru-divider {{
            display: flex; align-items: center; gap: 14px; margin: 12px 0 16px 0;
            color: #64748b; font-size: 0.72rem; font-weight: 600; letter-spacing: 0.08em;
        }}
        .mineru-divider::before, .mineru-divider::after {{
            content: ""; flex: 1; height: 1px;
            background: #1e293b;
        }}

        .mineru-strength-row {{
            display: flex; align-items: center; gap: 10px;
            margin: -4px 0 12px 0;
        }}
        .mineru-strength-bar {{
            flex: 1; display: flex; gap: 6px;
        }}
        .mineru-strength-seg {{
            height: 5px; flex: 1; border-radius: 999px;
            background: #1e293b;
            transition: background 0.25s ease;
        }}
        .mineru-strength-label {{
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.75rem; font-weight: 600; min-width: 80px; text-align: right;
        }}

        .mineru-banner {{
            display: flex; align-items: flex-start; gap: 12px;
            border-radius: 10px; padding: 12px 16px; margin: 4px 0 16px 0;
            font-size: 0.86rem; font-weight: 500; line-height: 1.45;
        }}
        .mineru-banner-icon {{ font-size: 1.1rem; margin-top: 1px; }}
        .mineru-banner-error {{
            background: #451a1a;
            border: 1px solid #ef4444;
            color: #fca5a5;
        }}
        .mineru-banner-info {{
            background: #0c4a6e;
            border: 1px solid #0284c7;
            color: #bae6fd;
        }}
        .mineru-banner-success {{
            background: #064e3b;
            border: 1px solid #10b981;
            color: #a7f3d0;
        }}
    </style>

    <!-- Background Elements -->
    <div class="cyber-grid-floor"></div>
    <div class="cyber-scanner-laser"></div>

    <!-- Floating HUD Badges -->
    <div class="hud-badge" style="top: 24px; left: 28px;">
        <span class="hud-badge-dot"></span>
        <span>NEURAL OCR CORE v2.5 [ACTIVE]</span>
    </div>
    <div class="hud-badge" style="top: 24px; right: 28px;">
        <span class="hud-badge-dot" style="background:#ef4444; box-shadow:0 0 8px #ef4444;"></span>
        <span>FORENSIC FRAUD DETECTOR [ARMED]</span>
    </div>
    <div class="hud-badge" style="bottom: 24px; left: 28px;">
        <span class="hud-badge-dot" style="background:#38bdf8; box-shadow:0 0 8px #38bdf8;"></span>
        <span>YOLOv11 LAYOUT SEGMENTATION</span>
    </div>
    <div class="hud-badge" style="bottom: 24px; right: 28px;">
        <span class="hud-badge-dot" style="background:#818cf8; box-shadow:0 0 8px #818cf8;"></span>
        <span>MULTIMODAL ZERO-TRUST AUTH</span>
    </div>
    """, unsafe_allow_html=True)

    # Interactive Full-Screen Particle / Quantum Laser Constellation Canvas
    st.components.v1.html("""
    <canvas id="quantum-constellation-canvas" style="position:fixed; top:0; left:0; width:100vw; height:100vh; z-index:0; pointer-events:none;"></canvas>
    <script>
    (function() {
        const parentDoc = window.parent.document;
        let canvas = parentDoc.getElementById('quantum-constellation-canvas');
        if (!canvas) {
            canvas = document.createElement('canvas');
            canvas.id = 'quantum-constellation-canvas';
            canvas.style.position = 'fixed';
            canvas.style.top = '0';
            canvas.style.left = '0';
            canvas.style.width = '100vw';
            canvas.style.height = '100vh';
            canvas.style.zIndex = '0';
            canvas.style.pointerEvents = 'none';
            parentDoc.body.appendChild(canvas);
        }

        const ctx = canvas.getContext('2d');
        let width = canvas.width = parentDoc.documentElement.clientWidth || window.innerWidth;
        let height = canvas.height = parentDoc.documentElement.clientHeight || window.innerHeight;

        window.parent.addEventListener('resize', () => {
            width = canvas.width = parentDoc.documentElement.clientWidth || window.innerWidth;
            height = canvas.height = parentDoc.documentElement.clientHeight || window.innerHeight;
        });

        const mouse = { x: width / 2, y: height / 2, radius: 150 };
        window.parent.addEventListener('mousemove', (e) => {
            mouse.x = e.clientX;
            mouse.y = e.clientY;
        });

        // Nodes with velocity, size, and pulse
        const numParticles = Math.min(60, Math.floor((width * height) / 22000));
        const particles = [];
        const colors = ['#38bdf8', '#60a5fa', '#94a3b8', '#0284c7'];

        for (let i = 0; i < numParticles; i++) {
            particles.push({
                x: Math.random() * width,
                y: Math.random() * height,
                vx: (Math.random() - 0.5) * 0.6,
                vy: (Math.random() - 0.5) * 0.6,
                size: Math.random() * 2 + 1,
                color: colors[Math.floor(Math.random() * colors.length)],
                pulse: Math.random() * Math.PI * 2
            });
        }

        // Floating holographic document wireframes
        const holoDocs = [
            { x: width * 0.12, y: height * 0.35, vx: 0.15, vy: 0.1, w: 90, h: 120, rot: -0.08 },
            { x: width * 0.82, y: height * 0.40, vx: -0.12, vy: 0.08, w: 95, h: 125, rot: 0.10 }
        ];

        function draw() {
            // If the user is logged in (login card is gone), remove the canvas and stop animation
            if (!parentDoc.querySelector('.st-key-login_card')) {
                if (canvas && canvas.parentNode) {
                    canvas.remove();
                }
                return;
            }

            ctx.clearRect(0, 0, width, height);

            // Draw Floating Hologram Wireframes
            holoDocs.forEach(doc => {
                doc.x += doc.vx;
                doc.y += doc.vy;
                if (doc.x < 50 || doc.x > width - 150) doc.vx *= -1;
                if (doc.y < 80 || doc.y > height - 200) doc.vy *= -1;

                ctx.save();
                ctx.translate(doc.x, doc.y);
                ctx.rotate(doc.rot);
                ctx.strokeStyle = 'rgba(56, 189, 248, 0.18)';
                ctx.lineWidth = 1.5;
                ctx.strokeRect(-doc.w/2, -doc.h/2, doc.w, doc.h);

                // Wireframe lines
                ctx.fillStyle = 'rgba(129, 140, 248, 0.12)';
                ctx.fillRect(-doc.w/2 + 10, -doc.h/2 + 14, doc.w - 20, 8);
                ctx.fillRect(-doc.w/2 + 10, -doc.h/2 + 30, doc.w - 30, 4);
                ctx.fillRect(-doc.w/2 + 10, -doc.h/2 + 40, doc.w - 25, 4);
                ctx.fillRect(-doc.w/2 + 10, -doc.h/2 + 50, doc.w - 35, 4);
                ctx.restore();
            });

            // Update & Draw Quantum Particles & Laser Filaments
            for (let i = 0; i < particles.length; i++) {
                const p = particles[i];
                p.x += p.vx;
                p.y += p.vy;
                p.pulse += 0.03;

                if (p.x < 0 || p.x > width) p.vx *= -1;
                if (p.y < 0 || p.y > height) p.vy *= -1;

                // Mouse interaction
                const dx = mouse.x - p.x;
                const dy = mouse.y - p.y;
                const dist = Math.sqrt(dx * dx + dy * dy);
                if (dist < mouse.radius) {
                    const angle = Math.atan2(dy, dx);
                    p.x -= Math.cos(angle) * 1.2;
                    p.y -= Math.sin(angle) * 1.2;
                }

                // Draw Particle Node
                const currentSize = p.size + Math.sin(p.pulse) * 0.6;
                ctx.beginPath();
                ctx.arc(p.x, p.y, Math.max(0.5, currentSize), 0, Math.PI * 2);
                ctx.fillStyle = p.color;
                ctx.shadowBlur = 12;
                ctx.shadowColor = p.color;
                ctx.fill();
                ctx.shadowBlur = 0;

                // Draw Connections
                for (let j = i + 1; j < particles.length; j++) {
                    const p2 = particles[j];
                    const djx = p.x - p2.x;
                    const djy = p.y - p2.y;
                    const d = Math.sqrt(djx * djx + djy * djy);
                    if (d < 135) {
                        const alpha = (1 - d / 135) * 0.32;
                        ctx.beginPath();
                        ctx.moveTo(p.x, p.y);
                        ctx.lineTo(p2.x, p2.y);
                        ctx.strokeStyle = `rgba(56, 189, 248, ${alpha})`;
                        ctx.lineWidth = 1;
                        ctx.stroke();
                    }
                }
            }

            requestAnimationFrame(draw);
        }

        draw();
    })();
    </script>
    """, height=0)

    _, mid_col, _ = st.columns([1, 2.6, 1])
    with mid_col:
        with st.container(border=True, key="login_card"):
            st.markdown("""
            <div class="mineru-brand">
                <div class="mineru-brand-icon-wrapper">
                    <div class="mineru-brand-icon">📄</div>
                </div>
                <div class="mineru-brand-title">Intelligent Document Processing</div>
                <div class="mineru-brand-tag">⚡ QUANTUM VISION OCR &amp; FRAUD FORENSICS v2.5</div>
                <div class="mineru-brand-sub">Autonomous Layout Parsing • Forensic Risk Scoring • QR Insight</div>
            </div>
            """, unsafe_allow_html=True)

            if not is_reset:
                tab_col1, tab_col2 = st.columns(2)
                with tab_col1:
                    if st.button("Log In", key="tab_login", width='stretch'):
                        st.session_state.login_mode = "login"
                        st.session_state.pop("_auth_error", None)
                        st.session_state.pop("_auth_success", None)
                        st.rerun()
                with tab_col2:
                    if st.button("Sign Up", key="tab_signup", width='stretch'):
                        st.session_state.login_mode = "signup"
                        st.session_state.pop("_auth_error", None)
                        st.session_state.pop("_auth_success", None)
                        st.rerun()

                st.write("")

            if is_reset:
                _render_reset_password_ui()

            if "_prefill_auth_email" in st.session_state and not is_reset:
                st.session_state["auth_email"] = st.session_state.pop("_prefill_auth_email")

            if not is_reset and not is_login:
                st.text_input("Full Name", placeholder="Enter your name", key="signup_name")
            if not is_reset:
                st.text_input("Email", placeholder="you@example.com", key="auth_email")
                st.text_input("Password", placeholder="Enter Password", type="password", key="auth_password")

            if not is_reset and not is_login:
                pw_score, pw_label, pw_color = check_password_strength(st.session_state.get("auth_password", ""))
                seg_map = {"Weak": 1, "Medium": 2, "Strong": 3, "Very Secure": 4}
                filled = seg_map.get(pw_label, 0)
                segs_html = "".join(
                    f'<div class="mineru-strength-seg" style="background:{pw_color if i < filled else "rgba(255,255,255,0.18)"};"></div>'
                    for i in range(4)
                )
                st.markdown(
                    f'<div class="mineru-strength-row">'
                    f'<div class="mineru-strength-bar">{segs_html}</div>'
                    f'<div class="mineru-strength-label" style="color:{pw_color if pw_label else "rgba(255,255,255,0.4)"};">{pw_label or "—"}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                st.text_input("Confirm Password", placeholder="Re-enter Password", type="password", key="signup_confirm")

            if not is_reset and st.button("Sign Up" if not is_login else "Login", key="auth_submit", width='stretch'):
                email_val = st.session_state.get("auth_email", "").strip()
                pw_val = st.session_state.get("auth_password", "")
                st.session_state.pop("_auth_error", None)
                st.session_state.pop("_auth_success", None)

                if not email_val or not EMAIL_RE.match(email_val):
                    st.session_state["_auth_error"] = "Please enter a valid email address."
                elif not pw_val:
                    st.session_state["_auth_error"] = "Please enter your password."
                elif not is_login and pw_val != st.session_state.get("signup_confirm", ""):
                    st.session_state["_auth_error"] = "Passwords do not match. Please try again."
                elif is_login:
                    record, status = _verify_local_user(email_val, pw_val)
                    if status == "not_found":
                        st.session_state["_auth_error"] = "We couldn't find an account with this email address."
                    elif status == "wrong_password":
                        st.session_state["_auth_error"] = "Incorrect password. Please try again."
                    else:
                        st.session_state["local_authenticated"] = True
                        st.session_state["local_user"] = {
                            "email": email_val,
                            "name": record.get("name") or email_val.split("@")[0],
                        }
                        st.rerun()
                else:
                    # Sign Up: create the account locally, then send them to Log In.
                    if email_val.strip().lower() in _load_local_users():
                        st.session_state["_auth_error"] = "An account with this email already exists. Please log in instead."
                    else:
                        name_val = st.session_state.get("signup_name", "").strip() or email_val.split("@")[0]
                        _create_local_user(email_val, name_val, pw_val)
                        st.session_state.login_mode = "login"
                        st.session_state["_auth_success"] = "Your account has been created! Please log in to continue."
                        st.session_state["_prefill_auth_email"] = email_val
                        st.session_state.pop("auth_password", None)
                        st.rerun()

            if st.session_state.get("_auth_error"):
                st.markdown(
                    f'<div class="mineru-banner mineru-banner-error">'
                    f'<span class="mineru-banner-icon">⚠️</span>'
                    f'<span>{html.escape(st.session_state["_auth_error"])}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

            if st.session_state.get("_auth_success"):
                st.markdown(
                    f'<div class="mineru-banner mineru-banner-success">'
                    f'<span class="mineru-banner-icon">✅</span>'
                    f'<span>{html.escape(st.session_state["_auth_success"])}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

            if is_login:
                fp_col1, fp_col2, fp_col3 = st.columns([1, 1.4, 1])
                with fp_col2:
                    if st.button("Forgot Password?", key="forgot_pw", width='stretch'):
                        st.session_state.login_mode = "reset"
                        st.session_state.pop("reset_stage", None)
                        st.session_state.pop("_auth_error", None)
                        st.session_state.pop("_auth_success", None)
                        st.rerun()

            if is_reset:
                back_col1, back_col2, back_col3 = st.columns([1, 1.4, 1])
                with back_col2:
                    if st.button("← Back to Log In", key="reset_back_login", width='stretch'):
                        st.session_state.login_mode = "login"
                        for k in ("reset_stage", "_reset_target_email", "reset_email",
                                  "reset_code", "reset_new_password", "reset_confirm_password",
                                  "_auth_error", "_auth_success"):
                            st.session_state.pop(k, None)
                        st.rerun()

            if not is_reset:
                st.markdown('<div class="mineru-divider">OR CONTINUE WITH</div>', unsafe_allow_html=True)

                if st.button("Continue with Google", key="google_trigger", width='stretch'):
                    try:
                        st.login("google")
                    except Exception as e:
                        st.session_state["_auth_error"] = (
                            "Google OAuth requires credentials in `.streamlit/secrets.toml`. "
                            "Please use Email & Password to log in, or configure your Google Client ID/Secret."
                        )
                        st.rerun()


def _is_logged_in():
    try:
        return getattr(st.user, "is_logged_in", False)
    except Exception:
        return False

if not _is_logged_in() and not st.session_state.get("local_authenticated"):
    render_login_screen()
    st.stop()

# Ensure all login canvas particles, grids, and HUD badges are completely removed from the main workspace
st.components.v1.html("""
<script>
(function() {
    try {
        const pdoc = window.parent.document;
        const c = pdoc.getElementById('quantum-constellation-canvas');
        if (c) c.remove();
        pdoc.querySelectorAll('.cyber-grid-floor, .cyber-scanner-laser, .hud-badge').forEach(el => el.remove());
    } catch(e) {}
})();
</script>
""", height=0)

# Logged in (either via Google, or a local Email/Password account) — show who's
# signed in and a logout option in the sidebar.
def _do_logout():
    try:
        if getattr(st.user, "is_logged_in", False):
            st.logout()
    except Exception:
        pass
    st.session_state.pop("local_authenticated", None)
    st.session_state.pop("local_user", None)


_local_user = st.session_state.get("local_user") or {}
_st_user_name = None
_st_user_email = None
try:
    if getattr(st.user, "is_logged_in", False):
        _st_user_name = st.user.get("name")
        _st_user_email = st.user.get("email")
except Exception:
    pass

_display_name = (
    _st_user_name
    or _local_user.get("name")
    or _st_user_email
    or _local_user.get("email")
    or "Signed in"
)

with st.sidebar:
    st.markdown(f"👋 **{_display_name}**")
    st.button("Log out", on_click=_do_logout, key="logout_btn", width='stretch')
    st.divider()

MODEL_PATH = Path("./MinerU2.5-Pro-2605-1.2B")
SUPPORTED_FORMATS = {
    "PDF": "pdf",
    "DOCX": "docx",
    "PPTX": "pptx",
    "XLSX": "xlsx",
    "PNG": "png",
    "JPG": "jpg",
    "JPEG": "jpeg"
}

MINERU_CLI_PREFIX = None
_venv_python = Path(__file__).parent / ".venv" / "Scripts" / "python.exe"
_venv_mineru = Path(__file__).parent / ".venv" / "Scripts" / "mineru.exe"
if _venv_python.exists():
    VENV_PYTHON = str(_venv_python)
    MINERU_CLI_PREFIX = [VENV_PYTHON, "-c", "from mineru.cli.client import main; main()"]
else:
    VENV_PYTHON = "python"
    if _venv_mineru.exists():
        MINERU_CLI_PREFIX = [str(_venv_mineru)]
    else:
        MINERU_CLI_PREFIX = ["python", "-c", "from mineru.cli.client import main; main()"]

OFFICE_EXTS = {"docx", "pptx", "xlsx"}
IMAGE_EXTS = {"png", "jpg", "jpeg"}
PDF_EXTS = {"pdf"}


class CachedUploadedDocument:
    """Persistent in-memory wrapper for uploaded documents ensuring byte persistence across reruns."""
    def __init__(self, name: str, data: bytes):
        self.name = name
        self._data = data

    def getvalue(self) -> bytes:
        return self._data

    def getbuffer(self):
        return memoryview(self._data)


if "pipeline" not in st.session_state:
    st.session_state.pipeline = None

if "uploaded_file" not in st.session_state:
    st.session_state.uploaded_file = None

if "uploaded_files" not in st.session_state:
    st.session_state.uploaded_files = []

if "uploader_version" not in st.session_state:
    st.session_state.uploader_version = 0

if "extraction_results" not in st.session_state:
    st.session_state.extraction_results = None

if "extraction_results_dict" not in st.session_state:
    st.session_state.extraction_results_dict = {}

if "preview_page_num" not in st.session_state:
    st.session_state.preview_page_num = 1

if "status_log" not in st.session_state:
    st.session_state.status_log = []

if "processing" not in st.session_state:
    st.session_state.processing = False


def clear_session():
    st.session_state.uploaded_file = None
    st.session_state.uploaded_files = []
    st.session_state.uploader_version += 1
    st.session_state.extraction_results = None
    st.session_state.extraction_results_dict = {}
    st.session_state.preview_page_num = 1
    st.session_state.status_log = []
    st.session_state.processing = False
    log_status("Session cleared")


def log_status(status: str):
    timestamp = datetime.now().strftime("%H:%M:%S")
    st.session_state.status_log.append(f"[{timestamp}] {status}")


def get_file_ext(filename: str) -> str:
    return Path(filename).suffix.lower().lstrip(".")


def find_parse_dir(output_root: Path, stem: str, backend: str, parse_method: str, is_office: bool) -> Optional[Path]:
    candidates = []

    if is_office:
        candidates.append(output_root / stem / "office")
    elif backend.startswith("pipeline"):
        candidates.append(output_root / stem / parse_method)
    elif backend.startswith("vlm"):
        candidates.append(output_root / stem / "vlm")
    elif backend.startswith("hybrid"):
        candidates.append(output_root / stem / f"hybrid_{parse_method}")

    candidates.extend([
        output_root / stem / parse_method,
        output_root / stem / "txt",
        output_root / stem / "auto",
        output_root / stem / "ocr",
        output_root / stem / "vlm",
        output_root / stem / f"hybrid_{parse_method}",
        output_root / stem / "hybrid_auto",
        output_root / stem / "hybrid_txt",
        output_root / stem / "office",
        output_root / stem,
        output_root,
    ])

    for cand in candidates:
        if cand.exists() and cand.is_dir():
            middle = cand / f"{stem}_middle.json"
            md = cand / f"{stem}.md"
            content = cand / f"{stem}_content_list.json"
            if middle.exists() or md.exists() or content.exists():
                return cand

    try:
        for root, dirs, files in os.walk(str(output_root)):
            if f"{stem}_middle.json" in files or f"{stem}.md" in files:
                return Path(root)
    except Exception:
        pass

    return None


def read_output_files(output_dir: Path, stem: str) -> Dict[str, Any]:
    results = {
        "markdown": "",
        "text": "",
        "json": {},
        "metadata": {},
        "images": [],
        "image_bytes_list": []
    }

    md_path = output_dir / f"{stem}.md"
    if md_path.exists():
        results["markdown"] = md_path.read_text(encoding="utf-8", errors="ignore")

    content_json = output_dir / f"{stem}_content_list.json"
    if content_json.exists():
        try:
            results["json"] = json.loads(content_json.read_text(encoding="utf-8", errors="ignore"))
        except Exception:
            pass

    content_v2 = output_dir / f"{stem}_content_list_v2.json"
    if not results["json"] and content_v2.exists():
        try:
            results["json"] = json.loads(content_v2.read_text(encoding="utf-8", errors="ignore"))
        except Exception:
            pass

    middle_json = output_dir / f"{stem}_middle.json"
    if middle_json.exists():
        try:
            mj = json.loads(middle_json.read_text(encoding="utf-8", errors="ignore"))
            pdf_info = mj.get("pdf_info", [])
            text_parts = []
            for page in pdf_info:
                if isinstance(page, dict):
                    for block in page.get("layout_dets", []) or []:
                        if isinstance(block, dict) and block.get("text"):
                            text_parts.append(block["text"])
            results["text"] = "\n".join(text_parts)
            results["metadata"]["_backend"] = mj.get("_backend", "")
            results["metadata"]["page_count"] = len(pdf_info) if isinstance(pdf_info, list) else 0
            results["metadata"]["_middle_json_exists"] = True
        except Exception:
            pass

    if not results["text"] and results["markdown"]:
        results["text"] = results["markdown"]

    images_dir = output_dir / "images"
    if images_dir.exists():
        for p in sorted(images_dir.glob("*")):
            if p.is_file():
                results["images"].append(p.name)
                try:
                    results["image_bytes_list"].append({
                        "name": p.name,
                        "bytes": p.read_bytes(),
                        "source": "MinerU Extracted"
                    })
                except Exception:
                    pass

    return results


def ensure_markdown(parse_dir: Path, stem: str) -> None:
    md_path = parse_dir / f"{stem}.md"
    if md_path.exists():
        return
    middle_path = parse_dir / f"{stem}_middle.json"
    if not middle_path.exists():
        return

    try:
        from mineru.cli.client_side_output import regenerate_client_side_outputs
        regenerate_client_side_outputs(str(parse_dir), stem)
    except Exception as exc:
        try:
            code = (
                "from mineru.cli.client_side_output import regenerate_client_side_outputs; "
                f"regenerate_client_side_outputs(r'{parse_dir}', r'{stem}')"
            )
            subprocess.run(
                [VENV_PYTHON, "-c", code],
                capture_output=True,
                text=True,
                timeout=120,
                env=os.environ.copy(),
            )
        except Exception:
            pass


def run_mineru_cli(
    input_path: Path,
    output_dir: Path,
    backend: str,
    parse_method: str,
    max_pages: int,
    lang: str = "ch",
    formula: bool = True,
    table: bool = True,
    client_side_output: bool = True,
    output_callback: Optional[Any] = None,
) -> Optional[Dict[str, Any]]:
    stem = input_path.stem
    ext = get_file_ext(input_path.name)
    is_office = ext in OFFICE_EXTS
    is_image = ext in IMAGE_EXTS

    cmd = MINERU_CLI_PREFIX + [
        "-p", str(input_path),
        "-o", str(output_dir),
        "-b", backend,
    ]

    if not is_office and not is_image:
        cmd.extend(["-m", parse_method])

    if is_image:
        cmd.extend(["-m", "ocr"])

    if not is_office and not is_image:
        cmd.extend(["-l", lang])

    if ext == "pdf":
        cmd.extend(["-s", "0", "-e", str(max_pages - 1)])

    if not is_office:
        cmd.extend([
            "-f", "true" if formula else "false",
            "-t", "true" if table else "false",
        ])

    if client_side_output:
        cmd.extend(["--client-side-output-generation", "true"])

    log_status(f"CMD: {' '.join(cmd)}")

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        universal_newlines=True,
        env=os.environ.copy(),
    )

    output_lines = []
    try:
        for line in process.stdout:
            line = line.rstrip()
            if line:
                output_lines.append(line)
                if len(output_lines) > 300:
                    output_lines = output_lines[-300:]
                if output_callback is not None:
                    try:
                        output_callback(line)
                    except Exception:
                        pass
    except Exception:
        pass

    return_code = process.wait(timeout=1800)
    combined = "\n".join(output_lines[-50:])

    if return_code != 0:
        raise Exception(f"MinerU CLI exited with code {return_code}. Last output:\n{combined}")

    actual_parse_dir = find_parse_dir(output_dir, stem, backend, parse_method, is_office)

    if actual_parse_dir is None:
        log_status(f"WARN: could not find parse_dir, listing output_dir...")
        try:
            for p in sorted(output_dir.rglob("*")):
                log_status(f"  {p.relative_to(output_dir)}")
        except Exception:
            pass
        raise Exception(f"MinerU finished but no parse directory was found under {output_dir}")

    log_status(f"Found parse_dir: {actual_parse_dir}")

    ensure_markdown(actual_parse_dir, stem)

    return read_output_files(actual_parse_dir, stem)


def save_results_to_zip(results: Dict[str, Any], file_name: str) -> bytes:
    try:
        zip_buffer = io.BytesIO()
        stem = Path(file_name).stem

        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            # 1. Rendered Markdown / Output MD
            if results.get("markdown"):
                zf.writestr(f"{stem}_markdown_rendered.md", results["markdown"])
                zf.writestr(f"{stem}_markdown_text.txt", results["markdown"])

            # 2. Plain Extracted Text
            if results.get("text") and results.get("text") != results.get("markdown"):
                zf.writestr(f"{stem}_raw_text.txt", results["text"])

            # 3. JSON Content
            if results.get("json"):
                zf.writestr(
                    f"{stem}_content_list.json",
                    json.dumps(results["json"], indent=2, ensure_ascii=False)
                )

            # 4. QR Codes Data
            qr_codes = results.get("qr_codes", [])
            if qr_codes:
                zf.writestr(
                    f"{stem}_qr_codes.json",
                    json.dumps(qr_codes, indent=2, ensure_ascii=False)
                )

            # 5. Extracted Images & Figures
            image_list = results.get("image_bytes_list", [])
            for idx, img_item in enumerate(image_list, 1):
                img_name = img_item.get("name", f"extracted_image_{idx}.png")
                zf.writestr(f"extracted_images/{img_name}", img_item["bytes"])

            # 6. YOLO Layout Analysis Bounding Boxes & Crops
            yolo_data = results.get("yolo_crops", [])
            if yolo_data:
                yolo_summary = []
                for idx, crop_info in enumerate(yolo_data, 1):
                    cls_name = crop_info.get("class_name", "box")
                    box = crop_info.get("box", [])
                    yolo_summary.append({
                        "id": idx,
                        "class_name": cls_name,
                        "box_bbox_xywh": box,
                    })
                    crop_pil = crop_info.get("crop_pil")
                    if crop_pil:
                        img_byte_arr = io.BytesIO()
                        crop_pil.save(img_byte_arr, format='PNG')
                        zf.writestr(f"yolo_layout_analysis/crops/crop_{idx}_{cls_name}.png", img_byte_arr.getvalue())

                zf.writestr(
                    "yolo_layout_analysis/layout_boxes.json",
                    json.dumps(yolo_summary, indent=2, ensure_ascii=False)
                )

            # 7. Overall Metadata
            metadata = {
                "file_name": results.get("file_name"),
                "extraction_time": results.get("extraction_time"),
                "metadata": results.get("metadata", {})
            }
            zf.writestr(
                f"{stem}_metadata.json",
                json.dumps(metadata, indent=2, ensure_ascii=False)
            )

        zip_buffer.seek(0)
        return zip_buffer.getvalue()

    except Exception as e:
        st.error(f"ZIP Creation Error: {str(e)}")
        return None


# --- SIDEBAR: UPLOADED FILES & EXECUTION LOG ---
with st.sidebar:
    st.header("📁 Uploaded Files")
    if st.session_state.get("uploaded_files"):
        st.caption("Click any file button below to open preview in a new tab:")

        # Inject top-level JS function for opening previews in parent window safely
        st.components.v1.html("""
        <script>
        window.parent.openDocumentPreview = function(b64Data, mimeType, fileName) {
            var win = window.open('', '_blank');
            if (win) {
                var content = '';
                if (mimeType.startsWith('image/')) {
                    content = "<div style='background:#0f172a;min-height:100vh;display:flex;justify-content:center;align-items:center;margin:0;'><img src='data:" + mimeType + ";base64," + b64Data + "' style='max-width:100%;max-height:100vh;object-fit:contain;' /></div>";
                } else if (mimeType === 'application/pdf') {
                    content = "<iframe src='data:" + mimeType + ";base64," + b64Data + "' style='width:100%;height:100vh;border:none;'></iframe>";
                } else {
                    content = "<div style='background:#0f172a;color:white;padding:40px;font-family:sans-serif;'><h2>" + fileName + "</h2></div>";
                }
                win.document.write('<!DOCTYPE html><html><head><title>' + fileName + '</title><style>body{margin:0;overflow:hidden;}</style></head><body>' + content + '</body></html>');
                win.document.close();
            }
        };
        </script>
        """, height=0)

        for idx, f_item in enumerate(st.session_state.uploaded_files, 1):
            f_name = f_item.name
            f_ext = get_file_ext(f_name)
            f_bytes = f_item.getvalue()
            b64_data = base64.b64encode(f_bytes).decode('utf-8')
            mime_type = "application/pdf" if f_ext == "pdf" else (f"image/{f_ext}" if f_ext in ["png", "jpg", "jpeg"] else "application/octet-stream")

            # Native Streamlit button with direct onclick JS trigger in parent frame
            btn_key = f"sb_file_btn_{idx}_{f_name}"
            if st.button(f"📄 {idx}. {f_name} ↗️", key=btn_key, width='stretch'):
                st.components.v1.html(f"""
                <script>
                if (window.parent.openDocumentPreview) {{
                    window.parent.openDocumentPreview("{b64_data}", "{mime_type}", "{f_name}");
                }}
                </script>
                """, height=0)
    else:
        st.info("No documents uploaded yet")

    st.divider()

    st.header("📋 Status & Execution Log")
    status_container = st.container(height=350, border=True)
    with status_container:
        if st.session_state.status_log:
            for log_entry in st.session_state.status_log[-35:]:
                st.text(log_entry)
        else:
            st.info("Real-time execution status log will appear here during document parsing...")

    if st.button("Clear Log", width='stretch', key="sidebar_clear_log_btn"):
        st.session_state.status_log = []
        st.rerun()

    st.divider()
    with st.expander("🤖 Document AI Chat Assistant Settings", expanded=False):
        st.caption("Configure Document AI Chat Assistant & Optional Gemini API Key:")
        gemini_key_input = st.text_input(
            "Gemini API Key (Optional)",
            value=st.session_state.get("gemini_api_key", os.getenv("GEMINI_API_KEY", "")),
            type="password",
            help="Enter your Google Gemini API key for advanced conversational reasoning. If empty, the built-in offline IDP extraction engine will answer your questions.",
            key="gemini_api_key_sidebar_input"
        )
        if gemini_key_input != st.session_state.get("gemini_api_key"):
            st.session_state["gemini_api_key"] = gemini_key_input
        st.info("💡 **Tip:** The floating AI assistant widget at the bottom right allows you to ask questions about your uploaded documents at any time!")


st.title("Intelligent Document Processing")
st.markdown("Real-time document parsing with advanced OCR, QR detection & YOLO layout segmentation")



# --- TOP SECTION: CLEAN UPLOAD & PROCESS INTERFACE ---
# Set default backend parameters
backend = "pipeline"
parse_method = "auto"
formula_enable = True
table_enable = True
enable_yolo_preview = True
yolo_conf = 0.25
yolo_alpha = 0.40
max_pages = 200
lang = "ch"

# CSS: permanently hide the REAL st.file_uploader (in every state — empty, mid-drag, or
# with files already added) so it can never show its own default look, plus the styling
# for our own always-identical hero box and the custom "uploaded documents" chip list.
st.markdown("""
<style>
    /* Visually-hidden (but still fully functional) — kept in the layout, just invisible */
    div[data-testid="stFileUploader"] {
        position: absolute !important;
        width: 1px !important;
        height: 1px !important;
        padding: 0 !important;
        margin: -1px !important;
        overflow: hidden !important;
        opacity: 0 !important;
        pointer-events: none !important;
    }

    .upload-hero-container {
        border: 2px dashed #4F46E5;
        border-radius: 16px;
        background: linear-gradient(135deg, rgba(79, 70, 229, 0.05), rgba(6, 182, 212, 0.05));
        padding: 30px 20px;
        text-align: center;
        margin-bottom: 20px;
        transition: all 0.3s ease;
        cursor: pointer;
    }
    .upload-hero-container:hover {
        border-color: #6366F1;
        box-shadow: 0px 8px 24px rgba(99, 102, 241, 0.15);
    }
    .upload-hero-container.drag-over {
        border-color: #06B6D4;
        box-shadow: 0px 8px 28px rgba(6, 182, 212, 0.25);
    }
    .upload-title {
        font-size: 2rem;
        font-weight: 800;
        background: linear-gradient(90deg, #4F46E5, #06B6D4);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 8px;
    }
    .upload-subtitle {
        font-size: 1.05rem;
        color: #64748B;
        margin-bottom: 0;
    }

    .doc-chip-row {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        margin-bottom: 20px;
    }
    .doc-chip {
        display: flex;
        align-items: center;
        gap: 10px;
        background: #F1F5F9;
        border-radius: 10px;
        padding: 10px 14px;
        cursor: pointer;
        transition: background 0.2s ease;
    }
    .doc-chip:hover {
        background: #E2E8F0;
    }
    .doc-chip-icon {
        width: 32px;
        height: 32px;
        border-radius: 6px;
        background: #0F172A;
        color: #ffffff;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 11px;
        font-weight: 700;
    }
    .doc-chip-name {
        font-weight: 600;
        color: #1E293B;
        font-size: 0.9rem;
    }
    .doc-chip-size {
        color: #64748B;
        font-size: 0.78rem;
    }

    .doc-chip {
        position: relative;
    }

    .doc-chip-main {
        padding-right: 18px;
    }

    .doc-chip-remove {
        position: absolute;
        top: 4px;
        right: 5px;
        width: 16px;
        height: 16px;
        border: none;
        background: transparent;
        color: #64748B;
        font-size: 15px;
        line-height: 14px;
        padding: 0;
        margin: 0;
        cursor: pointer;
        border-radius: 50%;
    }

    .doc-chip-remove:hover {
        color: #EF4444;
        background: #E2E8F0;
    }

    [class*="st-key-remove_uploaded_file_"] {
        position: absolute !important;
        width: 1px !important;
        height: 1px !important;
        overflow: hidden !important;
        opacity: 0 !important;
        pointer-events: none !important;
        margin: 0 !important;
        padding: 0 !important;
    }
</style>
""", unsafe_allow_html=True)

# The one and only visible upload zone — purely decorative HTML that ALWAYS looks like
# this, whether zero files or several are already uploaded. Click or drag onto it and JS
# forwards the action to the real (invisible) st.file_uploader below.
st.markdown("""
<div class="upload-hero-container" id="upload-hero-box">
    <div class="upload-title">📄 UPLOAD DOCUMENTS</div>
    <div class="upload-subtitle">Drag and drop your PDF, DOCX, PPTX, XLSX, or Images here to start parsing instantly</div>
</div>
""", unsafe_allow_html=True)

# The real uploader — permanently invisible (see CSS above). Only exists to do the actual work.
uploaded_files = st.file_uploader(
    "UPLOAD DOCUMENTS",
    type=list(SUPPORTED_FORMATS.values()),
    accept_multiple_files=True,
    label_visibility="collapsed",
    key=f"main_doc_uploader_{st.session_state.uploader_version}"
)

# Wire the hero box to the hidden uploader: clicking it opens the file picker, and files can
# be dragged straight onto it. Both are forwarded to the real hidden <input type="file">.
st.components.v1.html("""
<script>
function wireHeroUploadBox() {
    const parentDoc = window.parent.document;
    const heroBox = parentDoc.getElementById('upload-hero-box');
    if (!heroBox) return;

    if (heroBox.dataset.wired === "true") return;
    heroBox.dataset.wired = "true";

    heroBox.onclick = function(e) {
        const fileInput = parentDoc.querySelector('div[data-testid="stFileUploader"] input[type="file"]');
        if (fileInput) {
            fileInput.click();
        }
    };

    heroBox.ondragover = function(e) {
        e.preventDefault();
        heroBox.classList.add('drag-over');
    };

    heroBox.ondragleave = function(e) {
        heroBox.classList.remove('drag-over');
    };

    heroBox.ondrop = function(e) {
        e.preventDefault();
        heroBox.classList.remove('drag-over');
        const dropped = e.dataTransfer.files;
        if (!dropped || dropped.length === 0) return;

        const fileInput = parentDoc.querySelector('div[data-testid="stFileUploader"] input[type="file"]');
        if (!fileInput) return;

        const dt = new DataTransfer();
        for (let i = 0; i < dropped.length; i++) {
            dt.items.add(dropped[i]);
        }
        fileInput.files = dt.files;
        fileInput.dispatchEvent(new Event('change', { bubbles: true }));
    };
}
setInterval(wireHeroUploadBox, 500);
</script>
""", height=0)

# Keep uploaded documents in our own session list so individual files can be removed
# without changing the appearance or behavior of the upload area.
if uploaded_files:
    existing = st.session_state.get("uploaded_files", [])
    existing_keys = {
        (f.name, len(f.getvalue()), hashlib.md5(f.getvalue()).hexdigest())
        for f in existing
    }
    for f_item in uploaded_files:
        file_key = (
            f_item.name,
            len(f_item.getvalue()),
            hashlib.md5(f_item.getvalue()).hexdigest()
        )
        if file_key not in existing_keys:
            existing.append(f_item)
            existing_keys.add(file_key)

    st.session_state.uploaded_files = existing
    if existing:
        st.session_state.uploaded_file = existing[0]

active_files = st.session_state.get("uploaded_files", [])

if active_files:
    # Our own "uploaded documents" list (not the hidden native uploader's own file list),
    # so it always looks the same and each item opens the document in a new tab instantly.
    file_data_map = {}
    chip_parts = ['<div class="doc-chip-row">']
    for idx, f_item in enumerate(active_files):
        f_ext = get_file_ext(f_item.name)
        f_bytes = f_item.getvalue()
        b64_data = base64.b64encode(f_bytes).decode('utf-8')
        mime_type = "application/pdf" if f_ext == "pdf" else f"image/{f_ext}"
        data_url = f"data:{mime_type};base64,{b64_data}"
        safe_name = html.escape(f_item.name)
        file_data_map[f_item.name] = data_url

        size_kb = len(f_bytes) / 1024
        size_label = f"{size_kb/1024:.1f}MB" if size_kb > 1024 else f"{size_kb:.1f}KB"
        chip_parts.append(
            f'<div class="doc-chip" data-fname="{safe_name}">'
            f'<div class="doc-chip-icon">{f_ext.upper()[:3]}</div>'
            f'<div class="doc-chip-main"><div class="doc-chip-name">{safe_name}</div>'
            f'<div class="doc-chip-size">{size_label}</div></div>'
            f'<button class="doc-chip-remove" data-remove-index="{idx}" '
            f'title="Remove {safe_name}" aria-label="Remove {safe_name}">×</button>'
            f'</div>'
        )
    chip_parts.append('</div>')
    chip_html = ''.join(chip_parts)
    st.markdown(chip_html, unsafe_allow_html=True)

    # Hidden Streamlit buttons provide the Python-side remove action.
    for idx, f_item in enumerate(active_files):
        if st.button(
            "Remove",
            key=f"remove_uploaded_file_{idx}",
            width="content"
        ):
            st.session_state.uploaded_files.pop(idx)
            st.session_state.extraction_results_dict.pop(f_item.name, None)

            if (
                st.session_state.extraction_results
                and st.session_state.extraction_results.get("file_name") == f_item.name
            ):
                st.session_state.extraction_results = None

            st.session_state.uploaded_file = (
                st.session_state.uploaded_files[0]
                if st.session_state.uploaded_files
                else None
            )
            st.session_state.uploader_version += 1
            st.rerun()

    js_map_json = json.dumps(file_data_map)
    st.components.v1.html(f"""
    <script>
    const fileDataMap = {js_map_json};

    function attachFileClickListeners() {{
        const parentDoc = window.parent.document;
        const chips = parentDoc.querySelectorAll('.doc-chip');

        chips.forEach(chip => {{
            if (chip.dataset.hasClickListener) return;

            const fname = chip.getAttribute('data-fname');
            const url = fileDataMap[fname];
            const removeButton = chip.querySelector('.doc-chip-remove');

            if (removeButton) {{
                removeButton.addEventListener('click', (event) => {{
                    event.preventDefault();
                    event.stopPropagation();

                    const index = Number(removeButton.getAttribute('data-remove-index'));
                    const targetButton = parentDoc.querySelector(
                        '.st-key-remove_uploaded_file_' + index + ' button'
                    );

                    if (targetButton) {{
                        targetButton.click();
                    }}
                }});
            }}

            if (url) {{
                chip.dataset.hasClickListener = "true";
                chip.title = "Click to open " + fname + " in new tab";
                chip.addEventListener('click', (event) => {{
                    if (event.target.closest('.doc-chip-remove')) return;

                    const win = window.open();
                    if (win) {{
                        win.document.write(
                            '<iframe src="' + url +
                            '" frameborder="0" style="border:0; top:0px; left:0px; bottom:0px; right:0px; width:100%; height:100%;" allowfullscreen></iframe>'
                        );
                        win.document.title = fname;
                    }}
                }});
            }}
        }});
    }}

    setInterval(attachFileClickListeners, 500);
    </script>
    """, height=0)

    col_btn1, col_btn2 = st.columns([2, 1])

    with col_btn1:
        convert_btn = st.button(
            "🚀 Convert & Process Documents",
            width='stretch',
            type="primary",
            key="convert_btn"
        )

    with col_btn2:
        clear_btn = st.button(
            "🗑️ Clear Files / Reset",
            width='stretch',
            key="clear_btn"
        )

    if clear_btn:
        clear_session()
        st.rerun()

    # --- REAL-TIME CONVERSION LOADING CONTAINER ---
    if convert_btn:
        uploaded_files = st.session_state.uploaded_files
        st.session_state.processing = True
        st.session_state.extraction_results_dict = {}

        loading_container = st.container(border=True)
        with loading_container:
            # 3D Spinning Document & Laser Scanning Animation
            anim_spot = st.empty()
            first_thumb = get_file_preview_thumbnail_b64(uploaded_files[0].getvalue(), uploaded_files[0].name) if uploaded_files else None
            anim_spot.markdown(
                get_document_scanning_animation_html(uploaded_files[0].name, 1, len(uploaded_files), preview_b64=first_thumb),
                unsafe_allow_html=True
            )

            overall_progress = st.progress(0.0, text=f"Processing 0 of {len(uploaded_files)} files...")
            live_output_spot = st.empty()

            t_start = datetime.now()

            for file_idx, f_item in enumerate(uploaded_files, 1):
                # Update animation with current file name and thumbnail
                curr_thumb = get_file_preview_thumbnail_b64(f_item.getvalue(), f_item.name)
                anim_spot.markdown(
                    get_document_scanning_animation_html(f_item.name, file_idx, len(uploaded_files), preview_b64=curr_thumb),
                    unsafe_allow_html=True
                )
                work_dir = tempfile.mkdtemp(prefix="mineru_app_")
                input_dir = Path(work_dir) / "input"
                output_dir = Path(work_dir) / "output"
                input_dir.mkdir(parents=True, exist_ok=True)
                output_dir.mkdir(parents=True, exist_ok=True)

                file_ext = get_file_ext(f_item.name)
                input_path = input_dir / f_item.name
                input_path.write_bytes(f_item.getvalue())

                effective_parse_method = parse_method
                if file_ext in IMAGE_EXTS:
                    effective_parse_method = "ocr"

                try:
                    log_status(f"[{file_idx}/{len(uploaded_files)}] Processing: {f_item.name}")

                    def update_live_status(line_text):
                        log_status(line_text)
                        elapsed_sec = (datetime.now() - t_start).total_seconds()
                        live_output_spot.info(f"⏱️ **Running Time:** `{elapsed_sec:.1f}s` | File {file_idx}/{len(uploaded_files)} (`{f_item.name}`)  \n`{line_text[:110]}`")

                    prog_val = (file_idx - 0.5) / len(uploaded_files)
                    overall_progress.progress(prog_val, text=f"File {file_idx}/{len(uploaded_files)}: Extracting {f_item.name}...")

                    results = run_mineru_cli(
                        input_path=input_path,
                        output_dir=output_dir,
                        backend=backend,
                        parse_method=effective_parse_method,
                        max_pages=max_pages,
                        lang=lang,
                        formula=formula_enable,
                        table=table_enable,
                        output_callback=update_live_status
                    )

                    if results is not None:
                        qr_codes = []
                        try:
                            if file_ext in IMAGE_EXTS:
                                qr_codes = decode_qr_from_image_bytes(input_path.read_bytes())
                            elif file_ext == "pdf":
                                qr_codes = extract_qr_from_pdf_bytes(input_path.read_bytes(), max_pages=max_pages)

                            for qr in qr_codes:
                                qr["details"] = fetch_qr_details(qr["content"])
                        except Exception:
                            pass

                        # Compute and store YOLO layout crops for download
                        try:
                            if file_ext in IMAGE_EXTS:
                                p_img = Image.open(input_path)
                                _, _, y_crops = safe_run_yolo_layout_analysis(p_img, conf_threshold=yolo_conf, alpha=yolo_alpha)
                                results["yolo_crops"] = y_crops
                            elif file_ext == "pdf":
                                import pypdfium2 as pdfium
                                pdf_doc = pdfium.PdfDocument(input_path.read_bytes())
                                if len(pdf_doc) > 0:
                                    p_img = pdf_doc[0].render(scale=1.2).to_pil()
                                    _, _, y_crops = safe_run_yolo_layout_analysis(p_img, conf_threshold=yolo_conf, alpha=yolo_alpha)
                                    results["yolo_crops"] = y_crops
                        except Exception:
                            pass

                        results["qr_codes"] = qr_codes
                        results["file_name"] = f_item.name
                        results["extraction_time"] = datetime.now().isoformat()

                        st.session_state.extraction_results_dict[f_item.name] = results
                        st.session_state.extraction_results = results

                except Exception as e:
                    log_status(f"Failed processing {f_item.name}: {str(e)}")
                    st.error(f"Error processing {f_item.name}: {str(e)}")
                finally:
                    try:
                        shutil.rmtree(work_dir, ignore_errors=True)
                    except Exception:
                        pass

            elapsed = (datetime.now() - t_start).total_seconds()
            overall_progress.progress(1.0, text=f"✅ All {len(uploaded_files)} Document(s) Converted in {elapsed:.1f}s!")

        if st.session_state.extraction_results_dict:
            st.success(f"🎉 Successfully processed {len(st.session_state.extraction_results_dict)} document(s) in {elapsed:.1f} seconds! Viewing results below.")
            st.rerun()
        else:
            st.error("Conversion did not return results. Check the Execution Log in the sidebar for details.")

# --- BOTTOM SECTION: EXTRACTION RESULTS (POPS UP AFTER PROCESSING / UPLOAD) ---
if st.session_state.extraction_results_dict:
    st.markdown('<div id="extraction-results-section"></div>', unsafe_allow_html=True)
    st.components.v1.html("""
    <script>
    setTimeout(function() {
        const parentDoc = window.parent.document;
        const target = parentDoc.getElementById('extraction-results-section');
        if (target) {
            target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    }, 200);
    </script>
    """, height=0)
    st.divider()
    st.subheader("Extraction Results")

if st.session_state.extraction_results_dict:
    if len(st.session_state.extraction_results_dict) > 1:
        selected_res_file = st.selectbox(
            "📄 Select Extracted Document to View Results:",
            options=list(st.session_state.extraction_results_dict.keys()),
            key="sel_result_file_dropdown"
        )
        results = st.session_state.extraction_results_dict[selected_res_file]
    else:
        results = list(st.session_state.extraction_results_dict.values())[0]

    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9 = st.tabs([
        "Markdown Rendering",
        "Markdown Text",
        "JSON Content",
        "Download",
        "QR Codes",
        "Layout Analysis (YOLO)",
        "Extracted Images",
        "Fraud Detection",
        "🤖 AI Chat Assistant"
    ])

    with tab1:
        st.markdown("""
        <style>
        .md-panel-box {
            height: 62vh;
            min-height: 460px;
            max-height: 720px;
            overflow-y: auto;
            padding: 14px 16px;
            border-radius: 10px;
            background: #fafafa;
        }

        .md-panel-box img {
            width: 100%;
            height: auto;
            display: block;
            border-radius: 8px;
        }

        .md-panel-caption {
            text-align: center;
            font-size: 12px;
            color: #6b7280;
            margin-top: 8px;
        }

        /* Unify heading weight/size with bold text so labels read consistently
           instead of some lines looking like giant headers and others plain bold. */
        .markdown-render :is(h1, h2, h3, h4, h5, h6) {
            font-size: 15px !important;
            font-weight: 700 !important;
            color: #111827 !important;
            margin: 14px 0 6px 0 !important;
            line-height: 1.4 !important;
        }

        .markdown-render h1 {
            font-size: 17px !important;
            margin-top: 4px !important;
        }

        .markdown-render p,
        .markdown-render li {
            font-size: 13.5px !important;
            line-height: 1.65 !important;
            color: #374151 !important;
            margin: 2px 0 10px 0 !important;
        }

        .markdown-render strong,
        .markdown-render b {
            font-weight: 700 !important;
            color: #111827 !important;
        }

        .markdown-render table {
            width: 100% !important;
            border-collapse: collapse !important;
            font-size: 13px !important;
            margin: 10px 0 !important;
        }

        .markdown-render td,
        .markdown-render th {
            border: 1px solid #e5e7eb !important;
            padding: 6px 8px !important;
            text-align: left !important;
        }
        </style>
        """, unsafe_allow_html=True)

        st.markdown("### 📄 Markdown Rendering & Page Split View")
        if results.get("markdown"):
            col_md_preview, col_md_render = st.columns([1, 1], gap="large")

            with col_md_preview:
                with st.container(border=True):
                    st.markdown("#### 🖼️ Document Page Preview")

                    preview_img = None
                    preview_caption = None

                    if st.session_state.uploaded_file is not None:
                        up_file = st.session_state.uploaded_file
                        f_ext = get_file_ext(up_file.name)

                        if f_ext == "pdf":
                            try:
                                import pypdfium2 as pdfium
                                up_file.seek(0)
                                pdf_doc = pdfium.PdfDocument(up_file.read())
                                total_p = len(pdf_doc)

                                if total_p > 0:
                                    if total_p > 1:
                                        sel_p = st.number_input(
                                            "Select Page Preview",
                                            min_value=1,
                                            max_value=total_p,
                                            value=1,
                                            step=1,
                                            key="tab1_md_page_select"
                                        )
                                    else:
                                        sel_p = 1

                                    page_obj = pdf_doc[sel_p - 1]
                                    preview_img = page_obj.render(scale=1.2).to_pil()
                                    preview_caption = f"Document Page {sel_p} of {total_p}"

                                up_file.seek(0)

                            except Exception as ex:
                                st.warning(f"Could not render page preview: {str(ex)}")

                        elif f_ext in ["png", "jpg", "jpeg"]:
                            up_file.seek(0)
                            preview_img = Image.open(up_file)
                            preview_caption = f"Document: {up_file.name}"
                            up_file.seek(0)

                        else:
                            st.info(f"Page preview available for PDF and Image files ({f_ext.upper()})")

                    else:
                        st.info("No active document preview available")

                    if preview_img is not None:
                        prev_buf = io.BytesIO()
                        preview_img.convert("RGB").save(prev_buf, format="PNG")
                        prev_b64 = base64.b64encode(prev_buf.getvalue()).decode()
                        cap_html = f'<div class="md-panel-caption">{html.escape(preview_caption)}</div>' if preview_caption else ""
                        st.markdown(
                            f'<div class="md-panel-box"><img src="data:image/png;base64,{prev_b64}" />{cap_html}</div>',
                            unsafe_allow_html=True
                        )

            with col_md_render:
                with st.container(border=True):
                    st.markdown("#### 📝 Extracted Rendered Output")

                    st.markdown(
                        f'<div class="md-panel-box markdown-render">{results["markdown"]}</div>',
                        unsafe_allow_html=True
                    )
        else:
            md_missing_hint = []
            if results.get("metadata", {}).get("_middle_json_exists"):
                md_missing_hint.append("_middle.json found but .md missing — client-side regeneration may have failed.")
            md_missing_hint.append("Try re-running with a different parse method (txt / auto / ocr) or backend.")
            st.warning("No markdown extracted.\n- " + "\n- ".join(md_missing_hint))

    with tab2:
        st.markdown("### Raw Markdown")
        if results.get("markdown"):
            st.code(results["markdown"], language="markdown")
        else:
            st.info("No markdown content extracted")

    with tab3:
        st.markdown("### JSON Content List")
        if results.get("json"):
            st.json(results["json"])
        else:
            st.info("No JSON content extracted")

    with tab4:
        st.markdown("### Download Results")
        if results.get("markdown") or results.get("json"):
            zip_data = save_results_to_zip(
                results,
                results.get("file_name", "document")
            )

            if zip_data:
                st.download_button(
                    label="Download as ZIP",
                    data=zip_data,
                    file_name=f"{Path(results.get('file_name', 'document')).stem}_extracted.zip",
                    mime="application/zip",
                    width='stretch'
                )

                st.divider()
                st.markdown("**Individual Files:**")

                col_dl1, col_dl2 = st.columns(2)

                with col_dl1:
                    if results.get("markdown"):
                        st.download_button(
                            label="Markdown",
                            data=results["markdown"],
                            file_name=f"{Path(results.get('file_name', 'document')).stem}.md",
                            mime="text/markdown",
                            width='stretch'
                        )

                with col_dl2:
                    if results.get("json"):
                        st.download_button(
                            label="JSON",
                            data=json.dumps(results["json"], indent=2, ensure_ascii=False),
                            file_name=f"{Path(results.get('file_name', 'document')).stem}.json",
                            mime="application/json",
                            width='stretch'
                        )
        else:
            st.info("No extraction results to download yet")

    with tab5:
        st.markdown("### Advanced QR Codes Detected")
        qr_codes = results.get("qr_codes", [])
        if qr_codes:
            st.success(f"Detected {len(qr_codes)} QR code(s) in document")
            for idx, qr in enumerate(qr_codes, 1):
                with st.container(border=True):
                    page_label = f" (Page {qr['page']})" if "page" in qr else ""
                    st.markdown(f"**QR Code #{idx}{page_label}** — Type: `{qr['type']}`")
                    
                    details = qr.get("details", {})
                    if details.get("detected_gstin"):
                        st.info(f"🆔 **Detected GSTIN:** `{details['detected_gstin']}`")
                    
                    st.code(qr["content"])
                    
                    if details.get("parsed_fields"):
                        st.markdown("**Parsed Fields:**")
                        st.json(details["parsed_fields"])
                    elif "details" in qr:
                        st.json(qr["details"])
        else:
            st.info("No QR codes detected in this document")

    with tab6:
        st.markdown("### YOLO Layout Analysis")
        selected_cls = None

        if st.session_state.uploaded_file is not None:
            up_file = st.session_state.uploaded_file
            f_ext = get_file_ext(up_file.name)
            try:
                if f_ext in ["png", "jpg", "jpeg"]:
                    up_file.seek(0)
                    p_img = Image.open(up_file)
                    y_img, cnts, crops = safe_run_yolo_layout_analysis(
                        p_img, conf_threshold=yolo_conf, alpha=yolo_alpha, selected_class=selected_cls
                    )

                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Paragraphs", cnts.get("paragraph", 0))
                    c2.metric("Text Blocks", cnts.get("text", 0))
                    c3.metric("Images", cnts.get("image", 0))
                    c4.metric("Tables", cnts.get("table", 0))

                    render_layout_box_inspector(y_img, crops, key_prefix="tab6_img")
                    up_file.seek(0)

                elif f_ext == "pdf":
                    import pypdfium2 as pdfium
                    up_file.seek(0)
                    pdf_doc = pdfium.PdfDocument(up_file.read())
                    total_p = len(pdf_doc)
                    if total_p > 0:
                        sel_page = st.number_input("Select Page to Analyze", min_value=1, max_value=total_p, value=1, step=1, key="tab6_pdf_page")
                        page_obj = pdf_doc[sel_page - 1]
                        p_img = page_obj.render(scale=1.2).to_pil()

                        with st.spinner("Analyzing document layout with YOLO..."):
                            y_img, cnts, crops = safe_run_yolo_layout_analysis(
                                p_img, conf_threshold=yolo_conf, alpha=yolo_alpha, selected_class=selected_cls
                            )

                        c1, c2, c3, c4 = st.columns(4)
                        c1.metric("Paragraphs", cnts.get("paragraph", 0))
                        c2.metric("Text Blocks", cnts.get("text", 0))
                        c3.metric("Images", cnts.get("image", 0))
                        c4.metric("Tables", cnts.get("table", 0))

                        render_layout_box_inspector(y_img, crops, key_prefix=f"tab6_pdf_p{sel_page}")

                    up_file.seek(0)

                else:
                    st.info("Layout analysis preview is available for PDF and Image documents.")
            except Exception as ex:
                st.warning(f"Could not render layout analysis: {str(ex)}")
        else:
            st.info("Upload a document to view YOLO layout segmentation")

    with tab7:
        st.markdown("### Extracted Document Images & Figures")
        image_list = results.get("image_bytes_list", [])

        if image_list:
            st.success(f"Extracted {len(image_list)} images from document")
            img_grid = st.columns(min(3, len(image_list)))
            for idx, img_item in enumerate(image_list):
                target_col = img_grid[idx % len(img_grid)]
                with target_col:
                    with st.container(border=True):
                        st.markdown(f"**Image #{idx+1}**: `{img_item['name']}`")
                        st.caption(f"Source: {img_item['source']}")
                        st.image(img_item["bytes"], width='stretch')
                        st.download_button(
                            label="Download Image",
                            data=img_item["bytes"],
                            file_name=img_item["name"],
                            mime="image/png",
                            width='stretch',
                            key=f"dl_img_{idx}"
                        )
        else:
            st.info("No standalone images detected or extracted in this document.")

    with tab8:
        st.markdown("### 🛡️ Explainable AI Invoice Fraud Detection")
        st.markdown("Automated risk scoring, rule validation & field-level visual fraud localization")

        try:
            p_img = None
            active_crops = []

            if st.session_state.uploaded_file is not None:
                up_file = st.session_state.uploaded_file
                f_ext = get_file_ext(up_file.name)

                if f_ext in ["png", "jpg", "jpeg"]:
                    up_file.seek(0)
                    p_img = Image.open(up_file)
                    up_file.seek(0)
                    active_crops = results.get("yolo_crops") or []
                    if not active_crops and p_img is not None:
                        _, _, active_crops = safe_run_yolo_layout_analysis(
                            p_img, conf_threshold=yolo_conf, alpha=yolo_alpha
                        )

                elif f_ext == "pdf":
                    import pypdfium2 as pdfium
                    up_file.seek(0)
                    pdf_doc = pdfium.PdfDocument(up_file.read())
                    total_p = len(pdf_doc)
                    if total_p > 0:
                        if total_p > 1:
                            sel_p = st.selectbox(
                                "📑 Select Page for Fraud Inspection:",
                                options=list(range(1, total_p + 1)),
                                format_func=lambda x: f"Page {x} of {total_p}",
                                key="tab8_fraud_pdf_page_selector"
                            )
                        else:
                            sel_p = 1
                        page_obj = pdf_doc[sel_p - 1]
                        p_img = page_obj.render(scale=1.4).to_pil()
                        # Extract layout crops for this specific PDF page
                        _, _, active_crops = safe_run_yolo_layout_analysis(
                            p_img, conf_threshold=yolo_conf, alpha=yolo_alpha
                        )
                    up_file.seek(0)

            # Run Deep Explainable Fraud Detection
            fraud_report = detect_invoice_fraud(results, yolo_crops=active_crops)
            verdict = fraud_report["verdict"]
            risk_score = fraud_report["risk_score"]
            status_color = fraud_report["status_color"]
            detected_issues = fraud_report["detected_issues"]
            field_table = fraud_report["field_analysis_table"]
            annotated_crops = fraud_report["annotated_crops"]

            col_preview, col_report = st.columns([1.1, 1.0], gap="large")

            # ----------------------------------------------------
            # LEFT SIDE: FULL ORIGINAL FILE PREVIEW WITH YOLO BOXES
            # ----------------------------------------------------
            with col_preview:
                with st.container(border=True):
                    st.markdown("#### 🖼️ Full Document Visual Inspection")
                    st.markdown(
                        "<div style='display:flex; gap:16px; margin-bottom:12px; font-size:13px; font-weight:600;'>"
                        "<span style='color:#10B981; background:rgba(16,185,129,0.12); padding:4px 8px; border-radius:6px;'>🟢 Normal Fields (Valid)</span>"
                        "<span style='color:#EF4444; background:rgba(239,68,68,0.12); padding:4px 8px; border-radius:6px;'>🔴 Flagged Fields (Suspicious / Fraud)</span>"
                        "</div>",
                        unsafe_allow_html=True
                    )

                    if p_img is not None:
                        annotated_fraud_img = draw_fraud_layout_overlay(p_img, annotated_crops)
                        buf = io.BytesIO()
                        annotated_fraud_img.convert("RGB").save(buf, format="PNG")
                        img_bytes = buf.getvalue()
                        b64_img = base64.b64encode(img_bytes).decode()
                        st.markdown(
                            f'<div style="max-height:700px; overflow-y:auto; border-radius:8px; background:#f8fafc; padding:8px; text-align:center; border:1px solid #e2e8f0;">'
                            f'<img src="data:image/png;base64,{b64_img}" style="width:100%; height:auto; border-radius:6px;" />'
                            f'</div>',
                            unsafe_allow_html=True
                        )
                        st.download_button(
                            label="📥 Download Annotated Fraud Overlay Image",
                            data=img_bytes,
                            file_name=f"fraud_inspection_{selected_res_file if 'selected_res_file' in locals() else 'invoice'}.png",
                            mime="image/png",
                            use_container_width=True,
                            key="dl_fraud_overlay_btn"
                        )
                    else:
                        st.info("Upload an image or PDF invoice to view visual bounding box overlay.")

            # ----------------------------------------------------
            # RIGHT SIDE: DETAILED FRAUD ANALYSIS PANEL
            # ----------------------------------------------------
            with col_report:
                with st.container(border=True):
                    st.markdown("#### 📊 Fraud Detection Report")

                    # Status Banner
                    badge_bg = "rgba(239, 68, 68, 0.12)" if verdict == "FAKE / HIGH RISK" else ("rgba(245, 158, 11, 0.12)" if verdict == "SUSPICIOUS" else "rgba(16, 185, 129, 0.12)")
                    badge_border = status_color
                    badge_icon = "🚨" if verdict == "FAKE / HIGH RISK" else ("⚠️" if verdict == "SUSPICIOUS" else "✅")

                    st.markdown(f"""
                    <div style="background:{badge_bg}; border:2px solid {badge_border}; border-radius:12px; padding:14px 18px; margin-bottom:16px;">
                        <div style="font-size:12px; font-weight:700; text-transform:uppercase; color:#64748B; letter-spacing:0.5px;">INVOICE VERDICT</div>
                        <div style="font-size:24px; font-weight:800; color:{status_color}; margin-top:2px;">{badge_icon} {verdict}</div>
                    </div>
                    """, unsafe_allow_html=True)

                    # Risk Score Bar
                    c_score1, c_score2 = st.columns([1, 2])
                    with c_score1:
                        st.metric("Risk Score", f"{risk_score}%")
                    with c_score2:
                        st.markdown("<div style='margin-top:14px;'>", unsafe_allow_html=True)
                        st.progress(risk_score / 100.0)
                        st.markdown("</div>", unsafe_allow_html=True)

                    st.divider()

                    # Detected Issues List
                    st.markdown("##### 🔍 Detected Issues")
                    if detected_issues:
                        for issue in detected_issues:
                            sev = issue.get("severity", "HIGH")
                            icon = "🔴" if sev in ["CRITICAL", "HIGH"] else "🟡"
                            with st.container(border=True):
                                st.markdown(f"**{icon} {issue['title']}**")
                                st.markdown(f"- **Field:** `{issue['field']}`")
                                if issue.get("value"):
                                    st.markdown(f"- **Value:** `{issue['value']}`")
                                st.markdown(f"- **Reason:** {issue['reason']}")
                    else:
                        st.success("✅ **No fraud indicators or suspicious anomalies detected.** All rule checks passed!")

                    st.divider()

                    # Field Analysis Table
                    st.markdown("##### 📋 Field Analysis Table")
                    if field_table:
                        table_rows = []
                        for row in field_table:
                            stt = row.get("status", "VALID")
                            stt_color = "#10B981" if stt == "VALID" else ("#EF4444" if stt == "FAILED" else ("#F59E0B" if stt == "SUSPICIOUS" else "#64748B"))
                            table_rows.append(
                                f"<tr>"
                                f"<td style='padding:8px 12px; font-weight:600;'>{html.escape(str(row['field']))}</td>"
                                f"<td style='padding:8px 12px;'><code>{html.escape(str(row['value']))}</code></td>"
                                f"<td style='padding:8px 12px; font-weight:700; color:{stt_color};'>{html.escape(stt)}</td>"
                                f"</tr>"
                            )
                        rows_html = "".join(table_rows)
                        st.markdown(f"""
                        <table style="width:100%; border-collapse:collapse; font-size:13px; background:#fafafa; border-radius:8px; overflow:hidden; border:1px solid #e2e8f0;">
                            <thead>
                                <tr style="background:#f1f5f9; text-align:left; border-bottom:1px solid #cbd5e1;">
                                    <th style="padding:8px 12px;">Field</th>
                                    <th style="padding:8px 12px;">Value</th>
                                    <th style="padding:8px 12px;">Status</th>
                                </tr>
                            </thead>
                            <tbody>
                                {rows_html}
                            </tbody>
                        </table>
                        """, unsafe_allow_html=True)

        except Exception as e:
            st.error(f"Error executing fraud detection: {str(e)}")

    with tab9:
        st.markdown("### 🤖 Document AI Chat Assistant")
        st.markdown("Ask natural language questions about your extracted invoice, PDF, or document.")

        if "chat_history" not in st.session_state:
            st.session_state.chat_history = []

        cur_doc_name = selected_res_file if 'selected_res_file' in locals() else list(st.session_state.extraction_results_dict.keys())[0]

        col_c_left, col_c_right = st.columns([1.8, 1.2], gap="large")

        with col_c_left:
            with st.container(border=True):
                st.markdown(f"#### 💬 Ask Questions About `{cur_doc_name}`")

                # Render chat history
                chat_box = st.container(height=380)
                with chat_box:
                    st.chat_message("assistant", avatar="🤖").markdown(
                        f"Hi **{_display_name}**! 👋 I'm **Reeva AI**, your Intelligent Document Processing Assistant. What would you like to know about `{cur_doc_name}`?"
                    )
                    for msg in st.session_state.chat_history:
                        avatar = "👤" if msg["role"] == "user" else "🤖"
                        st.chat_message(msg["role"], avatar=avatar).markdown(msg["text"])

                # Quick starter prompt buttons
                q_cols = st.columns(3)
                if q_cols[0].button("💰 Total & Tax", key="qbtn_total", width='stretch'):
                    prompt_q = "What is the total amount, subtotal, and tax in this document?"
                    st.session_state.chat_history.append({"role": "user", "text": prompt_q})
                    ans, _ = ask_document_ai(prompt_q, document_data=results, document_name=cur_doc_name, api_key=st.session_state.get("gemini_api_key", ""))
                    st.session_state.chat_history.append({"role": "assistant", "text": ans})
                    st.rerun()
                if q_cols[1].button("🔢 Invoice No & Date", key="qbtn_inv", width='stretch'):
                    prompt_q = "What is the invoice number, date, and due date?"
                    st.session_state.chat_history.append({"role": "user", "text": prompt_q})
                    ans, _ = ask_document_ai(prompt_q, document_data=results, document_name=cur_doc_name, api_key=st.session_state.get("gemini_api_key", ""))
                    st.session_state.chat_history.append({"role": "assistant", "text": ans})
                    st.rerun()
                if q_cols[2].button("🛡️ Fraud Check", key="qbtn_fraud", width='stretch'):
                    prompt_q = "Are there any fraud indicators, layout mismatches, or suspicious items?"
                    st.session_state.chat_history.append({"role": "user", "text": prompt_q})
                    ans, _ = ask_document_ai(prompt_q, document_data=results, document_name=cur_doc_name, api_key=st.session_state.get("gemini_api_key", ""))
                    st.session_state.chat_history.append({"role": "assistant", "text": ans})
                    st.rerun()

                # Chat input
                user_query = st.chat_input("Ask any question about this document...", key="tab9_chat_input")
                if user_query:
                    st.session_state.chat_history.append({"role": "user", "text": user_query})
                    ans, _ = ask_document_ai(user_query, document_data=results, document_name=cur_doc_name, api_key=st.session_state.get("gemini_api_key", ""))
                    st.session_state.chat_history.append({"role": "assistant", "text": ans})
                    st.rerun()

        with col_c_right:
            with st.container(border=True):
                st.markdown("#### 📋 Document Context Summary")
                st.markdown(f"• **Active File:** `{cur_doc_name}`")
                st.markdown(f"• **Extracted Content:** `{len(results.get('markdown', ''))}` chars")
                st.markdown(f"• **QR Codes:** `{len(results.get('qr_codes', []))}` detected")
                st.markdown(f"• **Layout Boxes:** `{len(results.get('yolo_crops', []))}` segments")

                if st.session_state.chat_history:
                    if st.button("🧹 Clear Conversation History", key="clear_chat_hist_btn", width='stretch'):
                        st.session_state.chat_history = []
                        st.rerun()

                st.divider()
                st.info("💡 **Voice & Floating Widget:** Click the glowing AI Chat bubble in the bottom right corner at any time to open the floating voice assistant!")


# --- FLOATING DOCUMENT AI CHAT ASSISTANT WIDGET (BOTTOM-RIGHT) ---
active_doc_data = None
active_doc_name = ""
if st.session_state.get("extraction_results_dict"):
    active_doc_name = selected_res_file if 'selected_res_file' in locals() else list(st.session_state.extraction_results_dict.keys())[0]
    active_doc_data = st.session_state.extraction_results_dict.get(active_doc_name)

st.components.v1.html(
    get_ai_chat_widget_html(
        document_data=active_doc_data,
        document_name=active_doc_name,
        user_name=_display_name,
        gemini_api_key=st.session_state.get("gemini_api_key", os.getenv("GEMINI_API_KEY", ""))
    ),
    height=0
)