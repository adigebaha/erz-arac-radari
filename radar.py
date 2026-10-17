import requests
import json
import re
from datetime import datetime, timedelta
import time
import os

# ==========================================
# 1. AYARLAR VE ENTEGRASYONLAR
# ==========================================
TELEGRAM_BOT_TOKEN = "8208251806:AAGN1N9VvcDK-CKHE63n3jHXvkRQ9H67ReU"
TELEGRAM_CHAT_ID = "1580732505"
LOKASYON = "İstanbul Havalimanı"
BIZIM_FIRMA = "Green Motion"

YOLCU360_TOKEN = "eyJhbGciOiJIUzUxMiIsInR5cCI6IkpXVCJ9.eyJvdCI6InlvbGN1MzYwIiwib3JnYW5pemF0aW9ucyI6WzY4MzZdLCJvcmdhbml6YXRpb24iOnsiaWQiOjY4MzYsIm5hbWUiOiJZb2xjdTM2MCIsInR5cGUiOiJ5b2xjdTM2MCJ9LCJhbm9uIjp0cnVlLCJpc3MiOiJ5b2xjdTM2MC5jb20iLCJzdWIiOiJhbi0wNTAwMTQ5Zi1lZmRjLTRkMzQtODI4MS03M2I5NzlkMGFmMzciLCJleHAiOjE3OTI4NDQ3OTQsImlhdCI6MTc5MjIzOTk5NCwianRpIjoiNDQxNTY4YjgtZjc4YS00MzQ2LWJhZDQtM2M4Y2NjYjRhMWQ5In0.mpei82MJtno_xPY4wXVL8RfDF_5KDR6qaKjD5Atiq7KgSBEdE0GLjH1RTnWH3KVtzmhyNAra4uWrFSLmJrWDRQ"
YOLCU360_DEVICE_ID = "1ebbc367-950e-409c-a302-dcbec17101f9"

# Hata ayıklama: True ise her taramada yanıtın yapısı konsola yazılır
DEBUG = True


# ==========================================
# 2. BİLDİRİM GÖNDERME FONKSİYONU
# ==========================================
def patrona_bildirim_gonder(mesaj, markdown=True):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": mesaj}
    if markdown:
        payload["parse_mode"] = "Markdown"

    try:
        response = requests.post(url, json=payload, timeout=30)
        if response.status_code == 200:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 📱 BİLDİRİM GÖNDERİLDİ")
        elif markdown:
            # Markdown ayrıştırma hatası olabilir; düz metin olarak tekrar dene
            print(f"Markdown ile gönderilemedi ({response.status_code}), düz metin deneniyor...")
            patrona_bildirim_gonder(mesaj.replace("*", ""), markdown=False)
        else:
            print(f"Bildirim hatası: {response.text}")
    except Exception as e:
        print(f"Bildirim gönderilemedi: {e}")


# ==========================================
# 3. YOLCU360 VERİ ÇEKME FONKSİYONU
# ==========================================
def _arac_listesi_bul(veri):
    """Yanıt yapısı değişse bile araç listesini bulmaya çalışır."""
    if isinstance(veri, list):
        return veri
    if isinstance(veri, dict):
        anahtarlar = ("data", "results", "vehicles", "items", "cars", "list")
        for k in anahtarlar:
            v = veri.get(k)
            if isinstance(v, list):
                return v
            if isinstance(v, dict):
                for alt in anahtarlar:
                    if isinstance(v.get(alt), list):
                        return v[alt]
    return None


# Yolcu360 tutarları kuruş cinsinden döner (örn. 806072 = 8.060,72 TL).
# Yolcu360 sitesinde aynı aramadaki fiyatla karşılaştırıp doğrulayın.
FIYAT_BOLEN = 100

FIRMA_ANAHTARLARI = ("supplier", "vendor", "company", "provider", "rentalCompany", "agency", "partner")


def _normalize(metin):
    """Karşılaştırma için: Türkçe karakterleri sadeleştir, küçük harfe çevir, harf/rakam dışını at."""
    tablo = str.maketrans("ıİğĞüÜşŞöÖçÇ", "iigguussoocc")
    s = str(metin).translate(tablo).lower()
    return "".join(ch for ch in s if ch.isalnum())


