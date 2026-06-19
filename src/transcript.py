"""
Transcript modülü.
youtube-transcript-api kullanarak videonun altyazısını indirmeden çeker.

NOT: Bu modül datacenter/sunucu IP'lerinden 403/IpBlocked hatası verebilir.
Ev/ofis internet bağlantısından (normal IP) sorunsuz çalışması beklenir.
Altyazısı olmayan videolar için ileride Whisper fallback eklenebilir
(bkz. ileti_whisper_fallback fonksiyonu - şu an placeholder).
"""
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    TranscriptsDisabled,
    NoTranscriptFound,
    VideoUnavailable,
    RequestBlocked,
    IpBlocked,
)


def transcript_cek(video_id: str, diller: list[str] | None = None):
    """
    Bir videonun transcriptini düz metin olarak çeker.

    Parametreler:
        video_id: YouTube video kimliği (URL'deki v= sonrası)
        diller: Tercih sırasına göre dil kodları (örn. ["tr", "en"]).
                None ise önce tr, sonra en, sonra mevcut ilk dil denenir.

    Dönüş:
        dict: {
            "basarili": bool,
            "metin": str (başarılıysa düz metin, değilse ""),
            "dil": str (çekilen transcriptin dili),
            "otomatik": bool (otomatik üretilmiş altyazı mı),
            "hata": str | None (başarısızsa hata açıklaması),
            "fallback_gerekli": bool (Whisper'a düşülmeli mi),
        }
    """
    if diller is None:
        diller = ["tr", "en"]

    api = YouTubeTranscriptApi()

    try:
        # Önce mevcut transcript listesini al
        transcript_listesi = api.list(video_id)

        # Tercih edilen dillerden birini bulmaya çalış
        secilen = None
        for dil in diller:
            try:
                secilen = transcript_listesi.find_transcript([dil])
                break
            except NoTranscriptFound:
                continue

        # Tercih edilen dil yoksa, mevcut ilk transcripti al
        if secilen is None:
            mevcutlar = list(transcript_listesi)
            if not mevcutlar:
                return _sonuc(False, hata="Hiç transcript yok",
                             fallback=True)
            secilen = mevcutlar[0]

        # Transcripti çek
        veri = secilen.fetch()
        metin = " ".join(snip.text for snip in veri).strip()

        if not metin:
            return _sonuc(False, hata="Transcript boş", fallback=True)

        return _sonuc(
            True,
            metin=metin,
            dil=secilen.language_code,
            otomatik=secilen.is_generated,
        )

    except (TranscriptsDisabled, NoTranscriptFound):
        return _sonuc(False, hata="Altyazı devre dışı / bulunamadı",
                     fallback=True)
    except (RequestBlocked, IpBlocked):
        return _sonuc(
            False,
            hata="IP engellendi (datacenter IP? Ev bağlantısından deneyin)",
            fallback=False,  # bu IP sorunu, fallback çözmez
        )
    except VideoUnavailable:
        return _sonuc(False, hata="Video erişilemez", fallback=False)
    except Exception as e:
        return _sonuc(False, hata=f"{type(e).__name__}: {e}", fallback=True)


def _sonuc(basarili, metin="", dil="", otomatik=False, hata=None,
           fallback=False):
    """Standart sonuç sözlüğü üretir."""
    return {
        "basarili": basarili,
        "metin": metin,
        "dil": dil,
        "otomatik": otomatik,
        "hata": hata,
        "fallback_gerekli": fallback,
    }


def whisper_fallback_placeholder(video_id: str):
    """
    PLACEHOLDER - Henüz aktif değil.

    Altyazısı olmayan videolar için ileride buraya:
      1. yt-dlp ile SADECE ses indirme (video değil)
      2. Lokal Whisper (large-v3) ile transkripsiyon
    eklenecek. Bu adım 'indirme riski' kararına bağlı olduğu için
    şimdilik devre dışı bırakıldı.
    """
    raise NotImplementedError(
        "Whisper fallback henüz kurulmadı. İndirme kararı verildikten "
        "sonra etkinleştirilecek."
    )


if __name__ == "__main__":
    # Elle test (kendi makinende çalıştır)
    sonuc = transcript_cek("aircAruvnKk", diller=["en"])
    if sonuc["basarili"]:
        print(f"Dil: {sonuc['dil']} | Otomatik: {sonuc['otomatik']}")
        print(f"Metin uzunluğu: {len(sonuc['metin'])} karakter")
        print(f"İlk 300 karakter:\n{sonuc['metin'][:300]}")
    else:
        print(f"BAŞARISIZ: {sonuc['hata']}")
        print(f"Whisper fallback gerekli mi: {sonuc['fallback_gerekli']}")
