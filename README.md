# YouTube Konu Analiz Aracı

Bir konu verirsin → o konuda alakalı YouTube videolarını bulur → transcriptlerini
(indirmeden) çeker → bir LLM ile özetleyip Türkçe rapor verir.

## Mimari

```
[Konu]  → search.py  (YouTube Data API v3, arama)
   VEYA                    ↓
[Kanal] → channel.py (kanal videoları, ucuz)
                            ↓
                     precheck.py (altyazı var/yok — metni çekmeden)
                            ↓
                     transcript.py (youtube-transcript-api, indirmesiz)
                            ↓
                     synthesize.py (lokal vLLM VEYA Claude API)
                            ↓
                     Türkçe rapor (ekran + output/*.md)
```

Tüm akışı `main.py` orkestre eder.

## Kurulum

### 1. Bağımlılıklar
```bash
pip install -r requirements.txt
```

### 2. YouTube API anahtarı (arama için zorunlu)
1. https://console.cloud.google.com → yeni proje oluştur
2. "APIs & Services" → "Library" → "YouTube Data API v3" → **Enable**
3. "APIs & Services" → "Credentials" → "Create Credentials" → "API key"
4. Anahtarı kopyala

### 3. Yapılandırma
```bash
cp config/.env.ornek config/.env
# config/.env dosyasını aç, YOUTUBE_API_KEY satırına anahtarı yapıştır
```

## Kullanım

### Mod 1 — Konu araması
```bash
# Önce altyazı durumunu tara (transcript çekmeden, hızlı)
python src/main.py "yerelde çalışan yapay zeka" --sayi 100 --sadece-kontrol

# Tam çalıştır
python src/main.py "yerelde çalışan yapay zeka" --sayi 100
```

### Mod 2 — Kanaldan çekme (kota açısından çok ucuz)
```bash
# Bir kanalın son 1 yıllık videoları (handle ile)
python src/main.py --kanal "@kanaladi" --gun 365

# URL veya kanal ID de olur
python src/main.py --kanal "https://www.youtube.com/@kanaladi" --gun 365
python src/main.py --kanal "UCxxxxxxxxxxxxxxxxxxxxxx" --gun 365

# Kanaldan en fazla 50 video, önce ön-kontrol
python src/main.py --kanal "@kanaladi" --gun 365 --sayi 50 --sadece-kontrol
```

Kanal girdisi olarak @handle, tam URL veya kanal ID verebilirsin. Düz kanal
adı da çalışır ama 100 birim kota harcar (arama gerektirir); @handle ücretsizdir.

### Önerilen iş akışı
1. `--sadece-kontrol` ile tara → kaçında altyazı var gör
2. Çoğunda varsa → `--sadece-kontrol` olmadan tam çalıştır
3. Altyazısı olmayan azınlık için → Whisper fallback (henüz placeholder)

## Model seçimi

`config/.env` içindeki `MODEL_SAGLAYICI`:
- `lokal` → vLLM sunucun (GPU geldiğinde). `VLLM_URL` ve `VLLM_MODEL` ayarla.
- `claude` → Anthropic API. `ANTHROPIC_API_KEY` ayarla.

Tek satır değiştirerek geçiş yaparsın.

## Önemli notlar

- **IP engeli:** `transcript.py` datacenter/sunucu IP'lerinden 403/IpBlocked
  alabilir. Ev/ofis internet bağlantısından çalışır. Sunucuya taşırsan proxy gerekir.
- **Whisper fallback:** Altyazısı olmayan videolar için ses indirip lokal Whisper
  ile çevirme adımı `transcript.py` içinde PLACEHOLDER olarak duruyor. İndirme
  riski kararı verilince etkinleştirilecek.
- **Kota:** YouTube Data API günde 10.000 birim ücretsiz (~100 arama/gün).
- **Güvenlik:** `config/.env` ve `output/` `.gitignore`'da; anahtarlar repoya gitmez.

## Sonraki adımlar (opsiyonel)

1. Whisper fallback'i aktifleştir (indirme kararına bağlı)
2. Aynı konuda periyodik tarama (cron/zamanlanmış görev)
3. Birden fazla konuyu tek seferde işleme
4. Rapor formatını zenginleştirme (zaman damgalı alıntılar, vb.)
