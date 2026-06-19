"""
YouTube Konu Analiz Aracı - Ana Orkestratör

Kullanım:
    python src/main.py "Gemma 4 vision benchmark"
    python src/main.py "lokal LLM agentic coding" --sayi 5 --gun 30 --dil en

Akış:
    1. Konuyu ara (YouTube Data API v3)
    2. Her video için transcript çek (youtube-transcript-api)
    3. Başarılı transcriptleri sentezle (lokal vLLM veya Claude)
    4. Türkçe raporu hem ekrana yaz hem output/ klasörüne kaydet
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

# config/.env yükle
load_dotenv(Path(__file__).parent.parent / "config" / ".env")

from search import video_ara
from transcript import transcript_cek
from synthesize import sentezle
from precheck import toplu_kontrol
from channel import kanal_videolari


def main():
    parser = argparse.ArgumentParser(
        description="Bir konuda VEYA bir kanaldan YouTube videolarını "
                    "bulup özetler."
    )
    parser.add_argument("konu", nargs="?", default=None,
                        help="Aranacak konu (kanal modunda gerekmez)")
    parser.add_argument("--kanal", type=str, default=None,
                        help="Kanal adı, @handle, URL veya ID. Verilirse "
                             "konu araması yerine bu kanalın videoları çekilir.")
    parser.add_argument("--sayi", type=int, default=5,
                        help="Maksimum video sayısı (varsayılan 5)")
    parser.add_argument("--gun", type=int, default=None,
                        help="Son N gün filtresi (varsayılan: tüm zamanlar)")
    parser.add_argument("--dil", type=str, default=None,
                        help="Tercih dili (tr/en, varsayılan: hepsi)")
    parser.add_argument("--min-goruntulenme", type=int, default=0,
                        help="Minimum görüntülenme filtresi")
    parser.add_argument("--sadece-kontrol", action="store_true",
                        help="Transcript çekmeden sadece altyazı durumunu "
                             "tara ve raporla (100 video öncesi ön-kontrol)")
    args = parser.parse_args()

    # Mod kontrolü: ya konu ya kanal verilmeli
    if not args.konu and not args.kanal:
        print("HATA: Ya bir konu yazın ya da --kanal belirtin.")
        print('  Örnek: python src/main.py "yerelde çalışan yapay zeka"')
        print('  Örnek: python src/main.py --kanal "@kanaladi" --gun 365')
        sys.exit(1)

    # Başlık: kanal modunda kanal adı, konu modunda konu
    baslik = args.konu if args.konu else f"Kanal: {args.kanal}"

    print(f"\n{'='*60}")
    if args.kanal:
        print(f"KANAL MODU: {args.kanal}")
        if args.gun:
            print(f"Filtre: son {args.gun} gün")
    else:
        print(f"KONU: {args.konu}")
    print(f"{'='*60}\n")

    # 1. VİDEO BULMA (konu araması VEYA kanaldan listeleme)
    if args.kanal:
        print("[1/3] Kanal videoları listeleniyor...")
        try:
            videolar = kanal_videolari(
                args.kanal,
                son_gun=args.gun,
                max_video=args.sayi if args.sayi else None,
            )
        except Exception as e:
            print(f"  ✗ Kanal listeleme hatası: {e}")
            sys.exit(1)
    else:
        print("[1/3] Videolar aranıyor...")
        try:
            videolar = video_ara(
                args.konu,
                max_sonuc=args.sayi,
                son_gun=args.gun,
                min_goruntulenme=args.min_goruntulenme,
                dil=args.dil,
            )
        except Exception as e:
            print(f"  ✗ Arama hatası: {e}")
            sys.exit(1)

    if not videolar:
        print("  ✗ Hiç video bulunamadı.")
        sys.exit(0)

    print(f"  ✓ {len(videolar)} video bulundu:")
    for i, v in enumerate(videolar, 1):
        print(f"    {i}. {v['baslik'][:60]} "
              f"({v['goruntulenme']:,} görüntülenme)")

    # 1.5 ÖN-KONTROL (altyazı durumu, metni çekmeden)
    print(f"\n[Ön-kontrol] Altyazı durumu taranıyor...")
    kontrol = toplu_kontrol(videolar, diller=["tr", "en"])
    print(f"  {kontrol['ozet']}")
    if kontrol["whisper_gerekli"]:
        print(f"  ⚠ Altyazısı olmayan ({len(kontrol['whisper_gerekli'])}):")
        for v in kontrol["whisper_gerekli"][:10]:
            print(f"    - {v['baslik'][:55]}")

    # Sadece kontrol modu: burada dur, transcript çekme
    if args.sadece_kontrol:
        print(f"\n{'='*60}")
        print("ÖN-KONTROL TAMAMLANDI (--sadece-kontrol modu)")
        print(f"{'='*60}")
        print(f"\nAltyazılı (çekilebilir): {len(kontrol['altyazili'])}")
        print(f"Whisper gerekli: {len(kontrol['whisper_gerekli'])}")
        print(f"Erişilemez: {len(kontrol['erisilemez'])}")
        print("\nTranscript çekmek için --sadece-kontrol olmadan çalıştırın.")
        sys.exit(0)

    # Sadece altyazılı videolarla devam et
    videolar = kontrol["altyazili"]
    if not videolar:
        print("\n  ✗ Altyazılı video yok. Whisper olmadan devam edilemez.")
        sys.exit(1)

    # 2. TRANSCRIPT ÇEKME
    print(f"\n[2/3] Transcriptler çekiliyor...")
    basarili_videolar = []
    basarisizlar = []
    for i, v in enumerate(videolar, 1):
        sonuc = transcript_cek(v["video_id"], diller=["tr", "en"])
        if sonuc["basarili"]:
            v["metin"] = sonuc["metin"]
            v["transcript_dil"] = sonuc["dil"]
            basarili_videolar.append(v)
            print(f"    ✓ Video {i}: {len(sonuc['metin']):,} karakter "
                  f"({sonuc['dil']})")
        else:
            basarisizlar.append((v, sonuc))
            ek = " [Whisper gerekli]" if sonuc["fallback_gerekli"] else ""
            print(f"    ✗ Video {i}: {sonuc['hata']}{ek}")

    if not basarili_videolar:
        print("\n  ✗ Hiçbir videodan transcript çekilemedi.")
        print("    (Datacenter IP'deyseniz ev bağlantısından deneyin.)")
        sys.exit(1)

    # 3. SENTEZ
    print(f"\n[3/3] {len(basarili_videolar)} transcript özetleniyor...")
    try:
        rapor = sentezle(baslik, basarili_videolar)
    except Exception as e:
        print(f"  ✗ Sentez hatası: {e}")
        print("    (Lokal model çalışıyor mu? .env ayarları doğru mu?)")
        sys.exit(1)

    # ÇIKTI
    print(f"\n{'='*60}")
    print("RAPOR")
    print(f"{'='*60}\n")
    print(rapor)

    # Dosyaya kaydet
    zaman = datetime.now().strftime("%Y%m%d_%H%M%S")
    guvenli_konu = "".join(c if c.isalnum() else "_" for c in baslik)[:40]
    cikti_dosya = (
        Path(__file__).parent.parent / "output"
        / f"{zaman}_{guvenli_konu}.md"
    )
    with open(cikti_dosya, "w", encoding="utf-8") as f:
        f.write(f"# {baslik}\n\n")
        f.write(f"Tarih: {zaman}\n\n")
        f.write(f"## Analiz Edilen Videolar\n\n")
        for i, v in enumerate(basarili_videolar, 1):
            f.write(f"{i}. [{v['baslik']}]({v['url']}) - {v['kanal']}\n")
        if basarisizlar:
            f.write(f"\n## Transcript Çekilemeyenler\n\n")
            for v, s in basarisizlar:
                f.write(f"- {v['baslik']}: {s['hata']}\n")
        f.write(f"\n## Rapor\n\n{rapor}\n")

    print(f"\n{'='*60}")
    print(f"✓ Rapor kaydedildi: {cikti_dosya}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
