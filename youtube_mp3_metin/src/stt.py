"""MP3 -> metin: faster-whisper ile YEREL STT (GPU).

Model BIR KEZ yuklenir, tum videolarda tekrar kullanilir (hiz icin).
CUDA/cuDNN hatasi NET Turkce bildirilir; sessiz CPU fallback YOK
(istenmeden CPU'ya dusup saatlerce beklememek icin). CPU istiyorsan
acikca --cihaz cpu ver.
"""
from __future__ import annotations

import time
from pathlib import Path


def _cuda_hatasi_mi(e: Exception) -> bool:
    m = str(e).lower()
    return any(k in m for k in ("out of memory", "cuda", "cudnn", "cublas", "gpu"))


class WhisperMetin:
    """faster-whisper modelini bir kez yukleyip MP3'leri metne cevirir."""

    def __init__(self, model: str = "large-v3-turbo", cihaz: str = "cuda",
                 compute: str = "int8_float16", beam: int = 5):
        try:
            from faster_whisper import WhisperModel
        except Exception as e:
            raise RuntimeError(
                f"faster-whisper yuklenemedi: {e}\n"
                f"  Kurulum: pip install -r youtube_mp3_metin/requirements.txt"
            )
        self.beam = beam
        try:
            self.model = WhisperModel(model, device=cihaz, compute_type=compute)
        except Exception as e:
            if _cuda_hatasi_mi(e):
                raise RuntimeError(
                    f"CUDA/GPU hatasi (model yuklenemedi): {e}\n"
                    f"  Oneri: --compute int8 deneyin VEYA cuDNN/CUDA kurulumunu kontrol edin.\n"
                    f"  GPU yoksa: --cihaz cpu --compute int8 (yavas ama calisir)."
                )
            raise RuntimeError(f"Whisper modeli yuklenemedi ({model}): {e}")

    def cevir(self, mp3_yol, dil: str | None = None) -> tuple[str, str, float]:
        """(metin, algilanan_dil, sure_sn). dil=None -> otomatik algila."""
        t0 = time.perf_counter()
        try:
            segments, info = self.model.transcribe(
                str(mp3_yol), language=(dil or None),
                vad_filter=True, beam_size=self.beam)
            metin = " ".join(s.text.strip() for s in segments).strip()
        except Exception as e:
            if _cuda_hatasi_mi(e):
                raise RuntimeError(
                    f"CUDA OOM/hata (transcribe): {e}\n"
                    f"  Oneri: --compute int8 veya daha kisa video."
                )
            raise RuntimeError(f"STT hatasi: {e}")
        return metin, info.language, time.perf_counter() - t0


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Kullanim: python -m src.stt <mp3_dosyasi> [dil]")
        sys.exit(1)
    stt = WhisperMetin()
    metin, dil, sure = stt.cevir(Path(sys.argv[1]),
                                 sys.argv[2] if len(sys.argv) > 2 else None)
    print(f"[dil={dil}, {sure:.1f}s, {len(metin):,} karakter]\n")
    print(metin[:500])