def _firma_adaylari(arac):
    """Aracın hangi firmaya ait olduğunu gösteren tüm ipuçlarını döndürür."""
    adaylar = []

    def isim(v):
        if isinstance(v, dict):
            v = v.get("name") or v.get("title")
        return str(v) if v else None

    # 1) Doğrudan alanlar (eski/olası yapı)
    for k in FIRMA_ANAHTARLARI:
        n = isim(arac.get(k))
        if n:
            adaylar.append(n)

    # 2) integration.code (base64) içindeki hookName, örn. "avis"
    ent = arac.get("integration")
    if isinstance(ent, dict) and ent.get("code"):
        cozulmus = _b64_coz(ent["code"]) or ""
        m = re.search(r'"hookName"\s*:\s*"([^"]+)"', cozulmus)
        if m:
            adaylar.append(m.group(1))

    # 3) details içinde firma bilgisi taşıyan alanlar (ofis bilgileri hariç)
    def tara(obj, derinlik=0):
        if derinlik > 5:
            return
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k in ("appointment", "openingHours", "phones"):
                    continue
                if k in FIRMA_ANAHTARLARI:
                    n = isim(v)
                    if n:
                        adaylar.append(n)
                tara(v, derinlik + 1)
        elif isinstance(obj, list):
            for v in obj[:5]:
                tara(v, derinlik + 1)

    tara(arac.get("details"))
    return list(dict.fromkeys(adaylar))  # tekrarları at, sırayı koru


def _firma_adi(arac):
    return " | ".join(_firma_adaylari(arac))


def _bizim_mi(adaylar):
    hedef = _normalize(BIZIM_FIRMA)
    return any(hedef in _normalize(a) for a in adaylar)


def _tutar_oku(obj, *yol):
    for k in yol:
        if not isinstance(obj, dict):
            return None
        obj = obj.get(k)
    return obj


def _fiyat(arac):
    """Müşterinin ödeyeceği toplam tutarı TL olarak döndürür; okunamazsa 0."""
    # Güncel yapı: tutarlar kuruş cinsinden
    for yol in (("pricing", "display", "paymentTotal", "amount", "amount"),
                ("pricing", "display", "preDiscountTotal", "amount", "amount"),
                ("pricing", "display", "net", "amount", "amount")):
        try:
            v = float(_tutar_oku(arac, *yol))
        except (TypeError, ValueError):
            continue
        if v > 0:
            return v / FIYAT_BOLEN

    # Eski yapı (yedek)
    fiyat = arac.get("price")
    if isinstance(fiyat, dict):
        for k in ("total", "totalPrice", "amount", "value"):
            if fiyat.get(k) is not None:
                fiyat = fiyat[k]
                break
        else:
            return 0.0
    if fiyat is None:
        fiyat = arac.get("totalPrice") or arac.get("total") or 0
    try:
        # "1.234,56" / "1234.56" / 1234 hepsini kabul et
        if isinstance(fiyat, str):
            fiyat = fiyat.replace("TL", "").replace("₺", "").strip()
            if "," in fiyat:
                fiyat = fiyat.replace(".", "").replace(",", ".")
        return float(fiyat)
    except (TypeError, ValueError):
        return 0.0


ATLANACAK_ANAHTARLAR = {"searchRequest", "searchRequestV2", "posAliases", "campaignID",
                        "cmsKey", "searchAlgorithm", "searchAssignment", "searchID",
                        # Ofis adresi/saat/telefon gibi gürültü (fiyatla ilgisi yok)
                        "appointment", "openingHours", "phones", "rating", "images"}


def _b64_coz(metin):
    """Base64 (urlsafe veya normal) metni çözüp okunabilir kısmını döndürür."""
    import base64
    try:
        s = str(metin)
        s += "=" * (-len(s) % 4)
        return base64.urlsafe_b64decode(s).decode("utf-8", errors="replace")
    except Exception:
        return None


def _yapi_ozeti(obj, yol="", derinlik=0, satirlar=None):
    """Bir JSON nesnesini 'yol = değer' satırlarına düzleştirir (tanı amaçlı)."""
    if satirlar is None:
        satirlar = []
    if derinlik > 7:
        satirlar.append(f"{yol} = ...")
        return satirlar
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in ATLANACAK_ANAHTARLAR:
                continue
            _yapi_ozeti(v, f"{yol}.{k}" if yol else str(k), derinlik + 1, satirlar)
    elif isinstance(obj, list):
        if not obj:
            satirlar.append(f"{yol} = []")
        for i, v in enumerate(obj[:2]):
            _yapi_ozeti(v, f"{yol}[{i}]", derinlik + 1, satirlar)
        if len(obj) > 2:
            satirlar.append(f"{yol} = (+{len(obj) - 2} eleman daha)")
    else:
        satirlar.append(f"{yol} = {str(obj)[:60]}")
    return satirlar


