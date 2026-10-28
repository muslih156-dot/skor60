
import os
import requests
from flask import Flask
from datetime import datetime

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

ALREADY_SENT = set()

def send_telegram(pesan):
    """FIX: Return True/False biar gak hilang notif kalau gagal"""
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("TOKEN/CHAT_ID belum di set!")
        return False
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = {"chat_id": CHAT_ID, "text": pesan, "parse_mode": "HTML"}
        r = requests.post(url, data=data, timeout=10)
        if r.status_code == 200:
            print(f"[{datetime.now()}] Telegram OK")
            return True
        else:
            print(f"Telegram gagal: {r.text}")
            return False
    except Exception as e:
        print(f"Telegram error: {e}")
        return False

def cek_menit_60_00():
    """HANYA MENIT 60 SKOR 0-0"""
    try:
        url = "https://api.sofascore.com/api/v1/sport/football/events/live"
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=15)
        data = r.json()
        hasil = []
        for ev in data.get("events", []):
            status = ev.get("status", {}).get("type")
            minute = ev.get("time", {}).get("minute", 0)
            hs = ev.get("homeScore", {}).get("current", 0)
            aws = ev.get("awayScore", {}).get("current", 0)
            if status == "inprogress" and 59 <= minute <= 62 and hs == 0 and aws == 0:
                hasil.append({
                    "id": ev["id"],
                    "home": ev["homeTeam"]["name"],
                    "away": ev["awayTeam"]["name"],
                    "league": ev["tournament"]["name"],
                    "minute": minute,
                })
        return hasil
    except Exception as e:
        print(f"Error cek live: {e}")
        return []

def get_stats(event_id):
    try:
        url = f"https://api.sofascore.com/api/v1/event/{event_id}/statistics"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        data = r.json()
        stats = {}
        for group in data.get("statistics", []):
            for s in group.get("groups", []):
                for item in s.get("statisticsItems", []):
                    if item["name"] in ["Total shots", "Shots on target", "Dangerous attacks", "Expected goals"]:
                        stats[item["name"]] = {
                            "home": item.get("homeValue", 0),
                            "away": item.get("awayValue", 0),
                        }
        return stats
    except:
        return {}

def analisa_aktif_pasif(stats):
    total_shots = int(stats.get("Total shots", {}).get("home", 0) or 0) + int(stats.get("Total shots", {}).get("away", 0) or 0)
    da = int(stats.get("Dangerous attacks", {}).get("home", 0) or 0) + int(stats.get("Dangerous attacks", {}).get("away", 0) or 0)
    sot = int(stats.get("Shots on target", {}).get("home", 0) or 0) + int(stats.get("Shots on target", {}).get("away", 0) or 0)
    try:
        xg = float(stats.get("Expected goals", {}).get("home", 0) or 0) + float(stats.get("Expected goals", {}).get("away", 0) or 0)
    except:
        xg = 0
    if total_shots >= 12 and da >= 45 and sot >= 3:
        return f"AKTIF 🔥 (Shots {total_shots}, DA {da}, SoT {sot}, xG {xg:.2f})", True
    elif total_shots <= 6 and da <= 25:
        return f"PASIF 🥶 (Shots {total_shots}, DA {da}, SoT {sot}, xG {xg:.2f})", False
    else:
        return f"SEDANG 😐 (Shots {total_shots}, DA {da}, SoT {sot}, xG {xg:.2f})", None

def analisa_jebakan(match, stats):
    skor = 0
    alasan = []
    if any(x in match["league"] for x in ["India", "Egypt", "Kenya", "Friendly", "U19", "U21"]):
        alasan.append(f"Liga rawan {match['league']}")
        skor += 2
    total_shots = int(stats.get("Total shots", {}).get("home", 0) or 0) + int(stats.get("Total shots", {}).get("away", 0) or 0)
    sot = int(stats.get("Shots on target", {}).get("home", 0) or 0) + int(stats.get("Shots on target", {}).get("away", 0) or 0)
    if total_shots >= 14 and sot <= 2:
        alasan.append("Shot banyak tapi gak on target")
        skor += 2
    if skor >= 2:
        return f"YA ⚠️ JEBAKAN ({skor}/5) - {' | '.join(alasan)}", True
    return f"TIDAK ✅ AMAN ({skor}/5)", False

@app.route("/")
def home():
    return f"BOT MENIT 60 0-0 AKTIF ✅<br>Last: {datetime.now()} WITA<br>Gunakan /check untuk UptimeRobot"

@app.route("/check")
def check():
    matches = cek_menit_60_00()
    if not matches:
        return f"Tidak ada menit 60 0-0. Time: {datetime.now()}", 200

    sent = 0
    for m in matches:
        if m["id"] in ALREADY_SENT:
            continue
        stats = get_stats(m["id"])
        aktif_text, is_aktif = analisa_aktif_pasif(stats)
        jebakan_text, is_jebak = analisa_jebakan(m, stats)

        pesan = f"""⚽ <b>MENIT 60 - SKOR 0-0</b>

🏟️ {m['home']} vs {m['away']}
🏆 {m['league']}
⏱️ Menit: {m['minute']}

📊 {aktif_text}
🎭 {jebakan_text}

💡 {'SKIP - Jebakan' if is_jebak else 'GAS OVER 0.5' if is_aktif else 'SKIP - Pasif'}

ID: {m['id']} | {datetime.now().strftime('%H:%M WITA')}"""

        # FIX: Hanya tandai sudah dikirim kalau Telegram sukses
        if send_telegram(pesan):
            ALREADY_SENT.add(m["id"])
            sent += 1
        else:
            print(f"Gagal kirim {m['id']}, akan coba lagi next check")

    return f"Found {len(matches)}, sent {sent}", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
