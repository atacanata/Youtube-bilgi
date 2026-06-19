"""
Ön-kontrol modülü.
Bir video listesinde transcript ÇEKMEDEN önce, hangilerinde altyazı
var/yok olduğunu hızlıca tarar. Böylece 100 videoyu işlemeden önce
kaçında altyazı olduğunu, kaçının Whisper gerektireceğini görürsün.

Bu adım sadece altyazı LİSTESİNİ kontrol eder (metni çekmez),
bu yüzden çok daha hızlıdır.
"""
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    TranscriptsDisabled,
    NoTranscriptFound,
    VideoUnavailable,
    RequestBlocked,
    IpBlocked,
)


def altyazi_kontrol(video_id: str, diller: list[str] | None = None) -> dict:
    """
    Tek bir videoda altyazı durumunu kontrol eder (metni çekmeden).

    Dönüş:
        dict: {
            "video_id": str,
            "altyazi_var": bool,
            "diller": list[str] (mevcut dil kodları),
            "tercih_dil_var": bool (istenen dillerden biri mevcut mu),
            "durum": str (insan-okur durum metni),
            "whisper_gerekli": bool,
        }
    """
    if diller is None:
        diller = ["tr", "en"]

    api = YouTubeTranscriptApi()
    try:
        liste = api.list(video_id)
        mevcut_diller = [t.language_code for t in liste]
        tercih_var = any(d in mevcut_diller for d in diller)

        if not mevcut_diller:
            return _k(video_id, False, [], False,
                      "Altyazı yok", whisper=True)

        durum = f"Altyazı var ({', '.join(mevcut_diller)})"
        if not tercih_var:
            durum += " — tercih dili yok, mevcut dil kullanılacak"
        return _k(video_id, True, mevcut_diller, tercih_var, durum,
                  whisper=False)

    except (TranscriptsDisabled, NoTranscriptFound):
        return _k(video_id, False, [], False,
                  "Altyazı devre dışı", whisper=True)
    except (RequestBlocked, IpBlocked):
        return _k(video_id, False, [], False,
                  "IP engellendi (ev bağlantısı?)", whisper=False)
    except VideoUnavailable:
        return _k(video_id, False, [], False,
                  "Video erişilemez", whisper=False)
    except Exception as e:
        return _k(video_id, False, [], False,
                  f"{type(e).__name__}", whisper=False)


def toplu_kontrol(videolar: list[dict],
                  diller: list[str] | None = None) -> dict:
    """
    Video listesini tarar, özet istatistik döndürür.

    Parametreler:
        videolar: 'video_id' ve 'baslik' içeren liste

    Dönüş:
        dict: {
            "toplam": int,
            "altyazili": list[dict] (transcript çekilebilir),
            "whisper_gerekli": list[dict],
            "erisilemez": list[dict],
            "ozet": str,
        }
    """
    altyazili, whisper_gerekli, erisilemez = [], [], []

    for v in videolar:
        k = altyazi_kontrol(v["video_id"], diller)
        kayit = {**v, **k}
        if k["altyazi_var"]:
            altyazili.append(kayit)
        elif k["whisper_gerekli"]:
            whisper_gerekli.append(kayit)
        else:
            erisilemez.append(kayit)

    ozet = (
        f"Toplam {len(videolar)} video: "
        f"{len(altyazili)} altyazılı (çekilebilir), "
        f"{len(whisper_gerekli)} Whisper gerekli, "
        f"{len(erisilemez)} erişilemez"
    )
    return {
        "toplam": len(videolar),
        "altyazili": altyazili,
        "whisper_gerekli": whisper_gerekli,
        "erisilemez": erisilemez,
        "ozet": ozet,
    }


def _k(video_id, var, diller, tercih, durum, whisper):
    return {
        "video_id": video_id,
        "altyazi_var": var,
        "diller": diller,
        "tercih_dil_var": tercih,
        "durum": durum,
        "whisper_gerekli": whisper,
    }


if __name__ == "__main__":
    # Elle test (kendi makinende)
    sahte = [
        {"video_id": "aircAruvnKk", "baslik": "Test 1"},
        {"video_id": "xxxxxxxxxxx", "baslik": "Test 2"},
    ]
    rapor = toplu_kontrol(sahte, diller=["en"])
    print(rapor["ozet"])
    for v in rapor["altyazili"]:
        print(f"  ✓ {v['baslik']}: {v['durum']}")
    for v in rapor["whisper_gerekli"]:
        print(f"  ⚠ {v['baslik']}: {v['durum']}")
