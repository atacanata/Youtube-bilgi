# Ürün İçgörü Analizi (JSON çıktı)

Aşağıdaki **ürün incelemesi** videosunun transkriptini analiz et. Görev: üründen
çıkan istihbaratı çıkarmak. **SADECE transkriptte geçenleri** yaz; yorum katma,
**UYDURMA**. Bir bilgi videoda yoksa o alanı boş liste bırak veya "videoda
belirtilmemiş" yaz.

- Ürün: {{product}}
- Kategori: {{category}}
- Başlık: {{title}}
- URL: {{url}}

Çıktıyı **GEÇERLİ JSON** olarak ver (değerler Türkçe, tam olarak şu şema):

```json
{
  "artilar": ["videoda övülen somut özellikler"],
  "eksiler": ["videoda eleştirilen noktalar"],
  "sorunlar": ["bahsedilen arıza/sorun/şikayet (varsa)"],
  "rakip_karsilastirma": ["hangi modelle kıyaslandı ve sonuç ne"],
  "kriterler": ["değinilen kriterler: emiş, paspas, saç dolanması, ses, batarya, navigasyon..."],
  "satin_alma_etkenleri": ["satın alma kararını etkileyen noktalar"],
  "guvenilirlik": "reklam/sponsor sinyali var mı; yoksa 'belirtilmemiş'"
}
```

Yalnızca JSON döndür, başka metin ekleme.

---
TRANSKRİPT:
{{transcript}}
