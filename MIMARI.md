# YouTube Araştırma/Analiz Sistemi — Teknik Mimari

> Amaç: Belirli kanallardaki videolardan **işime/ajan sistemime uygulanabilir fikirler, hook,
> video yapısı, özet** üretmek. (Örnek kanallar: Mert Durmazer | Digital Academy, Alex Hormozi.)
>
> Temel ilke: **Asıl değer metadata + LLM analizinde.** Transkript "olursa iyi"dir, omurga değil.
> Resmî API = sağlam; transkript = seçici/yavaş/cache'li; proxy = ana çözüm DEĞİL.

## Mevcut durum (bu repoda zaten var)
- `src/channel.py` — YouTube Data API ile kanal→video listesi (playlistItems, 1 quota/sayfa).
- `kanal_cek.py --liste` — API ile listeleme, transkript ucuna dokunmaz (sıfır ban).
- `kanallar/<Kanal>/` — insan-okur çıktı (basliklar.md, videolar.json, analiz.md).
- Yapıldı: Alex Ziskind 100 + Mert 30 video **listesi** çekildi. Transkriptler IP engelinde.
- Donanım: RTX 4080 Laptop **12 GB** (faster-whisper large-v3 için yeterli).

---

## A) YouTube linkinden metin elde etme yöntemleri + KARAR MATRİSİ

