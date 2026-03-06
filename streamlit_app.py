"""
Streamlit Cloud - واجهة رفع المانهوا لتيليغرام
- أوتوماتيكي: يتحقق من uploaded.json ويرفع الجديد فقط
- يدوي: تختار المانهوا والفصل وترفع
"""

import streamlit as st
import requests
import json
import time
from huggingface_hub import HfApi, hf_hub_download
from io import BytesIO
import os

# ─── إعدادات ────────────────────────────────────────────
HF_DATASET_REPO = os.environ.get("HF_DATASET_REPO", "your-username/your-dataset")
HF_TOKEN = os.environ.get("HF_TOKEN", "")
HF_SPACE_URL = os.environ.get("HF_SPACE_URL", "https://your-space.hf.space")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "-1003858166428")
UPLOADED_JSON = "uploaded.json"

api = HfApi(token=HF_TOKEN)

# ─── دوال مساعدة ────────────────────────────────────────

def load_uploaded() -> dict:
    """يحمّل uploaded.json من HuggingFace Dataset"""
    try:
        path = hf_hub_download(
            repo_id=HF_DATASET_REPO,
            filename=UPLOADED_JSON,
            repo_type="dataset",
            token=HF_TOKEN,
        )
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_uploaded(data: dict):
    """يحفظ uploaded.json على HuggingFace Dataset"""
    json_bytes = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    api.upload_file(
        path_or_fileobj=BytesIO(json_bytes),
        path_in_repo=UPLOADED_JSON,
        repo_id=HF_DATASET_REPO,
        repo_type="dataset",
        token=HF_TOKEN,
    )


def get_manhwa_list() -> list:
    """يجيب قائمة المانهوات من الـ API"""
    try:
        r = requests.get(f"{HF_SPACE_URL}/manhwa/list", timeout=30)
        return r.json().get("manhwa", [])
    except Exception as e:
        st.error(f"خطأ في الاتصال بالـ API: {e}")
        return []


def get_chapters(manhwa_name: str) -> list:
    """يجيب الفصول من الـ API"""
    try:
        r = requests.get(f"{HF_SPACE_URL}/manhwa/{manhwa_name}/chapters", timeout=60)
        return r.json().get("chapters", [])
    except Exception as e:
        st.error(f"خطأ في جلب الفصول: {e}")
        return []


def get_pages(manhwa_name: str, chapter_folder: str) -> list:
    """يجيب الصفحات من الـ API"""
    try:
        r = requests.get(
            f"{HF_SPACE_URL}/manhwa/{manhwa_name}/chapter/{chapter_folder}/pages",
            timeout=30
        )
        return r.json().get("pages", [])
    except Exception as e:
        st.error(f"خطأ في جلب الصفحات: {e}")
        return []


def send_photo_to_telegram(image_url: str) -> str | None:
    """يرسل صورة لتيليغرام ويرجع file_id"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
        r = requests.post(url, data={
            "chat_id": TELEGRAM_CHAT_ID,
            "photo": image_url,
        }, timeout=30)
        result = r.json()
        if result.get("ok"):
            photo = result["result"]["photo"]
            return photo[-1]["file_id"]  # أعلى جودة
    except Exception as e:
        st.warning(f"خطأ في إرسال الصورة: {e}")
    return None


def send_photo_bytes_to_telegram(image_bytes: bytes, filename: str) -> str | None:
    """يرسل صورة كـ bytes لتيليغرام ويرجع file_id"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
        r = requests.post(url, data={
            "chat_id": TELEGRAM_CHAT_ID,
        }, files={
            "photo": (filename, BytesIO(image_bytes)),
        }, timeout=60)
        result = r.json()
        if result.get("ok"):
            photo = result["result"]["photo"]
            return photo[-1]["file_id"]
    except Exception as e:
        st.warning(f"خطأ في إرسال الصورة: {e}")
    return None


