# Dikey/Şarjlı Süpürge — Ürün İçgörü Analizi (JSON çıktı)

Aşağıdaki **DİKEY (kablosuz/şarjlı el) süpürge** incelemesi videosunun transkriptini analiz et.
**SADECE transkriptte geçenleri** yaz; yorum katma, **UYDURMA**. Bilgi yoksa o alanı boş liste bırak.

⚠️ Bu bir **DİKEY süpürgedir, robot süpürge DEĞİL.** Şu kriterlere odaklan:
- **saç dolanması (KRİTİK)**, emiş gücü, batarya süresi, ağırlık/denge,
  toz haznesi (kapasite/boşaltma kolaylığı), filtre (HEPA/yıkanabilir),
  başlık çeşitliliği (motorlu/mini/yumuşak rulo/aydınlatmalı), gürültü.
- Robot süpürge kriterlerini **DAHİL ETME**: navigasyon, harita, şarj/temizlik istasyonu,
  eşik aşma, paspaslama, otomatik toz boşaltma istasyonu.

- Ürün: {{product}}
- Kategori: {{category}}
- Başlık: {{title}}
- URL: {{url}}

Çıktıyı **GEÇERLİ JSON** olarak ver (değerler Türkçe, tam olarak şu şema):

```json
{
  "artilar": ["videoda övülen somut özellikler"],
  "eksiler": ["videoda eleştirilen noktalar"],
  "sorunlar": ["bahsedilen arıza/şikayet (varsa)"],
  "rakip_karsilastirma": ["hangi modelle kıyaslandı ve sonuç ne"],
  "kriterler": ["değinilenler: saç dolanması, emiş gücü, batarya süresi, ağırlık, toz haznesi, filtre, başlık çeşitliliği, gürültü"],
  "satin_alma_etkenleri": ["satın alma kararını etkileyen noktalar"],
  "guvenilirlik": "reklam/sponsor sinyali var mı; yoksa 'belirtilmemiş'"
}
```

Yalnızca JSON döndür, başka metin ekleme.

---
TRANSKRİPT:
{{transcript}}
