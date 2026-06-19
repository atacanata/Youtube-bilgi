"""
Anahtarsiz kanal cekme rutini  (Claude Code'un sentezi icin girdi hazirlar).

YouTube Data API anahtari GEREKMEZ: kanalin son videolarini RSS ile bulur,
sonra projenin GERCEK precheck.py + transcript.py modulleriyle altyazilari
indirmeden ceker. Sentez (ozetleme) bu betikte YOK -- onu Claude Code yapar.

Kullanim:
    python kanal_cek.py "@kanaladi"
    python kanal_cek.py "https://www.youtube.com/@kanaladi" --sayi 10
    python kanal_cek.py "UCxxxxxxxxxxxxxxxxxxxxxx"

Cikti (REPODA IZLENEN kanallar/<kanal>/ klasorune):
    transkriptler.json     (tum veri: meta + tam transcript metni, makine icin)
    ham_transkriptler.md   (satir-kaydirmali ham metinler, insan + Claude icin)

NOT: Sayfa kazima ~30 videoya kadar verir; RSS yedegi en fazla ~15. Daha
fazlasi veya konu aramasi icin projenin API anahtarli main.py akisi gerekir.
"""
import re
import sys
import json
import time
import argparse
import textwrap
import requests
from pathlib import Path
from xml.etree import ElementTree as ET

KOK = Path(__file__).parent
sys.path.insert(0, str(KOK / "src"))
from transcript import transcript_cek      # projenin gercek modulu
# NOT: transcript_cek zaten dahili .list() yapar; ayrica precheck cagirmak
# istegi ikiye katlar ve rate-limit'i kotulestirir -> rutinde tek cagri.

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
     "Accept-Language": "en-US,en;q=0.9",
     "Cookie": "CONSENT=YES+1"}   # onay sayfasini atla -> /videos grid'i gelir
DILLER = ["tr", "en"]


def kanal_id_cek(girdi: str) -> str:
    """@handle / URL / ID girdisinden kanal ID'sini API anahtarsiz bulur."""
    girdi = girdi.strip()
    if re.fullmatch(r"UC[\w-]{22}", girdi):
        return girdi
    m = re.search(r"channel/(UC[\w-]{22})", girdi)
    if m:
        return m.group(1)
    # @handle ya da duz ad -> kanal sayfasini cek, ID'yi ayikla
    if girdi.startswith("@") or "youtube.com" in girdi:
        url = girdi if girdi.startswith("http") else f"https://www.youtube.com/{girdi}"
    else:
        url = f"https://www.youtube.com/@{girdi}"
    if "/videos" not in url:
        url = url.rstrip("/") + "/videos"
    r = requests.get(url, headers=H, timeout=30)
    r.raise_for_status()
    m = (re.search(r'"channelId":"(UC[\w-]{22})"', r.text)
         or re.search(r'"externalId":"(UC[\w-]{22})"', r.text)
         or re.search(r'channel/(UC[\w-]{22})', r.text))
    if not m:
        raise SystemExit(f"Kanal ID bulunamadi: {girdi}")
    return m.group(1)


