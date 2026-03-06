import streamlit as st
import requests
import json
import os
import time

from dotenv import load_dotenv
load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

st.title("Streamlit Manga Uploader")

uploaded_file = st.file_uploader("Upload JSON from Space", type="json")

def upload_page_to_telegram(page_path):
    url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
    with open(page_path, "rb") as img:
        r = requests.post(url, data={"chat_id": CHAT_ID}, files={"photo": img})
    time.sleep(0.5)
    return r.json()["result"]["photo"][-1]["file_id"]

if uploaded_file is not None:
    chapters = json.load(uploaded_file)
    for chapter in chapters:
        st.write(f"Uploading Chapter {chapter['chapter']} - {chapter['series']}")
        file_ids = []
        for page_path in chapter["pages"]:
            st.write(f"Uploading {page_path}")
            file_id = upload_page_to_telegram(page_path)
            file_ids.append(file_id)
        chapter["file_ids"] = file_ids
    st.success("All chapters uploaded to Telegram!")
