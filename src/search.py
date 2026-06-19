"""
Video keşif modülü.
YouTube Data API v3 kullanarak bir konuda alakalı videoları bulur.

API anahtarı .env dosyasından YOUTUBE_API_KEY olarak okunur.
"""
import os
from datetime import datetime, timedelta, timezone
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


def video_ara(
    konu: str,
    max_sonuc: int = 5,
    son_gun: int | None = None,
    min_goruntulenme: int = 0,
    dil: str | None = None,
):
    """
    Bir konuda alakalı videoları arar ve meta verilerini döndürür.

    Parametreler:
        konu: Aranacak konu (örn. "Gemma 4 vision benchmark")
        max_sonuc: Döndürülecek video sayısı (varsayılan 5)
        son_gun: Sadece son N gün içindeki videolar (None = tüm zamanlar)
        min_goruntulenme: Minimum görüntülenme filtresi (0 = filtresiz)
        dil: Tercih edilen video dili kodu (örn. "tr", "en"; None = hepsi)

    Dönüş:
        list[dict]: Her biri video_id, baslik, kanal, tarih, goruntulenme,
                    aciklama, url içeren sözlük listesi.
    """
    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        raise ValueError(
            "YOUTUBE_API_KEY bulunamadı. config/.env dosyasına ekleyin."
        )

    youtube = build("youtube", "v3", developerKey=api_key)

    # Arama parametrelerini hazırla
    arama_params = {
        "q": konu,
        "part": "snippet",
        "type": "video",
        "order": "relevance",  # alaka sırası; "viewCount", "date" de olabilir
        "maxResults": min(max_sonuc * 2, 50),  # filtre payı için fazladan çek
    }
    if son_gun is not None:
        tarih_siniri = datetime.now(timezone.utc) - timedelta(days=son_gun)
        arama_params["publishedAfter"] = tarih_siniri.isoformat()
    if dil is not None:
        arama_params["relevanceLanguage"] = dil

    try:
        arama_yaniti = youtube.search().list(**arama_params).execute()
    except HttpError as e:
        raise RuntimeError(f"YouTube API arama hatası: {e}") from e

    # Video ID'lerini topla
    video_idler = [
        item["id"]["videoId"]
        for item in arama_yaniti.get("items", [])
        if item["id"].get("videoId")
    ]
    if not video_idler:
        return []

    # İstatistik (görüntülenme) için ikinci çağrı
    try:
        detay_yaniti = (
            youtube.videos()
            .list(part="statistics,snippet", id=",".join(video_idler))
            .execute()
        )
    except HttpError as e:
        raise RuntimeError(f"YouTube API detay hatası: {e}") from e

    sonuclar = []
    for item in detay_yaniti.get("items", []):
        goruntulenme = int(item["statistics"].get("viewCount", 0))
        if goruntulenme < min_goruntulenme:
            continue
        sonuclar.append(
            {
                "video_id": item["id"],
                "baslik": item["snippet"]["title"],
                "kanal": item["snippet"]["channelTitle"],
                "tarih": item["snippet"]["publishedAt"],
                "goruntulenme": goruntulenme,
                "aciklama": item["snippet"]["description"][:300],
                "url": f"https://www.youtube.com/watch?v={item['id']}",
            }
        )

    # Görüntülenmeye göre sırala, ilk max_sonuc'u al
    sonuclar.sort(key=lambda x: x["goruntulenme"], reverse=True)
    return sonuclar[:max_sonuc]


if __name__ == "__main__":
    # Basit elle test (kendi makinende API anahtarı ile çalıştır)
    import json
    from dotenv import load_dotenv

    load_dotenv("config/.env")
    sonuc = video_ara("Gemma 4 vision benchmark", max_sonuc=3, son_gun=90)
    print(json.dumps(sonuc, indent=2, ensure_ascii=False))
