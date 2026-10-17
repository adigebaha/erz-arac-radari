import requests
from datetime import datetime
import random

# ==========================================
# 1. AYARLAR VE ENTEGRASYONLAR
# ==========================================
TELEGRAM_BOT_TOKEN = "8208251806:AAGN1N9VvcDK-CKHE63n3jHXvkRQ9H67ReU" 
TELEGRAM_CHAT_ID = "1580732505"  
LOKASYON = "İstanbul Havalimanı"

bizim_sube = {
    "segment": "B Segment (Ekonomi)",
    "guncel_fiyat": 1200,
    "guncel_sira": 2
}

# ==========================================
# 2. BİLDİRİM GÖNDERME FONKSİYONU
# ==========================================
def patrona_bildirim_gonder(mesaj):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": mesaj,
        "parse_mode": "Markdown"
    }
    
    try:
        # Gerçekten mesaj gitmesi için aşağıdaki satır aktif olmalı
        res = requests.post(url, json=payload)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 📱 PATRONA BİLDİRİM GİTTİ:\n{mesaj}\n")
    except Exception as e:
        print(f"Bildirim gönderilemedi: {e}")

# ==========================================
# 3. VERİ ÇEKME (SİMÜLASYON)
# ==========================================
def piyasa_verilerini_cek():
    senaryolar = ["fiyat_kirilmasi", "yuksek_talep", "stabil"]
    guncel_durum = random.choice(senaryolar)
    
    if guncel_durum == "fiyat_kirilmasi":
        return {"rakip_ort_fiyat": 1050, "rakip_min_fiyat": 950, "bolge_doluluk": 45, "bizim_yeni_siramiz": 4}
    elif guncel_durum == "yuksek_talep":
        return {"rakip_ort_fiyat": 1350, "rakip_min_fiyat": 1250, "bolge_doluluk": 92, "bizim_yeni_siramiz": 1}
    else:
        return {"rakip_ort_fiyat": 1180, "rakip_min_fiyat": 1150, "bolge_doluluk": 60, "bizim_yeni_siramiz": 2}

# ==========================================
# 4. ANALİZ VE KARAR MOTORU
# ==========================================
def radar_analizi_yap():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 🔍 Pazar taraması başlatıldı ({LOKASYON})...")
    piyasa = piyasa_verilerini_cek()
    
    if piyasa["bolge_doluluk"] >= 90:
        mesaj = (
            f"🚨 *FIRSAT UYARISI - {LOKASYON}*\n\n"
            f"Bölgedeki araç doluluğu *%{piyasa['bolge_doluluk']}* oranına ulaştı. Piyasada araç azalıyor.\n"
            f"💡 *Aksiyon:* {bizim_sube['segment']} fiyatlarınızı anında %15 artırabilirsiniz."
        )
        patrona_bildirim_gonder(mesaj)
        
    elif piyasa["bizim_yeni_siramiz"] > 3 and piyasa["rakip_min_fiyat"] < bizim_sube["guncel_fiyat"]:
        fiyat_farki = bizim_sube["guncel_fiyat"] - piyasa["rakip_min_fiyat"]
        oran = round((fiyat_farki / bizim_sube["guncel_fiyat"]) * 100)
        
        mesaj = (
            f"⚠️ *REKABET UYARISI - {LOKASYON}*\n\n"
            f"Rakipler {bizim_sube['segment']} araç fiyatını ortalama *%{oran}* kırdı.\n"
            f"Şu anki {bizim_sube['guncel_fiyat']} TL'lik ilanınız *{piyasa['bizim_yeni_siramiz']}. sıraya* düştü!\n"
            f"💡 *Aksiyon:* Rekabette kalmak için Obilet/Yolcu360 fiyatınızı {fiyat_farki} TL indirin."
        )
        patrona_bildirim_gonder(mesaj)
        
    else:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ Piyasa stabil, aksiyon gerektiren bir durum yok.\n")

# Kodu çalıştır ve işlemi bitir
print("🚀 Araç Kiralama Radar Botu uyandı ve çalışıyor...")
radar_analizi_yap()
print("🏁 Tarama tamamlandı, sistem kapanıyor.")