def piyasa_verilerini_cek():
    """(sonuç, hata) döndürür. Başarılıysa hata None, başarısızsa sonuç None olur."""
    url = "https://api2.yolcu360.com/api/v1/search-api/search/point/"

    headers = {
        "authorization": f"Bearer {YOLCU360_TOKEN}",
        "accept": "application/json",
        "content-type": "application/json",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36",
        "referer": "https://yolcu360.com/",
        "x-device-id": YOLCU360_DEVICE_ID,
        "accept-language": "tr",
        "content-language": "tr",
    }

    yarin = datetime.now() + timedelta(days=1)
    cikis = yarin + timedelta(days=3)

    payload = {
        "version": "v3",
        "checkInDateTime": yarin.strftime("%Y-%m-%dT10:00:00+03:00"),
        "checkOutDateTime": cikis.strftime("%Y-%m-%dT10:00:00+03:00"),
        "age": "30-65",
        "language": "tr",
        "currency": "TRY",
        "country": "TR",
        "paymentType": "creditCard",
        "organizationId": 6836,
        "checkInLocation": {"lat": 41.259656501755316, "lon": 28.74417437428462},
        "checkOutLocation": {"lat": 41.259656501755316, "lon": 28.74417437428462},
        "period": "daily",
        "radius": 5,
    }

    # --- İstek ---
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
    except requests.exceptions.Timeout:
        return None, "Yolcu360 30 sn içinde yanıt vermedi (zaman aşımı)."
    except requests.exceptions.RequestException as e:
        return None, f"Yolcu360'a bağlanılamadı: {type(e).__name__}: {str(e)[:200]}"

    govde_ozet = response.text[:300].replace("\n", " ")

    # --- HTTP durumu ---
    if response.status_code != 200:
        print(f"\n❌ YOLCU360 API HATASI: HTTP {response.status_code}\nDetay: {response.text[:500]}\n")
        ipucu = {
            401: "Token reddedildi (süresi dolmuş veya geçersiz).",
            403: "Erişim engellendi (bot koruması/WAF olabilir; token değil, istek imzası sorunu).",
            404: "Adres bulunamadı (API yolu değişmiş olabilir).",
            422: "İstek gövdesi reddedildi (alan formatı değişmiş olabilir).",
            429: "Çok fazla istek (rate limit).",
        }.get(response.status_code, "Beklenmeyen sunucu yanıtı.")
        return None, f"HTTP {response.status_code} — {ipucu}\nYanıt: {govde_ozet}"

    # --- JSON ---
    try:
        veri = response.json()
    except ValueError:
        return None, f"HTTP 200 geldi ama yanıt JSON değil (content-type: {response.headers.get('content-type')}).\nYanıt: {govde_ozet}"

    if DEBUG:
        anahtarlar = list(veri.keys()) if isinstance(veri, dict) else type(veri).__name__
        print(f"[DEBUG] Yanıt üst anahtarları: {anahtarlar}")

    araclar = _arac_listesi_bul(veri)
    if araclar is None:
        anahtarlar = list(veri.keys()) if isinstance(veri, dict) else type(veri).__name__
        return None, f"Yanıtta araç listesi bulunamadı. Üst anahtarlar: {anahtarlar}\nYanıt: {govde_ozet}"

    if not araclar:
        return None, f"Arama başarılı ama {payload['checkInDateTime'][:10]} tarihi için hiç araç dönmedi."

    if DEBUG and isinstance(araclar[0], dict):
        print(f"[DEBUG] İlk araç anahtarları: {list(araclar[0].keys())}")

    # --- Fiyat analizi ---
    bizim_fiyat = None
    rakipler = []   # (fiyat, firma)
    firmalar = {}   # firma -> en düşük fiyat

    for arac in araclar:
        if not isinstance(arac, dict):
            continue
        adaylar = _firma_adaylari(arac)
        firma = " | ".join(adaylar)
        fiyat = _fiyat(arac)

        if fiyat > 0:
            firmalar[firma] = min(fiyat, firmalar.get(firma, fiyat))
            if _bizim_mi(adaylar):
                if bizim_fiyat is None or fiyat < bizim_fiyat:
                    bizim_fiyat = fiyat
            else:
                rakipler.append((fiyat, firma))

    if bizim_fiyat is None and not rakipler:
        ornek = araclar[0] if isinstance(araclar[0], dict) else {}
        # Tam örneği dosyaya da kaydet (scriptin çalıştığı klasöre)
        try:
            with open("yolcu360_ornek_yanit.json", "w", encoding="utf-8") as f:
                json.dump(araclar[:2], f, ensure_ascii=False, indent=2)
            print("[TANI] İlk 2 aracın tam yanıtı yolcu360_ornek_yanit.json dosyasına yazıldı.")
        except Exception as e:
            print(f"[TANI] Örnek dosya yazılamadı: {e}")
        # pricing en başa; ardından geri kalan alanlar
        satirlar = _yapi_ozeti({k: ornek[k] for k in ("pricing",) if k in ornek})
        satirlar += _yapi_ozeti({k: v for k, v in ornek.items() if k != "pricing"})

        # Şifreli görünen kod alanlarını çöz (firma/ürün bilgisi taşıyor olabilir)
        entegrasyon = ornek.get("integration")
        if isinstance(entegrasyon, dict) and entegrasyon.get("code"):
            satirlar.append(f"[çözülmüş] integration.code = {(_b64_coz(entegrasyon['code']) or '')[:250]}")
        if ornek.get("code"):
            satirlar.append(f"[çözülmüş] code = {(_b64_coz(ornek['code']) or '')[:250]}")

        ozet = "\n".join(satirlar)
        print("[TANI] İlk aracın yapısı:\n" + ozet)
        return None, (f"{len(araclar)} araç döndü ama fiyat okunamadı (yanıt formatı değişmiş).\n"
                      f"İlk aracın yapı özeti:\n{ozet[:2800]}")

    rakip_min, rakip_firma = min(rakipler) if rakipler else (0, "")

    if DEBUG:
        print("[DEBUG] Firma bazında en düşük fiyatlar (TL):")
        for f, p in sorted(firmalar.items(), key=lambda x: x[1]):
            print(f"   {p:>10,.0f}  {f}")

    return {
        "bizim_fiyat": bizim_fiyat,
        "rakip_min_fiyat": rakip_min,
        "rakip_min_firma": rakip_firma,
        "toplam_arac": len(araclar),
        "firmalar": sorted(f for f in firmalar if f),
    }, None