def _ytinitialdata(html: str):
    for pat in (r'ytInitialData\s*=\s*({.+?})\s*;</script>',
                r'var ytInitialData\s*=\s*({.+?});'):
        m = re.search(pat, html, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except Exception:
                continue
    return None


def _grid_videolar(data) -> list:
    """ytInitialData'daki /videos grid'inden videolari sirayla (yeniden eskiye) ceker."""
    out, seen = [], set()
    try:
        tabs = data["contents"]["twoColumnBrowseResultsRenderer"]["tabs"]
    except Exception:
        return out
    for tab in tabs:
        grid = tab.get("tabRenderer", {}).get("content", {}).get("richGridRenderer")
        if not grid:
            continue
        for it in grid.get("contents", []):
            vr = it.get("richItemRenderer", {}).get("content", {}).get("videoRenderer")
            if not vr or not vr.get("videoId") or vr["videoId"] in seen:
                continue
            t = vr.get("title", {})
            baslik = (t["runs"][0].get("text", "") if t.get("runs") else t.get("simpleText", ""))
            pt = vr.get("publishedTimeText", {})
            seen.add(vr["videoId"])
            out.append({
                "video_id": vr["videoId"],
                "baslik": baslik,
                "tarih": pt.get("simpleText", "") if isinstance(pt, dict) else "",
                "url": f"https://www.youtube.com/watch?v={vr['videoId']}",
            })
    return out


def son_videolar(kanal_id: str, adet: int):
    """Kanalin son videolarini API anahtarsiz getirir.
    Once /videos sayfasini kazir (30+ verebilir), eksik kalirsa RSS ile (max ~15) tamamlar."""
    kanal, videolar = "", []
    try:
        r = requests.get(f"https://www.youtube.com/channel/{kanal_id}/videos",
                         headers=H, timeout=30)
        r.raise_for_status()
        data = _ytinitialdata(r.text)
        if data:
            try:
                kanal = data["metadata"]["channelMetadataRenderer"]["title"]
            except Exception:
                pass
            videolar = _grid_videolar(data)
    except Exception:
        pass

    if len(videolar) < adet or not kanal:           # RSS yedek
        try:
            rss = requests.get(
                f"https://www.youtube.com/feeds/videos.xml?channel_id={kanal_id}",
                headers=H, timeout=30)
            rss.raise_for_status()
            ns = {"a": "http://www.w3.org/2005/Atom",
                  "yt": "http://www.youtube.com/xml/schemas/2015"}
            root = ET.fromstring(rss.content)
            if not kanal:
                kanal = root.findtext("a:title", default="", namespaces=ns)
            var = {v["video_id"] for v in videolar}
            for e in root.findall("a:entry", ns):
                vid = e.findtext("yt:videoId", namespaces=ns)
                if vid not in var:
                    videolar.append({
                        "video_id": vid,
                        "baslik": e.findtext("a:title", namespaces=ns),
                        "tarih": e.findtext("a:published", namespaces=ns),
                        "url": f"https://www.youtube.com/watch?v={vid}",
                    })
        except Exception:
            pass

    for v in videolar:
        v["kanal"] = kanal
    if len(videolar) < adet:
        print(f"  (Uyari: yalnizca {len(videolar)} video bulunabildi; "
              f"daha fazlasi icin API anahtarli main.py gerekir.)")
    return kanal, videolar[:adet]


_TR = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")


def slugla(ad: str, yedek: str) -> str:
    """Kanal adindan dosya-guvenli klasor adi uretir (Turkce -> ASCII)."""
    ad = (ad or yedek).translate(_TR)
    ad = re.sub(r"[^A-Za-z0-9]+", "_", ad).strip("_")
    return ad or yedek


def main():
    p = argparse.ArgumentParser(description="Anahtarsiz kanal cekme (scrape/RSS + transcript).")
    p.add_argument("kanal", help="@handle, URL veya kanal ID")
    p.add_argument("--sayi", type=int, default=10, help="Son kac video (varsayilan 10, ~30'a kadar)")
    args = p.parse_args()

    kanal_id = kanal_id_cek(args.kanal)
    kanal, videolar = son_videolar(kanal_id, args.sayi)
    print(f"Kanal: {kanal}  ({kanal_id})")
    print(f"Son {len(videolar)} video bulundu.\n")

    slug = slugla(kanal, re.sub(r"[^A-Za-z0-9]+", "_", args.kanal).strip("_") or kanal_id)
    hedef = KOK / "kanallar" / slug
    hedef.mkdir(parents=True, exist_ok=True)

    # Onceki basarili transcriptleri onbellekten al: tekrar cekme, IYI VERIYI EZME.
    onbellek = {}
    eski = hedef / "transkriptler.json"
    if eski.exists():
        try:
            for r in json.loads(eski.read_text(encoding="utf-8")).get("videolar", []):
                if r.get("metin"):
                    onbellek[r["video_id"]] = r
        except Exception:
            pass

    def engel_mi(h):
        return bool(h) and ("engel" in h.lower() or "block" in h.lower())

    bekleme = 2.5 if len(videolar) > 15 else 1.5
    sonuc = []
    for i, v in enumerate(videolar, 1):
        vid = v["video_id"]
        if vid in onbellek:                      # daha once cekilmis -> ag istegi yok
            sonuc.append({**v, **onbellek[vid]})
            print(f"  {i:>2}. ONBELLEK {len(onbellek[vid]['metin']):>7,} krk"
                  f"           | {v['baslik'][:50]}")
            continue
        t = transcript_cek(vid, DILLER)
        for deneme in range(2):                  # rate-limit'e karsi yeniden deneme
            if t["basarili"] or not engel_mi(t.get("hata")):
                break
            bekle = 10 * (deneme + 1)
            print(f"      ... IP engeli; {bekle}s bekleyip yeniden ({deneme+1}/2)")
            time.sleep(bekle)
            t = transcript_cek(vid, DILLER)
        kayit = {**v, "altyazi_var": t["basarili"],
                 "transcript_basarili": t["basarili"], "transcript_dil": t.get("dil", ""),
                 "otomatik": t.get("otomatik", False),
                 "metin": t["metin"] if t["basarili"] else "", "hata": t.get("hata")}
        durum = (f"OK {len(t['metin']):>7,} krk ({t['dil']}"
                 f"{', oto' if t.get('otomatik') else ''})"
                 if t["basarili"] else f"HATA: {t['hata']}")
        sonuc.append(kayit)
        print(f"  {i:>2}. {durum:<40} | {v['baslik'][:50]}")
        time.sleep(bekleme)                      # nazik ol: istekleri arala

    veri = {"kanal": kanal, "channel_id": kanal_id, "videolar": sonuc}
    eski.write_text(json.dumps(veri, ensure_ascii=False, indent=2), encoding="utf-8")

    # Ham transkriptler: REPODA IZLENEN, hem insan hem Claude icin okunakli dosya
    satir = [f"# {kanal} — Ham Transkriptler", "",
             f"Kanal ID: `{kanal_id}`  |  Video sayisi: {len(sonuc)}", ""]
    for i, v in enumerate(sonuc, 1):
        satir += ["", "―" * 78, f"## [Video {i}] {v['baslik']}",
                  f"- {v['url']}",
                  f"- tarih: {v.get('tarih','')} | dil: {v.get('transcript_dil','')} "
                  f"| {len(v.get('metin','')):,} karakter", ""]
        satir.append(textwrap.fill(v["metin"], 110) if v.get("metin")
                     else f"(transcript yok: {v.get('hata','')})")
    (hedef / "ham_transkriptler.md").write_text("\n".join(satir), encoding="utf-8")

    basarili = [s for s in sonuc if s.get("metin")]
    print(f"\nOZET: {len(basarili)}/{len(sonuc)} transcript, "
          f"toplam {sum(len(s['metin']) for s in basarili):,} karakter.")
    print(f"Cikti (repoda izlenir): kanallar/{slug}/")
    print("  transkriptler.json (ham/makine) + ham_transkriptler.md (ham/okunakli)")
    print("Sonraki adim: Claude Code ham_transkriptler.md'i okuyup analiz.md uretir.")


if __name__ == "__main__":
    main()