def upload_chapter(manhwa_name: str, chapter: dict, uploaded_data: dict, progress_bar=None, status_text=None) -> dict:
    """يرفع فصل كامل لتيليغرام ويحفظ file_ids"""
    chapter_folder = chapter["folder"]
    pages = chapter["pages"]

    if manhwa_name not in uploaded_data:
        uploaded_data[manhwa_name] = {}

    if chapter_folder not in uploaded_data[manhwa_name]:
        uploaded_data[manhwa_name][chapter_folder] = {}

    file_ids = uploaded_data[manhwa_name][chapter_folder]
    total = len(pages)

    for i, page in enumerate(pages):
        if page in file_ids:
            continue  # تخطى المرفوع

        image_url = f"{HF_SPACE_URL}/manhwa/{manhwa_name}/chapter/{chapter_folder}/page/{page}"

        # حاول بالـ URL أولاً
        file_id = send_photo_to_telegram(image_url)

        # إذا فشل، حمّل الصورة وأرسلها كـ bytes
        if not file_id:
            try:
                r = requests.get(image_url, timeout=60)
                file_id = send_photo_bytes_to_telegram(r.content, page)
            except Exception:
                pass

        if file_id:
            file_ids[page] = file_id

        if progress_bar:
            progress_bar.progress((i + 1) / total)
        if status_text:
            status_text.text(f"📤 {chapter_folder} — {i+1}/{total}: {page}")

        time.sleep(0.5)  # تجنب rate limit

    uploaded_data[manhwa_name][chapter_folder] = file_ids
    return uploaded_data


# ─── واجهة Streamlit ─────────────────────────────────────

st.set_page_config(page_title="Manhwa Uploader", page_icon="📚", layout="wide")
st.title("📚 Manhwa Uploader")

tab_auto, tab_manual = st.tabs(["🤖 أوتوماتيكي", "✋ يدوي"])

# ══ تاب أوتوماتيكي ══════════════════════════════════════
with tab_auto:
    st.subheader("رفع تلقائي — يتخطى المرفوع ويرفع الجديد فقط")

    if st.button("🚀 ابدأ الرفع الأوتوماتيكي", type="primary"):
        uploaded_data = load_uploaded()
        manhwa_list = get_manhwa_list()

        if not manhwa_list:
            st.warning("لا توجد مانهوات في الـ Dataset")
        else:
            for manhwa_name in manhwa_list:
                st.markdown(f"### 📖 {manhwa_name}")
                chapters = get_chapters(manhwa_name)

                for chapter in chapters:
                    chapter_folder = chapter["folder"]
                    existing = uploaded_data.get(manhwa_name, {}).get(chapter_folder, {})
                    pages = chapter["pages"]

                    if len(existing) == len(pages) and len(pages) > 0:
                        st.success(f"✅ {chapter_folder} — مرفوع بالكامل ({len(pages)} صفحة)")
                        continue

                    st.info(f"🆕 {chapter_folder} — سيتم رفع {len(pages) - len(existing)} صفحة")
                    progress = st.progress(0)
                    status = st.empty()

                    uploaded_data = upload_chapter(manhwa_name, chapter, uploaded_data, progress, status)
                    save_uploaded(uploaded_data)
                    st.success(f"✅ {chapter_folder} — تم الرفع")

            st.balloons()
            st.success("🎉 انتهى الرفع الأوتوماتيكي!")

# ══ تاب يدوي ════════════════════════════════════════════
with tab_manual:
    st.subheader("رفع يدوي — اختر المانهوا والفصل")

    manhwa_list = get_manhwa_list()

    if not manhwa_list:
        st.warning("لا توجد مانهوات")
    else:
        selected_manhwa = st.selectbox("اختر المانهوا", manhwa_list)

        if selected_manhwa:
            chapters = get_chapters(selected_manhwa)
            chapter_names = [c["folder"] for c in chapters]
            selected_chapter_name = st.selectbox("اختر الفصل", chapter_names)

            selected_chapter = next((c for c in chapters if c["folder"] == selected_chapter_name), None)

            if selected_chapter and st.button("📤 رفع الفصل", type="primary"):
                uploaded_data = load_uploaded()
                progress = st.progress(0)
                status = st.empty()

                uploaded_data = upload_chapter(selected_manhwa, selected_chapter, uploaded_data, progress, status)
                save_uploaded(uploaded_data)

                file_ids = uploaded_data.get(selected_manhwa, {}).get(selected_chapter_name, {})
                st.success(f"✅ تم رفع {len(file_ids)} صفحة!")
                st.json(file_ids)
