"""TEK video STT orkestrasyon (PILOT).

NEEDS_TRANSCRIPT + PRODUCT_SEARCH + skor>=esik icinden EN YUKSEK relevance_score'lu
1 videoyu isler. Audio context manager ile garanti silinir. Sure raporlanir (isinma icin).
"""
from __future__ import annotations

from contextlib import contextmanager

from src import db
from src.audio_downloader import download_audio, ffmpeg_var_mi
from src.transcript_import import save_transcript
from src.whisper_transcriber import transcribe


@contextmanager
def _gecici_audio(path, sil: bool):
    """Audio dosyasini is sonunda (hata olsa bile) siler."""
    try:
        yield path
    finally:
        if sil and path is not None and path.exists():
            try:
                path.unlink()
            except Exception:
                pass


def _hata(conn, vid: str, msg: str) -> None:
    conn.execute("UPDATE videos SET retry_count = retry_count + 1, updated_at = datetime('now') "
                 "WHERE video_id = ?", (vid,))
    conn.commit()
    rc = conn.execute("SELECT retry_count FROM videos WHERE video_id = ?", (vid,)).fetchone()[0]
    status = "FAILED" if rc >= 3 else "NEEDS_TRANSCRIPT"
    db.set_status(conn, vid, status, last_error=msg[:200])
    db.log_job(conn, vid, "stt-transcribe", "error", msg[:200])


def stt_transcribe(conn, config: dict, min_score: float, limit: int = 1) -> int:
    """En yuksek skorlu 1 urun videosunu indir + STT et."""
    stt = config.get("stt", {})
    if not stt.get("enabled", False):
        print("  ! stt.enabled=false. config.yaml -> stt.enabled: true yapin.")
        return 0
    if limit > 1:
        print(f"  UYARI: Pilot asamasi — 1 video onerilir (verilen --limit={limit}); yine de 1 islenecek.")
    if not ffmpeg_var_mi():
        raise SystemExit("ffmpeg PATH'te bulunamadi. Kurun: winget install Gyan.FFmpeg "
                         "(veya choco install ffmpeg), sonra terminali yeniden acin.")

    row = conn.execute(
        "SELECT video_id, title, url, relevance_score, language_hint FROM videos "
        "WHERE source_mode = 'PRODUCT_SEARCH' AND status = 'NEEDS_TRANSCRIPT' "
        "AND relevance_score >= ? ORDER BY relevance_score DESC, view_count DESC LIMIT 1",
        (min_score,),
    ).fetchone()
    if not row:
        print("  Uygun video yok (NEEDS_TRANSCRIPT + PRODUCT_SEARCH + skor>=esik).")
        return 0

    vid, title = row["video_id"], row["title"]
    print(f"  Secilen: [{row['relevance_score']}] {title[:60]} ({vid})")

    # 1) AUDIO INDIR
    db.set_status(conn, vid, "AUDIO_DOWNLOADING")
    try:
        wav = download_audio(vid, row["url"], stt.get("audio_tmp_dir", "tmp/audio"))
    except Exception as e:
        _hata(conn, vid, f"indirme: {e}")
        raise SystemExit(f"Indirme basarisiz: {e}")
    boyut_mb = wav.stat().st_size / 1e6
    print(f"  Audio indirildi: {boyut_mb:.1f} MB")

    text = lang = None
    sure = 0.0
    with _gecici_audio(wav, stt.get("delete_audio_after", True)):
        # 2) STT
        db.set_status(conn, vid, "TRANSCRIBING")
        try:
            text, lang, sure = transcribe(wav, row["language_hint"], stt)
        except Exception as e:
            _hata(conn, vid, f"stt: {e}")
            raise SystemExit(str(e))
        if not text:
            _hata(conn, vid, "bos transcript")
            raise SystemExit("STT bos metin dondurdu.")
        # 3) KAYDET (status -> TRANSCRIBED)
        save_transcript(conn, vid, "AUDIO_STT", lang, text)
        db.log_job(conn, vid, "stt-transcribe", "ok", f"{lang} {len(text)} krk {sure:.1f}s")

    silindi = not wav.exists()
    print("\n  === STT PILOT SONUC ===")
    print(f"  video_id       : {vid}")
    print(f"  baslik         : {title[:70]}")
    print(f"  dil (algilanan): {lang}")
    print(f"  STT suresi     : {sure:.1f} sn  (bu surede GPU yuk altindaydi -> isinma)")
    print(f"  audio boyut    : {boyut_mb:.1f} MB")
    print(f"  metin uzunlugu : {len(text):,} karakter")
    print(f"  audio silindi  : {silindi}")
    print(f"  status         : NEEDS_TRANSCRIPT -> TRANSCRIBED (source_type=AUDIO_STT)")
    print(f"  ilk 200 krk    : {text[:200]}")
    return 1
