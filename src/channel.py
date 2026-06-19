"""
Kanal modülü.
Bir kanalın videolarını listeler (konu araması yerine kanal-bazlı çekme).

Kota açısından çok ucuz: arama (search.list, 100 birim) yerine
playlistItems.list (~1 birim) kullanır. Böylece bir kanalın yüzlerce
videosunu düşük kotayla listeleyebilirsin.

Akış:
  1. Kanal adı/handle/URL -> kanal ID (gerekiyorsa)
  2. Kanal ID -> "uploads" playlist ID
  3. Playlist -> tüm videolar (sayfalı)
  4. Tarih filtresi (son N gün)
"""
import os
import re
from datetime import datetime, timedelta, timezone
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


def _youtube():
    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        raise ValueError(
            "YOUTUBE_API_KEY bulunamadı. config/.env dosyasına ekleyin."
        )
    return build("youtube", "v3", developerKey=api_key)


def kanal_id_bul(kanal_girdi: str) -> str:
    """
    Kanal adı, @handle veya URL'den kanal ID'sini bulur.

    Desteklenen girdiler:
        - "UCxxxxxxxxxxxxxxxxxxxxxx" (zaten ID ise dokunmaz)
        - "@kanalhandle"
        - "https://www.youtube.com/@kanalhandle"
        - "https://www.youtube.com/channel/UCxxxx"
        - "Kanal Adı" (düz metin -> arama ile bulur, 100 birim kota)

    Dönüş:
        str: kanal ID (UC ile başlar)
    """
    girdi = kanal_girdi.strip()

    # Zaten kanal ID mi?
    if re.fullmatch(r"UC[\w-]{22}", girdi):
        return girdi

    # channel/UC... URL'si mi?
    m = re.search(r"channel/(UC[\w-]{22})", girdi)
    if m:
        return m.group(1)

    yt = _youtube()

    # @handle mı? (URL içinden de ayıkla)
    handle = None
    m = re.search(r"@([\w.-]+)", girdi)
    if m:
        handle = m.group(1)

    if handle:
        try:
            yanit = yt.channels().list(
                part="id", forHandle=handle
            ).execute()
            if yanit.get("items"):
                return yanit["items"][0]["id"]
        except HttpError as e:
            raise RuntimeError(f"Handle ile kanal bulunamadı: {e}") from e

    # Son çare: düz metin adı ile ara (100 birim kota harcar)
    try:
        yanit = yt.search().list(
            q=girdi, part="snippet", type="channel", maxResults=1
        ).execute()
    except HttpError as e:
        raise RuntimeError(f"Kanal araması hatası: {e}") from e

    if not yanit.get("items"):
        raise ValueError(f"Kanal bulunamadı: '{kanal_girdi}'")
    return yanit["items"][0]["snippet"]["channelId"]


def kanal_videolari(
    kanal_girdi: str,
    son_gun: int | None = None,
    max_video: int | None = None,
):
    """
    Bir kanalın videolarını listeler.

    Parametreler:
        kanal_girdi: Kanal adı, @handle, URL veya ID
        son_gun: Sadece son N gün içindeki videolar (None = tümü)
        max_video: En fazla kaç video (None = tümü)

    Dönüş:
        list[dict]: search.py ile aynı format (video_id, baslik, kanal,
                    tarih, goruntulenme, aciklama, url)
    """
    yt = _youtube()
    kanal_id = kanal_id_bul(kanal_girdi)

    # uploads playlist ID'sini al
    try:
        kanal_yanit = yt.channels().list(
            part="contentDetails,snippet", id=kanal_id
        ).execute()
    except HttpError as e:
        raise RuntimeError(f"Kanal detayı hatası: {e}") from e

    if not kanal_yanit.get("items"):
        raise ValueError(f"Kanal ID geçersiz: {kanal_id}")

    kanal_adi = kanal_yanit["items"][0]["snippet"]["title"]
    uploads_id = (
        kanal_yanit["items"][0]["contentDetails"]
        ["relatedPlaylists"]["uploads"]
    )

    # Tarih sınırı
    tarih_siniri = None
    if son_gun is not None:
        tarih_siniri = datetime.now(timezone.utc) - timedelta(days=son_gun)

    # Playlist'i sayfa sayfa gez
    videolar = []
    sayfa_token = None
    durduruldu = False
    while not durduruldu:
        try:
            pl_yanit = yt.playlistItems().list(
                part="snippet,contentDetails",
                playlistId=uploads_id,
                maxResults=50,
                pageToken=sayfa_token,
            ).execute()
        except HttpError as e:
            raise RuntimeError(f"Playlist listeleme hatası: {e}") from e

        for item in pl_yanit.get("items", []):
            yayin_str = item["contentDetails"].get("videoPublishedAt")
            if not yayin_str:
                continue  # henüz yayınlanmamış / özel
            yayin = datetime.fromisoformat(yayin_str.replace("Z", "+00:00"))

            # Tarih filtresi: uploads playlist en yeniden eskiye sıralı,
            # sınırın altına inince durabiliriz
            if tarih_siniri and yayin < tarih_siniri:
                durduruldu = True
                break

            videolar.append({
                "video_id": item["contentDetails"]["videoId"],
                "baslik": item["snippet"]["title"],
                "kanal": kanal_adi,
                "tarih": yayin_str,
                "goruntulenme": 0,  # playlistItems görüntülenme vermez
                "aciklama": item["snippet"].get("description", "")[:300],
                "url": (
                    f"https://www.youtube.com/watch?v="
                    f"{item['contentDetails']['videoId']}"
                ),
            })

            if max_video and len(videolar) >= max_video:
                durduruldu = True
                break

        sayfa_token = pl_yanit.get("nextPageToken")
        if not sayfa_token:
            break

    return videolar


if __name__ == "__main__":
    # Elle test (kendi makinende API anahtarı ile)
    import json
    from dotenv import load_dotenv
    load_dotenv("config/.env")
    # Örnek: bir kanalın son 1 yılı
    vids = kanal_videolari("@3blue1brown", son_gun=365)
    print(f"Bulunan video: {len(vids)}")
    print(json.dumps(vids[:3], indent=2, ensure_ascii=False))
