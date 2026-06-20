"""PRODUCT_SEARCH STT orkestrasyon.

En yuksek skorlu N (varsayilan 1) NEEDS_TRANSCRIPT + PRODUCT_SEARCH videoyu yt-dlp ile
indirip faster-whisper ile transcribe eder. --product verilirse o urunle sinirlar.
Audio context manager ile (hata olsa bile) silinir. Sure raporlanir (GPU isinma icin).
Paralel YOK; tek tek islenir.
"""
from __future__ import annotations

from contextlib import contextmanager

from src import db
from src.audio_downloader import download_audio
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


def _process_one(conn, stt: dict, row) -> tuple[bool, float, int]:
    """Tek videoyu indir + STT + kaydet. (basarili, sure_sn, karakter) dondurur."""
    vid, title = row["video_id"], row["title"]
    print(f"\n  > [{row['relevance_score']}] {title[:58]} ({vid})")

    db.set_status(conn, vid, "AUDIO_DOWNLOADING")
    try:
        wav = download_audio(vid, row["url"], stt.get("audio_tmp_dir", "tmp/audio"))
    except Exception as e:
        _hata(conn, vid, f"indirme: {e}")
        print(f"    ! indirme hatasi: {e}")
        return (False, 0.0, 0)
    boyut_mb = wav.stat().st_size / 1e6

    with _gecici_audio(wav, stt.get("delete_audio_after", True)):
        db.set_status(conn, vid, "TRANSCRIBING")
        try:
            text, lang, sure = transcribe(wav, row["language_hint"], stt)
        except Exception as e:
            _hata(conn, vid, f"stt: {e}")
            print(f"    ! STT hatasi: {e}")
            return (False, 0.0, 0)
        if not text:
            _hata(conn, vid, "bos transcript")
            print("    ! bos transcript")
            return (False, 0.0, 0)
        save_transcript(conn, vid, "AUDIO_STT", lang, text)
        db.log_job(conn, vid, "stt-transcribe", "ok", f"{lang} {len(text)} krk {sure:.1f}s")

    print(f"    OK {boyut_mb:.1f}MB | dil={lang} | {sure:.1f}s | {len(text):,} krk "
          f"| audio silindi:{not wav.exists()}")
    return (True, sure, len(text))


def stt_transcribe(conn, config: dict, min_score: float, limit: int = 1,
                   product: str | None = None) -> int:
    """En yuksek skorlu (en fazla limit) urun videosunu indir + STT et."""
    stt = config.get("stt", {})
    if not stt.get("enabled", False):
        print("  ! stt.enabled=false. config.yaml -> stt.enabled: true yapin.")
        return 0

    q = ("SELECT video_id, title, url, relevance_score, language_hint FROM videos "
         "WHERE source_mode = 'PRODUCT_SEARCH' AND status = 'NEEDS_TRANSCRIPT' "
         "AND relevance_score >= ?")
    params: list = [min_score]
    if product:
        q += " AND product_name = ?"
        params.append(product)
    q += " ORDER BY relevance_score DESC, view_count DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(q, params).fetchall()
    if not rows:
        print("  Uygun video yok (NEEDS_TRANSCRIPT + PRODUCT_SEARCH + skor>=esik).")
        return 0

    print(f"  {len(rows)} video islenecek (her biri ~20 sn GPU yuku; tek tek).")
    ok = 0
    toplam_sure = 0.0
    toplam_krk = 0
    for row in rows:
        basarili, sure, krk = _process_one(conn, stt, row)
        if basarili:
            ok += 1
            toplam_sure += sure
            toplam_krk += krk

    print("\n  === STT OZET ===")
    print(f"  basarili: {ok}/{len(rows)} | toplam STT suresi: {toplam_sure:.1f} sn "
          f"| toplam metin: {toplam_krk:,} karakter")
    print("  (GPU bu sure boyunca yuk altindaydi -> isinma)")
    return ok