# ==========================================
# 4. ANALİZ VE KARAR MOTORU
# ==========================================
def radar_analizi_yap():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 🔍 Pazar taraması yapılıyor...")

    piyasa, hata = piyasa_verilerini_cek()

    if not piyasa:
        print(f"⚠️ Veri alınamadı: {hata}")
        # Hata metni özel karakter içerebildiği için düz metin gönderilir
        patrona_bildirim_gonder(f"❌ SİSTEM UYARISI\n\nYolcu360'tan veri alınamadı.\n\nNeden: {hata}", markdown=False)
        return

    bizim_fiyat = piyasa["bizim_fiyat"]
    rakip_min = piyasa["rakip_min_fiyat"]

    if bizim_fiyat is None:
        mesaj = (f"⚠️ *STOK UYARISI - {LOKASYON}*\n\n"
                 f"*{BIZIM_FIRMA}* ile eşleşen araç bulunamadı (araç yok ya da firma adı farklı yazılıyor olabilir).\n"
                 f"Bölgedeki en ucuz rakip fiyatı: {rakip_min:.0f} TL.\n"
                 f"Listede görünen firmalar: {', '.join(piyasa['firmalar'])}")
        patrona_bildirim_gonder(mesaj)
        return

    if rakip_min > 0 and bizim_fiyat > (rakip_min * 1.05):
        fiyat_farki = bizim_fiyat - rakip_min
        mesaj = (f"⚠️ *REKABET UYARISI - {LOKASYON}*\n\n"
                 f"Rakipler fiyat kırdı! Sizin en uygun aracınız *{bizim_fiyat:.0f} TL* iken, "
                 f"pazardaki en düşük fiyat *{rakip_min:.0f} TL* ({piyasa['rakip_min_firma']}).\n"
                 f"💡 Rekabette kalmak için fiyatınızı *{fiyat_farki:.0f} TL* indirmeyi değerlendirin.")
        patrona_bildirim_gonder(mesaj)
    else:
        mesaj = (f"✅ *DURUM RAPORU - {LOKASYON}*\n\n"
                 f"🟢 *Sizin Fiyatınız:* {bizim_fiyat:.0f} TL (3 günlük toplam)\n"
                 f"🔵 *En Düşük Rakip:* {rakip_min:.0f} TL ({piyasa['rakip_min_firma']})\n"
                 f"🚗 *Taranan Araç:* {piyasa['toplam_arac']} adet")
        patrona_bildirim_gonder(mesaj)


# ==========================================
# 5. ZAMANLAYICI
# ==========================================
def ana_dongu():
    os.system("cls" if os.name == "nt" else "clear")
    print("==================================================")
    print(f"  🚀 ARAÇ KİRALAMA RADARI BAŞLATILDI ({BIZIM_FIRMA})")
    print("  (Bu pencereyi arka plana alabilirsiniz)")
    print("==================================================\n")

    BEKLEME_SURESI = 3600

    while True:
        try:
            radar_analizi_yap()
        except Exception as e:
            # Beklenmeyen bir hata döngüyü öldürmesin
            print(f"Beklenmeyen hata: {type(e).__name__}: {e}")
            patrona_bildirim_gonder(f"❌ SİSTEM UYARISI\n\nRadar beklenmeyen bir hata verdi: {type(e).__name__}: {str(e)[:300]}", markdown=False)

        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] ⏳ Bir sonraki tarama için 60 dakika bekleniyor...")
        time.sleep(BEKLEME_SURESI)


if __name__ == "__main__":
    try:
        ana_dongu()
    except KeyboardInterrupt:
        print("\nSistem kullanıcı tarafından durduruldu.")