| Yöntem | Ne verir | Temizlik (ToS) | Güvenilirlik | Maliyet | Ban riski | Ne zaman |
|--------|----------|----------------|--------------|---------|-----------|----------|
| **Data API — metadata** (playlistItems + videos.list) | başlık, açıklama, chapter, süre, view/like, thumbnail | ✅ Tam temiz | ✅ Yüksek | ~1 unit/50 video | ❌ Yok | **Her zaman (omurga)** |
| **Data API — captions.download** | altyazı metni | ✅ Temiz ama **sadece SAHİBİ olduğun** video | Orta | 200 unit/çağrı + OAuth | ❌ Yok | Kendi/yetkili kanal |
| **youtube-transcript-api** (timedtext) | altyazı metni (her video) | ⚠️ Gri (otomatik erişim ToS'a aykırı) | Düşük (IP banlanır) | Ücretsiz | ⚠️ Yüksek | Az sayıda, yavaş, cache'li |
| **yt-dlp + STT** (audio indir→Whisper) | her videodan metin | ⛔ Koyu gri (başkasının içeriğini indirme) | Yüksek (teknik) | GPU/zaman | ⚠️ İndirme tespit edilebilir | Kendi/izinli dosya |
| **Manuel transcript paste** | altyazı metni | ✅ Tam temiz | ✅ Yüksek | İnsan emeği | ❌ Yok | Yüksek değerli az video |
| **Kullanıcı yüklediği mp4/mp3 → STT** | metin | ✅ Temiz (dosya sende) | ✅ Yüksek | GPU | ❌ Yok | Elinde dosya varsa |
| **Browser extension** (kendi oturumunda panel okuma) | altyazı metni | ⚠️ Gri (otomatik çıkarım) | Orta | — | Düşük-orta (kullanıcı gibi görünür) | Yarı-manuel |

**NoteGPT vb. siteler** muhtemelen: timedtext + yt-dlp'yi **dönen residential proxy havuzuyla** ölçekte çağırıyor; ban riskini bir iş modeli olarak üstleniyorlar. Senin için sürdürülebilir değil.

**Kanal sahipliği ayrımı (en kritik kural):**
- **Kendi kanalın** → captions API (resmî, temiz). En iyi yol.
- **İzinli kanal** → sahibinden SRT/VTT export iste (temiz).
- **Başkasının kanalı** → temiz tek yol *manuel*; gerisi gri. Bu yüzden başkası için **metadata-temelli analizi** esas al.

---

## B) Pipeline mimarisi (video → [metin] → analiz)

### Hedef dosya yapısı (mevcut repoyu evrimleştir)
```
youtube-bilgi/
  config/
    .env               # YOUTUBE_API_KEY (gitignored)
    kanallar.yaml      # izlenen kanallar + kanal başına ayar (sayi, min_score...)
  src/
    youtube_api.py     # Data API: liste + metadata (videos.list zenginleştirme)
    db.py              # SQLite şema + erişim katmanı
    scorer.py          # metadata'dan "işime yarar" skoru (LLM veya kural)
    analyzer.py        # LLM analizi (Claude): özet/fikir/hook/yapı/uygulama
    transcript_fetcher.py # SEÇİCİ, yavaş, cache'li transkript (gri katman, opsiyonel)
    stt.py             # faster-whisper (kendi/izinli/yüklenen dosyalar)
    ratelimit.py       # token-bucket + jitter + backoff
    sync.py            # orkestrasyon (discover→score→[fetch]→analyze)
  data/
    videos.db          # SQLite (gitignore)
    audio/             # GEÇİCİ; iş bitince silinir (gitignore)
    transcripts/       # ham metin .txt (gitignore — gri + büyük)
  kanallar/<Kanal>/    # COMMIT edilen insan-okur çıktı
    basliklar.md
    videolar.json
    analiz.md          # ASIL DEĞER (özet + uygulanabilir fikirler)
```
> `.gitignore`: `data/`, `config/.env`. **Commit edilen** = `kanallar/**` (özet/analiz) ve `src/`.
> Ham transkriptleri repoya koymak gri alan + telif; özet/çıkarımları koymak daha temiz.

### Durum makinesi (her video)
```
discovered → scored → (skor<eşik ? skip_transcript) → queued → fetching
   → done | failed(retry) ;  paralelde:  analyzed(metadata) → analyzed(full)
```
- `transcript_status`: none | queued | fetching | done | failed | skip
- `analysis_status`: none | meta | full   (meta = sadece metadata'dan; full = transkriptle)

### SQLite şeması
```sql
CREATE TABLE channels (
  channel_id TEXT PRIMARY KEY,
  handle TEXT, title TEXT, uploads_playlist TEXT,
  last_synced_at TEXT
);
CREATE TABLE videos (
  video_id TEXT PRIMARY KEY,
  channel_id TEXT REFERENCES channels(channel_id),
  title TEXT, description TEXT, published_at TEXT,
  duration_sec INTEGER, view_count INTEGER, like_count INTEGER,
  thumbnail TEXT, url TEXT,
  score REAL, score_reason TEXT,
  transcript_status TEXT DEFAULT 'none',
  transcript_source TEXT,                 -- api|timedtext|manual|stt
  analysis_status TEXT DEFAULT 'none',
  attempts INTEGER DEFAULT 0,
  next_attempt_at TEXT,                    -- backoff için
  created_at TEXT, updated_at TEXT
);
CREATE TABLE transcripts (
  video_id TEXT PRIMARY KEY REFERENCES videos(video_id),
  lang TEXT, is_generated INTEGER, char_count INTEGER,
  text TEXT, source TEXT, created_at TEXT
);
CREATE TABLE summaries (
  video_id TEXT PRIMARY KEY REFERENCES videos(video_id),
  kisa_ozet TEXT, detayli_ozet TEXT, fikirler TEXT,
  hook TEXT, yapi TEXT, uygulama TEXT,
  kaynak TEXT,                            -- 'metadata' | 'transcript'
  model TEXT, created_at TEXT
);
CREATE TABLE fetch_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  video_id TEXT, ts TEXT, action TEXT, ok INTEGER, detail TEXT
);
```

### Cache / dedup / retry / temizlik kuralları
- **Dedup:** `video_id` PK. Sync'te `INSERT OR IGNORE`; var olan + değişmişse `UPDATE`.
- **Tekrar işleme yok:** `transcript_status='done'` veya `analysis_status` dolu → atla.
- **Retry/backoff:** başarısızda `attempts++`, `next_attempt_at = now + min(6h, 15dk * 2^attempts)`. `attempts>=5` → `failed` (artık deneme).
- **Tek tek:** transcript_fetcher aynı anda 1 video; istekler arası 30–120 sn **rastgele** bekleme.
- **Büyük dosya temizliği:** STT bitince `data/audio/<id>.wav` **silinir** (sadece metin saklanır).
- **Saklama:** ham metin `transcripts/` + DB; **özet** `summaries/` + `kanallar/<Kanal>/analiz.md`.

---

## C) Yerel STT (RTX 4080 12 GB; ileride RTX 6000 Pro)

| Çözüm | Hız | Kalite (TR+EN) | Not |
|-------|-----|----------------|-----|
| **faster-whisper** (CTranslate2) | ⭐ En iyi denge | large-v3 = en iyi | **Önerilen.** 12 GB'a rahat sığar |
| whisper.cpp (GGUF) | İyi (CPU/taşınabilir) | İyi | NVIDIA'da faster-whisper daha hızlı |
| openai-whisper (referans) | Yavaş | large-v3 = en iyi | Referans, üretim için değil |
| distil-whisper | Çok hızlı | **EN ağırlıklı, TR zayıf** | **Türkçe için KULLANMA** |
| large-v3-turbo | ~8x hızlı | TR'de hafif düşük | Hacim çoksa pratik |

**Öneri:** `faster-whisper` + **large-v3** (Türkçe kalitesi için), `compute_type="float16"`.
12 GB'da rahat çalışır; gerçek-zaman çarpanı yüksek (1 saatlik video birkaç dakikada).

```python
# src/stt.py — özet
from faster_whisper import WhisperModel
model = WhisperModel("large-v3", device="cuda", compute_type="float16")
segments, info = model.transcribe("data/audio/ID.wav",
                                  language=None,          # otomatik (tr/en)
                                  vad_filter=True, beam_size=5)
metin = " ".join(s.text for s in segments).strip()
```
Ses hazırlama (kendi/izinli dosyadan):
```bash
ffmpeg -i girdi.m4a -ar 16000 -ac 1 -c:a pcm_s16le data/audio/ID.wav
```
Kurulum: `pip install faster-whisper` + ffmpeg (`winget install Gyan.FFmpeg`).
RTX 6000 Pro gelince: `BatchedInferencePipeline` ile toplu/çok daha hızlı.

---

## D) Hukuki / ToS / ban risk modeli

- ✅ **Temiz:** Data API (metadata, kendi kanalının captions'ı), manuel paste, **senin yüklediğin** dosyadan STT, sahibinden alınan SRT.
- ⚠️ **Gri:** youtube-transcript-api (timedtext otomatik), browser-extension otomatik çıkarım. *Çalışır ama ToS'a aykırı; düşük hacim + cache + yavaş ile risk azalır, sıfırlanmaz.*
- ⛔ **Uzak dur:** Başkasının videolarını yt-dlp ile toplu indirip arşivleme; **proxy farm ile sınırsız** çekme; API'de kimlik gizleme/yanlış temsil (politika ihlali).

**Düşük hacim + cache'li + proxy'siz risk modeli:** Teknik ban riski *düşük* (çünkü metadata-öncelikli, transkript seçici/yavaş). ToS açısından transkript hâlâ gri — bu yüzden **minimumda tut**, asıl değeri metadata'dan üret.

---

## E) 3 seviyeli mimari

**1) En temiz / kurumsal**
Data API metadata + **sadece** (kendi/izinli) captions + başkası için manuel paste + STT yalnız senin dosyalarında. → %100 ToS-uyumlu. Dezavantaj: başkasının videosunda tam metin yok (metadata + manuel ile sınırlı).

**2) Pratik MVP (ÖNERİLEN)**
Data API metadata → **metadata-temelli LLM analizi** (transkriptSİZ değer) + en yüksek skorlu birkaç videoda transkript (manuel veya yavaş/cache'li timedtext). Cache + skor + kuyruk. → Güçlü değer, düşük risk.

**3) Teknik mümkün ama gri**
yt-dlp audio + yerel Whisper STT ile *her* videodan metin. Yavaş + cache + agresif değil. GPU'n var diye cazip ama ToS-gri + indirme riski. → Sadece kendi/izinli içerikte yap; başkasında *bilinçli risk*.

---

## F) NET KARAR — İlk kurulacak MVP

**Amaç:** "Mert Durmazer, Alex Hormozi gibi kanallardan işime uygulanabilir fikir çıkarmak."
Bunun için **birebir transkript ŞART DEĞİL** — bu tür kanallarda başlık = hook, açıklama = chapter/özet zaten yüksek sinyal. O yüzden:

### MVP = Seviye 2 (metadata-öncelikli), 4 adım
1. **Envanter (var):** Data API ile kanal→video + **videos.list ile zenginleştir** (tam açıklama, süre, view/like) → `videos.db` + `kanallar/<Kanal>/videolar.json`. Cache: aynı videoyu tekrar çekme.
2. **Skor:** başlık + açıklama → "işime yarar mı?" skoru (önce basit kural/LLM; 0–100).
3. **Analiz (asıl değer):** Claude, her kanal/segment için Türkçe `analiz.md`:
   - ana temalar / konu haritası
   - **uygulanabilir fikirler** (senin işine/ajan sistemine)
   - hook kalıpları + başlık formülleri + video yapısı
4. **Transkript = opsiyonel sonraki faz:** sadece en yüksek skorlu videolarda, manuel paste ya da (istersen) hotspot+yavaş timedtext; geldikçe `analiz.md` derinleşir.

### İlk somut komutlar
```bash
# (zaten yapıldı) liste:
python kanal_cek.py "@digitalacademyturkiye" --sayi 30 --liste
python kanal_cek.py "@AlexHormozi" --sayi 50 --liste
# eklenecek: videos.list zenginleştirme + SQLite + metadata analizi
```

### Yol haritası
- **Faz 1 (şimdi):** metadata zenginleştirme + SQLite + metadata-temelli `analiz.md`. (Ban-free, kalıcı.)
- **Faz 2:** skorlama + kanal başına `kanallar.yaml` + günlük/haftalık inkremental sync.
- **Faz 3:** seçici transkript (manuel/STT/yavaş) + transkriptli derin analiz.
- **Faz 4 (GPU gelince):** kendi/izinli içerikte yt-dlp+faster-whisper tam STT.

**Özet karar:** Proxy ile değil, **Data API + cache + metadata analizi** ile başla. Transkript sonra, seçici ve kontrollü eklenir.
