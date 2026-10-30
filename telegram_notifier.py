import os
import requests
from typing import Optional

def send_telegram_message(message: str) -> bool:
    """
    Mengirim pesan teks ke Telegram menggunakan Bot API.
    Mengambil token dan chat_id dari environment variables GitHub Actions.
    """
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        print("⚠️ Telegram Token atau Chat ID belum dikonfigurasi.")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown"
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            print("✅ Pesan Telegram berhasil dikirim.")
            return True
        else:
            print(f"❌ Gagal mengirim pesan Telegram: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error koneksi ke Telegram API: {e}")
        return False
