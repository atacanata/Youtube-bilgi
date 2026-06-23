"""Konu basligi -> YouTube'da ara -> MP3 indir -> yerelde metne cevir.

Bagimsiz arac (eski transcript/altyazi hattindan tamamen ayri).

Akis:
    1. Konuyu yt-dlp ile ARA (anahtarsiz, ytsearchN)
    2. Her video icin MP3 INDIR (yt-dlp + ffmpeg)  -> ciktilar/<konu>/mp3/
    3. MP3'u faster-whisper ile YEREL metne cevir   -> ciktilar/<konu>/metin/
    4. videolar.json + tum_metinler.md kaydet

Kullanim:
    python cikar.py "konu basligi"
    python cikar.py "konu basligi" --sayi 10 --dil tr
    python cikar.py "konu basligi" --cihaz cpu --compute int8     # GPU yoksa
    python cikar.py "konu basligi" --sadece-indir                 # MP3 al, STT yapma

MP3 ve metin diskte SAKLANIR; arac tekrar calistirilinca var olanlar atlanir.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

KOK = Path(__file__).parent
sys.path.insert(0, str(KOK))

from src.arama import konu_ara
from src.indir import mp3_indir

_TR = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")


def slugla(ad: str) -> str:
    """Konu/baslik -> dosya-guvenli klasor adi (Turkce -> ASCII)."""
    ad = (ad or "konu").translate(_TR)
    ad = re.sub(r"[^A-Za-z0-9]+", "_", ad).strip("_")
    return (ad or "konu")[:50]


def main():
    p = argparse.ArgumentParser(
        description="Konu basligindan YouTube videolarini MP3'e cevirip yerelde metne doker."
    )
    p.add_argument("konu", help="Aranacak konu basligi")
    p.add_argument("--sayi", type=int, default=10, help="Islenecek video sayisi (varsayilan 10)")
    p.add_argument("--dil", default=None, help="STT dili (tr/en...). Bos = otomatik algila")
    p.add_argument("--model", default="large-v3-turbo", help="faster-whisper modeli")
    p.add_argument("--cihaz", default="cuda", help="cuda | cpu")
    p.add_argument("--compute", default="int8_float16",
                   help="compute_type (cuda: int8_float16/float16 | cpu: int8)")
    p.add_argument("--sadece-indir", action="store_true",
                   help="Sadece MP3 indir, metne CEVIRME")
    p.add_argument("--gecikme", type=float, default=0,
                   help="Videolar arasi bekleme (sn); buyuk islerde 5-10 onerilir")
    args = p.parse_args()

    print(f"\n{'='*60}\nKONU: {args.konu}\n{'='*60}\n")

    # 1. ARAMA
    print(f"[1/3] '{args.konu}' icin {args.sayi} video araniyor (yt-dlp, anahtarsiz)...")
    try:
        videolar = konu_ara(args.konu, args.sayi)
    except RuntimeError as e:
        print(f"  ✗ {e}")
        sys.exit(1)
    if not videolar:
        print("  ✗ Hic video bulunamadi.")
        sys.exit(0)
    print(f"  ✓ {len(videolar)} video bulundu:")
    for i, v in enumerate(videolar, 1):
        print(f"    {i:>2}. {v['baslik'][:60]}  ({v['kanal']})")

    # Cikti klasorleri
    slug = slugla(args.konu)
    hedef = KOK / "ciktilar" / slug
    mp3_dir = hedef / "mp3"
    metin_dir = hedef / "metin"
    mp3_dir.mkdir(parents=True, exist_ok=True)
    metin_dir.mkdir(parents=True, exist_ok=True)

    # STT modelini BIR KEZ yukle (sadece-indir degilse)
    stt = None
    if not args.sadece_indir:
        print(f"\n[STT] faster-whisper yukleniyor "
              f"(model={args.model}, cihaz={args.cihaz}, compute={args.compute})...")
        from src.stt import WhisperMetin
        try:
            stt = WhisperMetin(args.model, args.cihaz, args.compute)
        except RuntimeError as e:
            print(f"  ✗ {e}")
            sys.exit(1)
        print("  ✓ Model hazir.")

    # 2-3. INDIR + METNE CEVIR
    sonuc = []
    for i, v in enumerate(videolar, 1):
        vid = v["video_id"]
        print(f"\n[{i}/{len(videolar)}] {v['baslik'][:55]}")

        # 2. MP3 indir
        try:
            print("  [2/3] MP3 indiriliyor...")
            mp3_yol = mp3_indir(vid, v["url"], mp3_dir)
            mb = mp3_yol.stat().st_size / 1e6
            print(f"    ✓ {mp3_yol.name} ({mb:.1f} MB)")
        except RuntimeError as e:
            print(f"    ✗ Indirme hatasi: {e}")
            sonuc.append({**v, "mp3": None, "metin_dosya": None, "hata": str(e)})
            continue

        kayit = {**v, "mp3": str(mp3_yol.relative_to(KOK))}

        # 3. Metne cevir
        if stt is not None:
            metin_yol = metin_dir / f"{vid}.txt"
            if metin_yol.exists() and metin_yol.stat().st_size > 0:
                print(f"    [3/3] Metin onbellekte: {metin_yol.name} (atlandi)")
                kayit["metin_dosya"] = str(metin_yol.relative_to(KOK))
            else:
                try:
                    print("    [3/3] Metne ceviriliyor (yerel Whisper)...")
                    metin, algi_dil, sure = stt.cevir(mp3_yol, args.dil)
                    metin_yol.write_text(metin, encoding="utf-8")
                    kayit.update({"metin_dosya": str(metin_yol.relative_to(KOK)),
                                  "stt_dil": algi_dil, "stt_sure_sn": round(sure, 1)})
                    print(f"      ✓ {len(metin):,} karakter ({algi_dil}, {sure:.0f}s) "
                          f"-> {metin_yol.name}")
                except RuntimeError as e:
                    print(f"      ✗ STT hatasi: {e}")
                    kayit["hata"] = str(e)

        sonuc.append(kayit)
        if args.gecikme and i < len(videolar):
            time.sleep(args.gecikme)

    # videolar.json
    (hedef / "videolar.json").write_text(
        json.dumps({"konu": args.konu, "videolar": sonuc}, ensure_ascii=False, indent=2),
        encoding="utf-8")

    # tum_metinler.md (okunakli birlesik dosya)
    if not args.sadece_indir:
        satir = [f"# {args.konu} — Metinler", ""]
        for i, v in enumerate(sonuc, 1):
            satir += ["", "―" * 70, f"## [{i}] {v['baslik']}", f"- {v['url']}"]
            md = v.get("metin_dosya")
            if md and (KOK / md).exists():
                satir += [f"- dil: {v.get('stt_dil','')} | {len((KOK / md).read_text(encoding='utf-8')):,} karakter", "",
                          (KOK / md).read_text(encoding="utf-8")]
            else:
                satir += ["", f"(metin yok: {v.get('hata','-')})"]
        (hedef / "tum_metinler.md").write_text("\n".join(satir), encoding="utf-8")

    # Ozet
    indirilen = sum(1 for s in sonuc if s.get("mp3"))
    cevrilen = sum(1 for s in sonuc if s.get("metin_dosya"))
    print(f"\n{'='*60}")
    print(f"BITTI: {indirilen}/{len(sonuc)} MP3 indirildi, "
          f"{cevrilen}/{len(sonuc)} metne cevrildi.")
    print(f"Cikti: ciktilar/{slug}/  (mp3/ + metin/ + tum_metinler.md + videolar.json)")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
