import time
import requests
import schedule
from datetime import datetime
import random # Sadece piyasa verisini simüle etmek için

# ==========================================
# 1. AYARLAR VE ENTEGRASYONLAR
# ==========================================
# Telegram üzerinden patrona bildirim atmak için gerekli bilgiler
TELEGRAM_BOT_TOKEN = "8208251806:AAGN1N9VvcDK-CKHE63n3jHXvkRQ9H67ReU"
TELEGRAM_CHAT_ID = "1580732505"
LOKASYON = "İstanbul Havalimanı"

# Şubemizin veritabanından çekilen anlık durumu
bizim_sube = {
    "segment": "B Segment (Ekonomi)",
    "guncel_fiyat": 1200, # TL
    "guncel_sira": 2
}

# ==========================================
# 2. BİLDİRİM GÖNDERME FONKSİYONU
# ==========================================
def patrona_bildirim_gonder(mesaj):
    """Telegram API kullanarak patronun telefonuna anlık push bildirim gönderir."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": mesaj,
        "parse_mode": "Markdown"
    }
    
    try:
        # requests.post(url, json=payload) # Gerçek kullanımda buradaki yorum satırı kaldırılır
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 📱 PATRONA BİLDİRİM GİTTİ:\n{mesaj}\n")
    except Exception as e:
        print(f"Bildirim gönderilemedi: {e}")

# ==========================================
# 3. VERİ ÇEKME (SCRAPING) SİMÜLASYONU
# ==========================================
def piyasa_verilerini_cek():
    """
    Gerçek senaryoda burada BeautifulSoup veya Selenium ile 
    Yolcu360/Obilet gibi sitelerden anlık fiyatlar kazınır (scrape edilir).
    """
    # Örnek senaryoları test etmek için rastgele piyasa durumları oluşturuyoruz
    senaryolar = ["fiyat_kirilmasi", "yuksek_talep", "stabil"]
    guncel_durum = random.choice(senaryolar)
    
    if guncel_durum == "fiyat_kirilmasi":
        return {"rakip_ort_fiyat": 1050, "rakip_min_fiyat": 950, "bolge_doluluk": 45, "bizim_yeni_siramiz": 4}
    elif guncel_durum == "yuksek_talep":
        return {"rakip_ort_fiyat": 1350, "rakip_min_fiyat": 1250, "bolge_doluluk": 92, "bizim_yeni_siramiz": 1}
    else:
        return {"rakip_ort_fiyat": 1180, "rakip_min_fiyat": 1150, "bolge_doluluk": 60, "bizim_yeni_siramiz": 2}

# ==========================================
# 4. ANALİZ VE KARAR MOTORU (SAATLİK ÇALIŞAN ANA BLOK)
# ==========================================
def radar_analizi_yap():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 🔍 Pazar taraması başlatıldı ({LOKASYON})...")
    
    piyasa = piyasa_verilerini_cek()
    
    # KURAL 1: Yüksek Talep ve Doluluk Fırsatı
    if piyasa["bolge_doluluk"] >= 90:
        mesaj = (
            f"🚨 *FIRSAT UYARISI - {LOKASYON}*\n\n"
            f"Bölgedeki araç doluluğu *%{piyasa['bolge_doluluk']}* oranına ulaştı. Piyasada araç azalıyor.\n"
            f"💡 *Aksiyon:* {bizim_sube['segment']} fiyatlarınızı anında %15 artırabilirsiniz."
        )
        patrona_bildirim_gonder(mesaj)
        
    # KURAL 2: Rakiplerin Fiyat Kırması ve Sıra Kaybı
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

# ==========================================
# 5. SAATLİK ZAMANLAYICI (SCHEDULER)
# ==========================================
# Her saat başı 00 geçe çalışacak şekilde ayarlanır. (Şu an test için her 10 saniyede bir çalışır)
# schedule.every().hour.do(radar_analizi_yap) # Gerçek senaryo
schedule.every(10).seconds.do(radar_analizi_yap) # Test senaryosu

print("🚀 Araç Kiralama Radar Botu başlatıldı. Arka planda çalışıyor...")
radar_analizi_yap() # İlk taramayı hemen yap

# Arka planda sonsuz döngüde bekleme
while True:
    schedule.run_pending()
    time.sleep(1)
