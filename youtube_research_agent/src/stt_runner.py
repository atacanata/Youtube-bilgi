"""PRODUCT_SEARCH STT orkestrasyon + BAN KORUMASI (rate limit).

En yuksek skorlu (en fazla rate_limit.max_videos_per_run) NEEDS_TRANSCRIPT + PRODUCT_SEARCH
videoyu yt-dlp ile indirip faster-whisper ile transcribe eder.
Guvenlik: gunluk kap, --limit tavani, video arasi RASTGELE gecikme, 429'da cooldown+DUR.
Paralel YOK; tek tek islenir. Audio context manager ile (hata olsa bile) silinir.
"""
from __future__ import annotations

import time
from contextlib import contextmanager

from src import db, rate_limiter
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


def _is_rate_limit(msg: str) -> bool:
    """yt-dlp hata metni ban/hiz-siniri sinyali iceriyor mu?"""
    m = (msg or "").lower()
    return any(s in m for s in (
        "429", "too many requests", "rate limit", "not a bot", "403", "forbidden"))


def _hata(conn, vid: str, msg: str) -> None:
    conn.execute("UPDATE videos SET retry_count = retry_count + 1, updated_at = datetime('now') "
                 "WHERE video_id = ?", (vid,))
    conn.commit()
    rc = conn.execute("SELECT retry_count FROM videos WHERE video_id = ?", (vid,)).fetchone()[0]
    status = "FAILED" if rc >= 3 else "NEEDS_TRANSCRIPT"
    db.set_status(conn, vid, status, last_error=msg[:200])
    db.log_job(conn, vid, "stt-transcribe", "error", msg[:200])


def _process_one(conn, stt: dict, row) -> tuple[str, float, int]:
    """Tek video: indir + STT + kaydet. Durum: 'ok' | 'fail' | 'ratelimit'."""
    vid, title = row["video_id"], row["title"]
    print(f"\n  > [{row['relevance_score']}] {title[:58]} ({vid})")

    db.set_status(conn, vid, "AUDIO_DOWNLOADING")
    try:
        wav = download_audio(vid, row["url"], stt.get("audio_tmp_dir", "tmp/audio"))
    except Exception as e:
        if _is_rate_limit(str(e)):
            db.set_status(conn, vid, "FAILED", last_error="rate_limit")
            db.log_job(conn, vid, "stt-transcribe", "error", "rate_limit")
            print(f"    !! HIZ SINIRI/ban sinyali: {e}")
            return ("ratelimit", 0.0, 0)
        _hata(conn, vid, f"indirme: {e}")
        print(f"    ! indirme hatasi: {e}")
        return ("fail", 0.0, 0)
    boyut_mb = wav.stat().st_size / 1e6

    with _gecici_audio(wav, stt.get("delete_audio_after", True)):
        db.set_status(conn, vid, "TRANSCRIBING")
        try:
            text, lang, sure = transcribe(wav, row["language_hint"], stt)
        except Exception as e:
            _hata(conn, vid, f"stt: {e}")
            print(f"    ! STT hatasi: {e}")
            return ("fail", 0.0, 0)
        if not text:
            _hata(conn, vid, "bos transcript")
            print("    ! bos transcript")
            return ("fail", 0.0, 0)
        save_transcript(conn, vid, "AUDIO_STT", lang, text)
        db.log_job(conn, vid, "stt-transcribe", "ok", f"{lang} {len(text)} krk {sure:.1f}s")

    print(f"    OK {boyut_mb:.1f}MB | dil={lang} | {sure:.1f}s | {len(text):,} krk "
          f"| audio silindi:{not wav.exists()}")
    return ("ok", sure, len(text))


def stt_transcribe(conn, config: dict, min_score: float, limit: int = 1,
                   product: str | None = None, dry_run: bool = False) -> int:
    """En yuksek skorlu urun videolarini (guvenlik kurallariyla) indir + STT et."""
    stt = config.get("stt", {})
    if not stt.get("enabled", False):
        print("  ! stt.enabled=false. config.yaml -> stt.enabled: true yapin.")
        return 0

    # --- BAN KORUMASI: gunluk kap ---
    allowed, used, remaining = rate_limiter.check_daily_cap(config)
    cap = rate_limiter.daily_cap(config)
    if not allowed:
        print(f"  Bugun {used} video islendi (gunluk guvenlik limiti {cap}). "
              f"Yarin devam edin.")
        return 0

    # --- BAN KORUMASI: tek-calistirma tavani ---
    hard = rate_limiter.max_per_run(config)
    effective = min(limit, hard, remaining)
    if limit > hard:
        print(f"  Guvenlik limiti: tek calistirmada en fazla {hard} video. "
              f"{effective} islenecek (istenen {limit}).")
    print(f"  Gunluk kullanim: {used}/{cap} | kalan: {remaining} | bu calistirma: {effective}")

    q = ("SELECT video_id, title, url, relevance_score, language_hint FROM videos "
         "WHERE source_mode = 'PRODUCT_SEARCH' AND status = 'NEEDS_TRANSCRIPT' "
         "AND relevance_score >= ?")
    params: list = [min_score]
    if product:
        q += " AND product_name = ?"
        params.append(product)
    q += " ORDER BY relevance_score DESC, view_count DESC LIMIT ?"
    params.append(effective)
    rows = conn.execute(q, params).fetchall()
    if not rows:
        print("  Uygun video yok (NEEDS_TRANSCRIPT + PRODUCT_SEARCH + skor>=esik).")
        return 0

    if dry_run:
        print("  [DRY-RUN] indirme/STT YOK. Islenecek videolar:")
        for r in rows:
            print(f"   - [{r['relevance_score']}] {r['title'][:55]} ({r['video_id']})")
        ornek = [rate_limiter.get_random_delay(config) for _ in range(4)]
        print(f"  Ornek rastgele video-arasi gecikmeler (sn, sabit degil): {ornek}")
        return 0

    ok = 0
    toplam_sure = 0.0
    toplam_krk = 0
    for i, row in enumerate(rows):
        status, sure, krk = _process_one(conn, stt, row)
        if status == "ratelimit":
            rate_limiter.trigger_cooldown(config)
            print("\n  !! YouTube HIZ SINIRI algilandi -> ISLEM DURDURULDU (sessizce devam YOK).")
            print("     IP'ye birkac saat ara verin veya modemi yeniden baslatin, sonra tekrar deneyin.")
            break
        if status == "ok":
            rate_limiter.record_video_processed(config)
            ok += 1
            toplam_sure += sure
            toplam_krk += krk
            if i < len(rows) - 1:
                d = rate_limiter.get_random_delay(config)
                print(f"  ... sonraki videodan once {d} sn bekleniyor (insan-benzeri damlatma)")
                time.sleep(d)

    print("\n  === STT OZET ===")
    print(f"  basarili: {ok}/{len(rows)} | toplam STT suresi: {toplam_sure:.1f} sn "
          f"| toplam metin: {toplam_krk:,} karakter")
    print("  (GPU bu sure boyunca yuk altindaydi -> isinma)")
    return ok
