# YouTube Research Agent — Sprint 1 (MVP iskeleti)

Belirli kanallardan **resmî** YouTube Data API ile video metadata çeker, SQLite'a
idempotent kaydeder, skorlar, transcript için sağlam bir provenance altyapısı kurar
ve transcript varsa analiz/prompt üretir.

> Bu sprintte **yt-dlp / video indirme / Whisper STT YOK** — sadece statü ve ileride
> bağlanacak hook'lar var (bkz. Sprint 2).

## Mimari ayrım (önemli)
- `videos.status` = **süreç / state machine** (videonun hangi aşamada olduğu).
- `transcripts.source_type` = **provenance** (metnin nereden geldiği).
- Metadata-only durum **video.status** ile temsil edilir; `transcripts` satırı yalnızca
  gerçek metin varsa oluşur. (Yani "metadata-only" bir source_type DEĞİLDİR.)

## Kurulum
```bash
# repo kökündeki venv kullanılabilir veya yeni venv:
pip install -r youtube_research_agent/requirements.txt
# STT (Sprint 4) icin ek: Windows'ta ffmpeg gerekli -> winget install Gyan.FFmpeg  (veya: choco install ffmpeg)
# faster-whisper GPU icin CUDA + cuDNN kurulu olmali; ilk calismada ~1.5GB model iner.

cd youtube_research_agent
cp .env.example .env        # sonra .env içine anahtarı yaz
```

`.env` içeriği:
```
YOUTUBE_API_KEY=...        # ZORUNLU (Data API v3)
ANTHROPIC_API_KEY=         # opsiyonel; varsa analyze gerçek API çağırır, yoksa prompt üretir
```
`.env` git'e gitmez (`.gitignore`).

## Kanal ID nereye yazılır?
`config.yaml` → `channels[].channel_id`. Hazır gelen iki kanal:
- `mert` → `UCCtwhjWO0NGOAhWOgv3DKFA`
- `hormozi` → `UCUyDOdBWhC1MCxEjC46d-zw`

**Kanal ID bulma** (3 yol):
1. Kanal sayfası → "Paylaş" / kaynak kodda `UC...` (24 haneli, `UC` ile başlar).
2. `https://www.youtube.com/@handle` sayfasının HTML'inde `"channelId":"UC..."`.
3. Data API: `channels.list(part=id, forHandle=HANDLE)` (1 quota).

> Normal `sync` akışı `search.list` KULLANMAZ (pahalı). ID config'te verilir.

## Komutlar
```bash
python main.py init-db
python main.py sync --channel mert --limit 30
python main.py sync --all --limit 30
python main.py score
python main.py score --channel mert
python main.py list --status NEEDS_TRANSCRIPT
python main.py list --status NEEDS_MANUAL_TRANSCRIPT
python main.py import-transcript --video-id VIDEO_ID --file transcript.txt --source MANUAL_TRANSCRIPT --lang tr
python main.py captions --min-score 7 --limit 5     # gri/opsiyonel; config ile kapalı
python main.py analyze --limit 10
python main.py report --channel mert
```

## Akış
```
sync (Data API metadata) → score → [transcript: import/captions] → analyze → report
   DISCOVERED            → NEEDS_TRANSCRIPT/SKIPPED → TRANSCRIBED → (ANALYZED) → rapor
```

## Transcript kaynakları (source_type) ve temizlik
| source_type | Nasıl | Temizlik |
|-------------|-------|----------|
| `MANUAL_TRANSCRIPT` | elle yapıştırılan dosya | ✅ temiz |
| `USER_UPLOADED_AUDIO` / `AUTHORIZED_VIDEO` | kendi/izinli içerik | ✅ temiz |
| `AUDIO_STT` | (Sprint 2) yt-dlp+Whisper | ⚠️ kendi/izinli içerikte |
| `CAPTION_TRANSCRIPT` | youtube-transcript-api | ⚠️ gri; varsayılan KAPALI |

`captions` hattı `config.settings.allow_unofficial_captions=false` iken çalışmaz; proxy/cookie/auth-bypass yoktur.

## Analiz modu
- `ANTHROPIC_API_KEY` yoksa → `data/analyses/{video_id}_prompt.md` üretilir (elle Claude'a verilir).
- Varsa → `_call_claude_api` iskeleti çağrılır (bu sprintte çıktı `detailed_summary`'e konur).
Prompt şablonu: `prompts/analysis_prompt.md` (8 başlık).

## Bilinen eksikler / sınırlar
- captions hattı, IP rate-limit'e tabidir (gri). Temiz yol: `import-transcript`.
- analyze API modu ham çıktıyı tek alana yazar; 8 başlığa ayrıştırma Sprint 2.
- yt-dlp / STT yok (Sprint 2). `NEEDS_AUDIO_STT` statüsü ileride kullanılacak.
- `data/` (db, transcripts, analyses, reports) git'e gitmez; çıktılar yerel.

## Sprint 2 önerisi
`NEEDS_AUDIO_STT` durumundaki (kendi/izinli) videolar için **yt-dlp + ffmpeg + faster-whisper**
fallback'i: ses indir → 16kHz WAV → `large-v3` STT → `source_type=AUDIO_STT` → analyze.
Ayrıca analyze çıktısını 8 başlığa ayrıştırıp `analyses` alanlarına yazmak.
