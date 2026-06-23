# YouTube → MP3 → Yerel Metin

Bir **konu başlığı** verirsin → YouTube'da arar → bulunan videoları **MP3'e**
indirir → MP3'leri **yerelde faster-whisper (GPU)** ile **metne** çevirir.

> Bu araç, repodaki eski **altyazı/transcript çekme** hattından **tamamen
> bağımsızdır**. Altyazıya hiç dokunmaz; sesi indirip yerelde STT yapar.

## Akış
```
[Konu başlığı]
      │  arama.py — yt-dlp ytsearch (API anahtarı GEREKMEZ)
      ▼
[Video listesi]
      │  indir.py — yt-dlp + ffmpeg
      ▼
[MP3]  (ciktilar/<konu>/mp3/ — saklanır)
      │  stt.py — faster-whisper (GPU), model bir kez yüklenir
      ▼
[Metin]  (ciktilar/<konu>/metin/*.txt + tum_metinler.md)
```

## Kurulum

### 1. Python bağımlılıkları
```bash
pip install -r youtube_mp3_metin/requirements.txt
```

### 2. ffmpeg (MP3 dönüşümü için ZORUNLU)
```bash
# Linux
sudo apt install ffmpeg
# Windows
winget install Gyan.FFmpeg
# macOS
brew install ffmpeg
```

### 3. GPU (faster-whisper için)
- NVIDIA GPU + CUDA + cuDNN kurulu olmalı.
- İlk çalıştırmada Whisper modeli (~1.5 GB) otomatik iner.
- GPU yoksa CPU modu: `--cihaz cpu --compute int8` (yavaş ama çalışır).

## Kullanım
```bash
cd youtube_mp3_metin

# Varsayılan: 10 video, dil otomatik, GPU
python cikar.py "konu başlığı"

# Türkçe içerik, 5 video
python cikar.py "konu başlığı" --sayi 5 --dil tr

# Sadece MP3 indir (metne çevirme)
python cikar.py "konu başlığı" --sadece-indir

# GPU yoksa CPU'da
python cikar.py "konu başlığı" --cihaz cpu --compute int8

# Büyük işlerde nazik ol (videolar arası bekleme)
python cikar.py "konu başlığı" --sayi 20 --gecikme 8
```

### Parametreler
| Bayrak | Varsayılan | Açıklama |
|--------|-----------|----------|
| `--sayi` | 10 | İşlenecek video sayısı |
| `--dil` | otomatik | STT dili (`tr`, `en`...). Boşsa Whisper algılar |
| `--model` | `large-v3-turbo` | faster-whisper modeli |
| `--cihaz` | `cuda` | `cuda` veya `cpu` |
| `--compute` | `int8_float16` | GPU: `int8_float16`/`float16` · CPU: `int8` |
| `--sadece-indir` | — | Sadece MP3, STT yok |
| `--gecikme` | 0 | Videolar arası bekleme (sn) |

## Çıktı
```
ciktilar/<konu_slug>/
├── mp3/<video_id>.mp3        # indirilen sesler (saklanır)
├── metin/<video_id>.txt      # her video için metin
├── tum_metinler.md           # hepsi tek okunaklı dosyada
└── videolar.json             # meta + dosya yolları (makine için)
```
`ciktilar/` `.gitignore`'dadır — MP3/metin repoya gitmez.

## Notlar
- **Onbellek:** MP3 veya metin zaten varsa tekrar indirilmez/çevrilmez. Arac
  yeniden çalıştırılabilir; kaldığı yerden devam eder.
- **ToS:** yt-dlp ile ses indirme gri alandır; kişisel/yerel STT amaçlı, tek tek,
  yeniden-yayın yok varsayımıyla kullan.
- **Hız:** Model bir kez yüklenir, tüm videolarda tekrar kullanılır.
- **CPU fallback yok:** GPU hatasında sessizce CPU'ya düşmez; net Türkçe hata
  verir. CPU istiyorsan açıkça `--cihaz cpu` ver.
