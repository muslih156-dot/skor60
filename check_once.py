
import os
import requests
from datetime import datetime

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

def send_telegram(pesan):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("TOKEN/CHAT_ID belum di set")
        return False
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = {"chat_id": CHAT_ID, "text": pesan, "parse_mode": "HTML"}
        r = requests.post(url, data=data, timeout=10)
        print(f"Telegram status: {r.status_code}")
        return r.status_code == 200
    except Exception as e:
        print(f"Error: {e}")
        return False

def cek_menit_60():
    try:
        url = "https://api.sofascore.com/api/v1/sport/football/events/live"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        data = r.json()
        out = []
        for ev in data.get("events", []):
            minute = ev.get("time", {}).get("minute", 0)
            hs = ev.get("homeScore", {}).get("current", 0)
            aws = ev.get("awayScore", {}).get("current", 0)
            status = ev.get("status", {}).get("type")
            # REVISI FINAL: hanya menit 60 skor 0-0
            if status == "inprogress" and 59 <= minute <= 62 and hs == 0 and aws == 0:
                out.append({
                    "id": ev["id"],
                    "home": ev["homeTeam"]["name"],
                    "away": ev["awayTeam"]["name"],
                    "league": ev["tournament"]["name"],
                    "minute": minute
                })
        return out
    except Exception as e:
        print(f"Error cek: {e}")
        return []

def get_stats(event_id):
    try:
        url = f"https://api.sofascore.com/api/v1/event/{event_id}/statistics"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        data = r.json()
        stats = {}
        for g in data.get("statistics", []):
            for s in g.get("groups", []):
                for it in s.get("statisticsItems", []):
                    if it["name"] in ["Total shots", "Shots on target", "Dangerous attacks", "Expected goals"]:
                        stats[it["name"]] = {"home": it.get("homeValue", 0), "away": it.get("awayValue", 0)}
        return stats
    except:
        return {}

def analisa(stats):
    ts = int(stats.get("Total shots", {}).get("home", 0) or 0) + int(stats.get("Total shots", {}).get("away", 0) or 0)
    da = int(stats.get("Dangerous attacks", {}).get("home", 0) or 0) + int(stats.get("Dangerous attacks", {}).get("away", 0) or 0)
    sot = int(stats.get("Shots on target", {}).get("home", 0) or 0) + int(stats.get("Shots on target", {}).get("away", 0) or 0)
    if ts >= 12 and da >= 45 and sot >= 3:
        return f"AKTIF 🔥 Shots {ts} DA {da} SoT {sot}"
    elif ts <= 6 and da <= 25:
        return f"PASIF 🥶 Shots {ts} DA {da} SoT {sot}"
    else:
        return f"SEDANG 😐 Shots {ts} DA {da} SoT {sot}"

if __name__ == "__main__":
    print(f"Check menit 60 - {datetime.now()}")
    matches = cek_menit_60()
    print(f"Found {len(matches)} match")
    for m in matches:
        stats = get_stats(m["id"])
        analisa_text = analisa(stats)
        pesan = f"""⚽ <b>MENIT 60 - 0-0</b>

🏟️ {m['home']} vs {m['away']}
🏆 {m['league']}
⏱️ Menit {m['minute']}

📊 {analisa_text}

ID: {m['id']} | {datetime.now().strftime('%H:%M WITA')}"""
        send_telegram(pesan)
    print("Done")
