import requests
import json
from datetime import datetime

# ==========================================
# 1. AYARLAR VE ENTEGRASYONLAR
# ==========================================
TELEGRAM_BOT_TOKEN = "8208251806:AAGN1N9VvcDK-CKHE63n3jHXvkRQ9H67ReU"
TELEGRAM_CHAT_ID = "1580732505"
LOKASYON = "İstanbul Havalimanı"
BIZIM_FIRMA = "Green Motion"  # Sistemde firmanın tam adı nasıl geçiyorsa buraya yaz (örn: "Metal Filo")

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
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 📱 PATRONA BİLDİRİM GİTTİ:\n{mesaj}\n")
        else:
            print(f"Bildirim hatası: {response.text}")
    except Exception as e:
        print(f"Bildirim gönderilemedi: {e}")

# ==========================================
# 3. YOLCU360 GERÇEK VERİ ÇEKME FONKSİYONU
# ==========================================
def piyasa_verilerini_cek():
    url = "https://api2.yolcu360.com/api/v1/search-api/search/point/"
    
    headers = {
        "authorization": "Bearer eyJhbGciOiJIUzUxMiIsInR5cCI6IkpXVCJ9.eyJvdCI6InlvbGN1MzYwIiwib3JnYW5pemF0aW9ucyI6WzY4MzZdLCJvcmdhbml6YXRpb24iOnsiaWQiOjY4MzYsIm5hbWUiOiJZb2xjdTM2MCIsInR5cGUiOiJ5b2xjdTM2MCJ9LCJhbm9uIjp0cnVlLCJpc3MiOiJ5b2xjdTM2MC5jb20iLCJzdWIiOiJhbi0wNTAwMTQ5Zi1lZmRjLTRkMzQtODI4MS03M2I5NzlkMGFmMzciLCJleHAiOjE3OTI4NDQ3OTQsImlhdCI6MTc5MjIzOTk5NCwianRpIjoiNDQxNTY4YjgtZjc4YS00MzQ2LWJhZDQtM2M4Y2NjYjRhMWQ5In0.mpei82MJtno_xPY4wXVL8RfDF_5KDR6qaKjD5Atiq7KgSBEdE0GLjH1RTnWH3KVtzmhyNAra4uWrFSLmJrWDRQ",
        "accept": "application/json",
        "content-type": "application/json",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36",
        "referer": "https://yolcu360.com/",
        "x-device-id": "1ebbc367-950e-409c-a302-dcbec17101f9"
    }

    payload = {
        "version": "v3",
        "checkInDateTime": "2026-10-18T10:00:00+03:00",
        "checkOutDateTime": "2026-10-21T10:00:00+03:00",
        "age": "30-65",
        "language": "tr",
        "currency": "TRY",
        "country": "TR",
        "paymentType": "creditCard",
        "organizationId": 6836,
        "checkInLocation": {"lat": 41.259656501755316, "lon": 28.74417437428462},
        "checkOutLocation": {"lat": 41.259656501755316, "lon": 28.74417437428462},
        "period": "daily",
        "radius": 5
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        veri = response.json()
        
        # Yolcu360 API yapısına göre araçları çekiyoruz
        araclar = veri.get("data", [])
        
        if not araclar:
            print("API'den araç listesi boş döndü. (Tarih geçmiş veya token süresi dolmuş olabilir)")
            return None
            
        bizim_fiyat = None
        rakip_fiyatlar = []

        for arac in araclar:
            # API yapısındaki firma adını ve fiyatı alıyoruz (Genel JSON yapısına uygun güvenli arama)
            firma_adi = arac.get("supplier", {}).get("name", "")
            fiyat = arac.get("price", {}).get("total", 0)
            
            if fiyat > 0:
                if BIZIM_FIRMA.lower() in firma_adi.lower():
                    # Bizim firmaya ait birden fazla araç olabilir, en ucuzunu baz alalım
                    if bizim_fiyat is None or fiyat < bizim_fiyat:
                        bizim_fiyat = fiyat
                else:
                    rakip_fiyatlar.append(fiyat)

        if not rakip_fiyatlar:
            rakip_min_fiyat = 0
        else:
            rakip_min_fiyat = min(rakip_fiyatlar)

        return {
            "bizim_fiyat": bizim_fiyat,
            "rakip_min_fiyat": rakip_min_fiyat,
            "toplam_arac": len(araclar)
        }
        
    except Exception as e:
        print(f"API bağlantısında hata oluştu: {e}")
        return None

# ==========================================
# 4. ANALİZ VE KARAR MOTORU
# ==========================================
def radar_analizi_yap():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 🔍 {LOKASYON} için gerçek Yolcu360 verileri taranıyor...")
    
    piyasa = piyasa_verilerini_cek()
    
    if not piyasa:
        print("Tarama yapılamadı, sistem kapanıyor.")
        return

    bizim_fiyat = piyasa["bizim_fiyat"]
    rakip_min = piyasa["rakip_min_fiyat"]
    
    print(f"Toplam listelenen araç: {piyasa['toplam_arac']}")
    
    if bizim_fiyat is None:
        mesaj = (
            f"⚠️ *STOK UYARISI - {LOKASYON}*\n\n"
            f"Şu an Yolcu360 üzerinde *{BIZIM_FIRMA}* firmasına ait müsait araç bulunmuyor!\n"
            f"Bölgedeki en ucuz rakip fiyatı: {rakip_min} TL."
        )
        patrona_bildirim_gonder(mesaj)
        return

    print(f"Bizim En Düşük Fiyatımız: {bizim_fiyat} TL | Rakip En Düşük: {rakip_min} TL")

    # KURAL: Bizim fiyatımız piyasadaki en düşük fiyattan %5'ten daha pahalıysa uyar
    if rakip_min > 0 and bizim_fiyat > (rakip_min * 1.05):
        fiyat_farki = bizim_fiyat - rakip_min
        
        mesaj = (
            f"⚠️ *REKABET UYARISI - {LOKASYON}*\n\n"
            f"Rakipler fiyat kırdı! Sizin en uygun aracınız *{bizim_fiyat} TL* iken, "
            f"pazardaki en düşük fiyat *{rakip_min} TL* seviyesine indi.\n\n"
            f"💡 *Aksiyon:* Rekabette kalmak ve üst sıralara çıkmak için fiyatınızı yaklaşık *{fiyat_farki} TL* indirmeyi değerlendirin."
        )
        patrona_bildirim_gonder(mesaj)
    else:
        print(f"✅ Fiyatınız rekabetçi ({bizim_fiyat} TL). Rakipler sizden ucuz değil. Bildirim atılmadı.")

# ==========================================
# 5. ÇALIŞTIRMA KOMUTU
# ==========================================
print("🚀 Araç Kiralama Radar Botu uyandı...")
radar_analizi_yap()
print("🏁 Tarama tamamlandı, sistem kapanıyor.")
