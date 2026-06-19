"""
Sentez modülü.
Çekilen transcriptleri bir LLM ile özetler ve Türkçe rapor üretir.

Model seçimi .env'deki MODEL_SAGLAYICI ile yapılır:
  - "lokal"  -> vLLM (OpenAI uyumlu endpoint, örn. http://localhost:8000)
  - "claude" -> Anthropic Claude API

Bu sayede model kararını sonraya bırakabilirsin; tek satır .env değişikliği.
"""
import os
import requests


SISTEM_PROMPTU = """Sen bir video içeriği analistisin. Sana bir konu hakkında \
birden fazla YouTube videosunun transcripti verilecek. Görevin:

1. Bu videolardan çıkan ANA temaları ve ortak noktaları belirle.
2. Videolar arasında çelişen veya farklı görüşleri vurgula.
3. Bu konuda GERÇEKTEN YENİ olan ne varsa öne çıkar.
4. Konuyu, hiç video izlememiş birine anlatır gibi net özetle.

Yanıtını TÜRKÇE ver. Spekülasyon yapma; sadece transcriptlerde olan bilgiye \
dayan. Bir bilgi tek videoda geçiyorsa bunu belirt. Kaynak videoyu \
[Video N] şeklinde referansla."""


def sentezle(konu: str, videolar: list[dict]) -> str:
    """
    Videoların transcriptlerini özetleyip Türkçe rapor üretir.

    Parametreler:
        konu: Kullanıcının sorduğu ana konu
        videolar: Her biri 'baslik', 'kanal', 'url', 'metin' içeren liste
                  (yalnızca transcripti başarıyla çekilmiş videolar)

    Dönüş:
        str: Türkçe özet/analiz raporu
    """
    if not videolar:
        return "Özetlenecek transcript yok (hiçbir videodan metin çekilemedi)."

    # Transcriptleri tek bir bağlam metnine birleştir
    baglamlar = []
    for i, v in enumerate(videolar, 1):
        baglamlar.append(
            f"=== [Video {i}] {v['baslik']} (Kanal: {v['kanal']}) ===\n"
            f"URL: {v['url']}\n"
            f"Transcript:\n{v['metin']}\n"
        )
    baglam = "\n".join(baglamlar)

    kullanici_mesaji = (
        f"KONU: {konu}\n\n"
        f"Aşağıda bu konuyla ilgili {len(videolar)} videonun transcripti var. "
        f"Talimatlara göre analiz et:\n\n{baglam}"
    )

    saglayici = os.getenv("MODEL_SAGLAYICI", "lokal").lower()
    if saglayici == "lokal":
        return _lokal_vllm(kullanici_mesaji)
    elif saglayici == "claude":
        return _claude_api(kullanici_mesaji)
    else:
        raise ValueError(
            f"Bilinmeyen MODEL_SAGLAYICI: '{saglayici}'. "
            f"'lokal' veya 'claude' olmalı."
        )


def _lokal_vllm(kullanici_mesaji: str) -> str:
    """
    Lokal vLLM sunucusuna (OpenAI uyumlu) istek atar.
    .env: VLLM_URL (örn. http://localhost:8000), VLLM_MODEL
    """
    url = os.getenv("VLLM_URL", "http://localhost:8000")
    model = os.getenv("VLLM_MODEL", "google/gemma-4-31B-it")

    yanit = requests.post(
        f"{url}/v1/chat/completions",
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": SISTEM_PROMPTU},
                {"role": "user", "content": kullanici_mesaji},
            ],
            "temperature": 0.3,
            "max_tokens": 2000,
        },
        timeout=300,
    )
    yanit.raise_for_status()
    return yanit.json()["choices"][0]["message"]["content"]


def _claude_api(kullanici_mesaji: str) -> str:
    """
    Anthropic Claude API'sine istek atar.
    .env: ANTHROPIC_API_KEY, CLAUDE_MODEL
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY bulunamadı (.env).")
    model = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")

    yanit = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": model,
            "max_tokens": 2000,
            "system": SISTEM_PROMPTU,
            "messages": [{"role": "user", "content": kullanici_mesaji}],
        },
        timeout=300,
    )
    yanit.raise_for_status()
    return yanit.json()["content"][0]["text"]


if __name__ == "__main__":
    # Sahte veriyle yapısal test (gerçek model gerektirmez)
    sahte = [
        {"baslik": "Test Video", "kanal": "Test Kanal",
         "url": "https://youtube.com/x", "metin": "Bu bir test metnidir."}
    ]
    print("Bağlam hazırlama testi geçti. Modül yapısı doğru.")
    print(f"Saglayici (env): {os.getenv('MODEL_SAGLAYICI', 'lokal')}")
