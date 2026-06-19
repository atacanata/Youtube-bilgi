# Kanal: Alex Ziskind — Son 10 Video Analizi

Tarih: 20260619_192753
Kanal: Alex Ziskind (`UCajiMK_CY9icRhLepS8_3ug`)
Sentez: Claude Code (yerel sentez; özetleme API'si kullanılmadı)
Kaynak: Altyazılar `youtube-transcript-api` ile indirmeden çekildi (10/10 başarılı, ~79.500 karakter)

## Analiz Edilen Videolar

1. [This Is What Happens When You CRUSH An AI Video Model — *kısa*](https://www.youtube.com/watch?v=nKZvMrlaPbM) — Alex Ziskind (19 Haz 2026)
2. [This Is What Happens When You CRUSH An AI Video Model — *tam*](https://www.youtube.com/watch?v=octq1gJ0dkM) — Alex Ziskind (18 Haz 2026)
3. [AMD's Strix Successor Just Caught the M4 Pro — *kısa*](https://www.youtube.com/watch?v=ZC-ieyZPMhs) — Alex Ziskind (16 Haz 2026)
4. [Three months wrong about why my 4-node AMD cluster was slow](https://www.youtube.com/watch?v=PMQGT5F6rzo) — Alex Ziskind (16 Haz 2026)
5. [AMD's Strix Successor Just Caught the M4 Pro — *tam*](https://www.youtube.com/watch?v=sxMSKyrnZH4) — Alex Ziskind (12 Haz 2026)
6. [Everything looks fine at 4-bit](https://www.youtube.com/watch?v=GjQFRXaSChM) — Alex Ziskind (9 Haz 2026)
7. [My LLM Hoarding Got Out of Hand… So I Built This](https://www.youtube.com/watch?v=YMoDxVlUniI) — Alex Ziskind (4 Haz 2026)
8. [This MacBook Pro Makes Me Feel Stupid](https://www.youtube.com/watch?v=6KkjdQxqF0k) — Alex Ziskind (3 Haz 2026)
9. [RTX Spark Is Already Making People Mad](https://www.youtube.com/watch?v=VGVwOI2gcF4) — Alex Ziskind (2 Haz 2026)
10. [Intel just CRUSHED Nvidia & AMD GPU pricing](https://www.youtube.com/watch?v=J2jRWNSrNDQ) — Alex Ziskind (31 May 2026)

> **Not:** Bu "son 10 yükleme" içinde iki konu hem kısa (Shorts) hem tam sürümle yer alıyor: [Video 1]≈[Video 2] (AI video modeli kuantizasyonu) ve [Video 3]≈[Video 5] (Beelink SER 10). Yani efektif olarak ~8 farklı konu var. Kısa sürümler (1–2 bin karakter) tam videoların özeti niteliğinde.

---

## Rapor

### 1. Ana Temalar ve Ortak Noktalar

Kanalın tamamı tek bir eksende dönüyor: **yapay zeka modellerini kendi donanımında (yerelde) çalıştırmak** — ve bunun donanım/yazılım gerçeklerini ölçümle göstermek.

- **Kuantizasyon (modeli küçültmek) merkezde.** [Video 1], [Video 2] ve [Video 6] doğrudan bu konuda; [Video 5], [Video 7], [Video 8] de Q4/4-bit gibi kuantize sürümleri varsayıyor. Tekrarlayan tespit: yerelde model çalıştıran herkes aslında *kuantize* model çalıştırıyor ama bunun bedelinin ne olduğu kullanıcıya hiç anlatılmıyor ([Video 2], [Video 6]).
- **Birleşik bellek (unified memory) işi mümkün kılan şey.** [Video 5]'te AMD'nin iGPU'su "4 GB" görünmesine rağmen UMA sayesinde 8,37 GB'lık modeli yüklüyor (Windows sistem RAM'inden sessizce pay veriyor). [Video 8]'de M5 Max'in 128 GB'ı, başka hiçbir makinede var olamayan 122B'lik modeli çalıştırıyor. [Video 4] (Strix Halo 128 GB) ve [Video 9] (RTX Spark 128 GB) aynı mantığa dayanıyor.
- **Donanım karşılaştırması bir spor dalı:** Apple Silicon (M4/M5 Pro/Max), AMD (Strix Halo, Gorgon Point), Nvidia (DGX/RTX Spark) ve Intel (Arc Pro B50/B70) sürekli kıyaslanıyor.
- **NPU "atıl kapasite".** [Video 3] ve [Video 5]: AMD 2 yıldır kutuya NPU koyuyor ama kimse ölçmüyor; doğru iş bölümü → NPU "prefill" (uzun bağlam), iGPU "decode" (akışlı sohbet) için.
- **Kurulum tuzakları işin yarısı.** [Video 5]: Windows'ta Ollama varsayılan olarak yanlış çipi (CPU) kullanıyor — Vulkan bayrağı şart; Windows Defender derlemeyi 217 sn'den 161 sn'ye yavaşlatmış. [Video 7]: model dosyalarını yönetmek için kendi açık kaynak aracı **Model Shelf**.
- Sürekli geçen araç/model adları: Qwen, DeepSeek-R1, Gemma; çalıştırma için llama.cpp, MLX, vLLM, Ollama, LM Studio, Lemonade Server.

### 2. Çelişen / Sezgiye Aykırı Bulgular

- **"Daha çok bit = daha iyi" YANLIŞ.** En güçlü tez [Video 1] ve [Video 2]'den: Aynı 8 bit olmasına rağmen **FP8 formatı, Q8 (INT8)'den belirgin kötü** — temel modelden ortalama iki kat daha fazla sapıyor. Hatta FP8'de basit bir komutta **kırmızı araba geri geri gidiyor** (başka hiçbir kuantizasyonda olmayan bir hata). Slogan: *"Format, bit sayısından daha çok iş yapar."* Donanım hızlandırması olan FP8'in "geleceğin formatı" olduğu beklentisini çürütüyor.
- **Sorun her zaman kuantizasyon değil.** [Video 6]: Hiç kuantize edilmemiş (BF16) 32B model bile ay yüzeyi sorusunda hata yaptı (John Young'ın "iki kez yürüdüğü" — yanlış). Yani halüsinasyon tam hassasiyette de var; suçu hep küçültmeye atmak yanlış.
- **Çok GPU her zaman hızlandırmaz.** [Video 10]: İki Intel B70 ile prompt işleme ikiye katlanıyor (9.281 → 18.170 t/s) ama token üretimi *düşüyor* (72 → 52 t/s), çünkü GPU'lar arası PCIe bağı 63 GB/s ile sınırlı. Küçük modellerde çok GPU zarar verebilir.
- **Multimodalde ses, görüntüden önce bozulur.** [Video 2]: Sesli model LTX'te Q4'e inerken ses kalitesi videodan çok daha hızlı çöküyor — izleyici kötü sesi anında fark ettiği için bu daha kritik.
- **Apple mı AMD mi?** [Video 5]: AMD'nin yeni Gorgon Point'i çok çekirdek/throughput'ta M4 Pro'yu *yakaladı* (Geekbench multi'de %1 fark, V8 TypeScript'te SER 9'a göre +%65). Ama Apple tek çekirdekte ve IO-yoğun gerçek derlemelerde (Umbraco) hâlâ önde. Yani "yakaladı" başlığı throughput için doğru, her şey için değil.
- **"Windows AI için kötü" vs Alex'in tezi.** [Video 9]: İnternet RTX Spark'ın Windows'la gelmesine kızarken Alex tam tersini savunuyor — "Windows-önce" en akıllı hamle, çünkü zor problem Windows-on-ARM ekosistemini kurmak; Linux-on-ARM zaten çözülmüş ve sonradan miras alacak.

### 3. Gerçekten Yeni Olan Ne Var?

- **FP8 vs Q8 format bulgusu** ([Video 1]/[Video 2]) — somut, ölçülmüş ve çoğu kullanıcının bilmediği bir sonuç; üstelik iki ayrı mimaride (WAN 2.2, LTX 2.3) tekrarlanıyor.
- **Model Shelf** ([Video 7]) — Alex'in kendi açık kaynak aracı: model dosyalarını disklerde temiz, okunaklı yolda tutuyor; canlı Hugging Face hub'ını "doğru kaynak" kabul ediyor (modelin eski hafızasına güvenmiyor); arka planda demon/MCP yok, sadece JSON döken bir kabuk komutu. **Claude Code ile bir "skill" olarak entegre** — kurulduğu an Claude Code modeli nasıl bulacağını biliyor. (Bizim projemiz açısından dikkat çekici: aynı ekosistem.)
- **Minisforum'u kendi reklamında geçmek** ([Video 4]): 4 düğümlü Strix Halo kümesinde, DeepSeek-R1'i vLLM tensor paralelliğiyle 6,23 t/s — üreticinin kendi videosundaki 5,94 t/s'nin üstünde. (3 ay süren çoğu sorunun "yanlış yerde sorun aramak" olduğunu itiraf ediyor.)
- **"4 GB" iGPU'da 14B model** ([Video 5]) — UMA ile 8+ GB ağırlık yüklenebiliyor; aynı çip SER 9'da da olduğu için "donanımın iyi, yazılımını güncelle" mesajı.
- **RTX Spark = DGX Spark'ın yeniden paketlenmişi** ([Video 9]): yeni çip değil, Blackwell GPU + MediaTek CPU; N1 vs N1X = binlenmiş (tam vs kırpılmış) silikon; tüketici sürümü pahalı ConnectX-7 yerine sade 10-gig ethernet ile daha ucuz olacak.
- **Intel Arc Pro B70** ([Video 10]): 32 GB VRAM, 1.000 doların altında; 4 tanesi = 128 GB VRAM — yerel AI için fiyat/performans iddiası.

### 4. Hiç İzlememiş Birine Net Özet

Alex Ziskind, "yapay zekayı bulutta değil, masandaki makinede çalıştırmak" konusunu işleyen bir geliştirici. Son 10 videosunun ana mesajları:

1. **Yerel model çalıştırıyorsan kuantize çalıştırıyorsun** — ve formatın seçimi (FP8 mı, Q8 mi) çoğu zaman bit sayısından daha önemli. Pratik tavsiye: aksini gerektiren bir sebep yoksa **Q4** kullan; sesli/videolu modelde çıktıyı *dinle*, çünkü ses önce bozulur.
2. **Bellek miktarı, hangi modelleri çalıştırabileceğini belirler.** 128 GB birleşik bellek (Apple M5 Max, AMD Strix Halo, Nvidia RTX Spark) "hız"dan çok "o modelin makinende var olabilmesi" demek.
3. **Donanım yarışı kızıştı:** AMD'nin yeni mini PC'leri throughput'ta Apple'ı yakaladı; Intel ucuz çok-VRAM'lı kartlarla giriyor; Nvidia tüketiciye 128 GB'lık ARM tabanlı kutu getiriyor. Tek bir "kazanan" yok; iş yüküne göre değişiyor.
4. **Asıl zorluk yazılım/kurulum:** doğru çipi kullandırtmak (Ollama+Vulkan, NPU), modelleri düzenli tutmak (kendi yaptığı **Model Shelf** aracı, Claude Code'a entegre).

Tek videoda geçen ve genellenemeyecek noktalar: ay yüzeyi olgu testi yalnız [Video 6]'da; Intel çok-GPU PCIe darboğazı yalnız [Video 10]'da; "Windows-önce" tezi yalnız [Video 9]'da bir görüş olarak sunuluyor (kanıt değil, yorum).

---

### Ek Notlar (şeffaflık)

- **Reklam/sponsor bölümleri** transkriptlerde mevcut ve özet dışı tutuldu: Plaude NotePin S ([Video 2]), Chat LLM Teams/Abacus AI ([Video 5], [Video 9]), Acasis TB504 ([Video 7]). Bunlar içerik değil, sponsorluk.
- Otomatik altyazılar bazı özel adları bozmuş olabilir (ör. "Plaude"→Plaud, "Quen/Gwent"→Qwen, "Juan"→WAN, "MPU"→NPU, "OpenClaw"→OpenWebUI?, "B link"→Beelink). Sayılar ve teknik iddialar transkriptteki haliyle aktarılmıştır.
