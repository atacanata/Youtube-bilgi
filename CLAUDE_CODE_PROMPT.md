# Claude Code İş Paketi Promptu — YouTube Konu & Kanal Analiz Aracı

> Bu promptu Claude Code'a (terminal) ver. Referans kod sağlanan arşivde mevcut;
> arşivi de Claude Code'a verebilirsin. Çalışma dizinini kendi sistemine göre düzenle.

---

## İş paketi adı
YouTube Analiz Aracı — Konu araması + Kanal modu + altyazı ön-kontrol (indirmesiz transcript çekirdeği)

## Amaç
Bir konu yazıldığında VEYA bir kanal verildiğinde, ilgili videoları bulup önce altyazı durumlarını tarayan, sonra altyazıları indirmeden çekip bir LLM ile özetleyerek Türkçe rapor üreten komut satırı aracını kurmak.

## Bağlam
- Sistem altı modülden oluşur:
  1. search.py    — YouTube Data API v3 ile konu araması (meta veri; API'nin açıkça izinli kullanımı)
  2. channel.py   — kanal adı/@handle/URL/ID'den videoları listeler (playlistItems, kota açısından ucuz)
  3. precheck.py  — transcript çekmeden altyazı var/yok taraması (100+ video öncesi ön-kontrol)
  4. transcript.py— youtube-transcript-api ile altyazı çekme (indirmesiz)
  5. synthesize.py— vLLM veya Claude API arası .env ile geçişli özetleme
  6. main.py      — iki modu (konu / --kanal) orkestre eden CLI
- main.py mod seçimi: pozisyonel `konu` argümanı VEYA `--kanal` bayrağı. Biri zorunlu.
- Pipeline'ın precheck/transcript/synthesize kısmı her iki modda ORTAKTIR.
- Transcript çekme resmi API değildir (gri alan); datacenter IP'lerinde 403/IpBlocked verir, ev/ofis bağlantısında çalışır.
- İndirme (yt-dlp) ve Whisper fallback KAPSAM DIŞI; transcript.py içinde placeholder olarak durur. Risk kararı henüz verilmedi.
- Sentez modeli .env'deki MODEL_SAGLAYICI ile seçilir (varsayılan "lokal" = vLLM). GPU henüz gelmediği için ilk test "claude" ile veya transcript adımına kadar yapılabilir.

## Çalışma dizini + exact Python path
- Çalışma dizini: `C:\Users\Atacan Ata\Desktop\youtube-arac`
- Python exact path: `C:\Users\Atacan Ata\Desktop\youtube-arac\venv\Scripts\python.exe`
  (venv yoksa önce oluştur: `python -m venv venv`)

## Yapılacaklar
1. Çalışma dizininde `venv` sanal ortamı oluştur.
2. requirements.txt kur: youtube-transcript-api>=1.2.0, google-api-python-client>=2.0.0, python-dotenv>=1.0.0, requests>=2.31.0
3. Klasör yapısını oluştur: `src/`, `config/`, `output/`
4. Altı modülü yaz: search.py, channel.py, precheck.py, transcript.py, synthesize.py, main.py (referans arşivde mevcut).
5. config/.env.ornek, .gitignore, README.md oluştur (.env ve output/ ignore edilmeli).
6. Doğrula:
   - `python -c "import search, channel, precheck, transcript, synthesize, main"` (6 modül import)
   - `python src/main.py --help` çalışıyor, hem `konu` hem `--kanal` görünüyor
   - `python src/main.py` (argümansız) düzgün hata veriyor
7. Türkçe kurulum durum raporu ver.

## Yapılmayacaklar
- yt-dlp KURULMAYACAK, ses/video indirme kodu YAZILMAYACAK.
- Whisper entegrasyonu YAPILMAYACAK (transcript.py'deki placeholder olduğu gibi kalacak).
- Gerçek YouTube API çağrısı ile canlı test YAPILMAYACAK (API anahtarı kullanıcıda; kullanıcı kendi test edecek).
- Periyodik/zamanlanmış görev (cron) KURULMAYACAK; sadece tek seferlik komut.
- API anahtarları koda veya .env.ornek'e YAZILMAYACAK.
- Mevcut iki modun (konu/kanal) dışında yeni mod EKLENMEYECEK.

## Çıktılar
- Çalışan klasör yapısı ve altı Python modülü.
- requirements.txt, config/.env.ornek, .gitignore, README.md.
- `python src/main.py --help` başarılı çıktısı (--kanal ve --sadece-kontrol bayrakları dahil).
- Türkçe kurulum durum raporu.

## Kurallar
- Tahmin yürütme. youtube-transcript-api arayüzünden emin değilsen önce doğrula: sürüm 1.2.x'te YouTubeTranscriptApi() örneklenir ve `.fetch()` / `.list()` metodları kullanılır; eski static `get_transcript` YOKTUR.
- Hata alınca dur, raporla, kullanıcıya sor; sessizce devam etme.
- Tüm raporlama Türkçe.
- Kapsamı dar tut; bir sonraki adıma (indirme, Whisper, periyodik tarama) taşma olmasın.
- Kod veya tasarım değişikliği gerekiyorsa önce kullanıcı onayı al.

## Kullanıcının kurulum sonrası yapacakları (Claude Code yapmayacak)
1. Google Cloud Console'dan YouTube Data API v3 anahtarı al, config/.env'e koy.
2. Kanal modu ön-kontrol örneği:
   `python src/main.py --kanal "@kanaladi" --gun 365 --sadece-kontrol`
3. Kaç videoda altyazı olduğunu gördükten sonra --sadece-kontrol olmadan tam çalıştır.
4. Sentez için: GPU gelince MODEL_SAGLAYICI=lokal (vLLM); öncesinde test için =claude.
