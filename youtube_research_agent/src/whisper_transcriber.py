"""faster-whisper ile yerel STT.

CUDA OOM / kutuphane hatasi NET Turkce bildirilir; SESSIZ CPU FALLBACK YOK.
Dizustu (12GB) icin compute_type/model config'ten gelir (turbo + int8_float16).
"""
from __future__ import annotations

import time


def _cuda_hatasi_mi(e: Exception) -> bool:
    m = str(e).lower()
    return any(k in m for k in ("out of memory", "cuda", "cudnn", "cublas", "gpu"))


def transcribe(wav_path, language_hint, stt_cfg) -> tuple[str, str, float]:
    """(text, detected_lang, sure_sn). Hata -> RuntimeError (Turkce, net)."""
    try:
        from faster_whisper import WhisperModel
    except Exception as e:
        raise RuntimeError(f"faster-whisper yuklenemedi: {e}")

    is_tr = (language_hint or "").lower().startswith("tr")
    model_name = stt_cfg.get("whisper_model_tr") if is_tr else stt_cfg.get("whisper_model_en")
    model_name = model_name or "large-v3-turbo"
    device = stt_cfg.get("device", "cuda")
    compute = stt_cfg.get("compute_type", "int8_float16")
    beam = stt_cfg.get("beam_size", 5)

    try:
        model = WhisperModel(model_name, device=device, compute_type=compute)
    except Exception as e:
        if _cuda_hatasi_mi(e):
            raise RuntimeError(
                f"CUDA/GPU hatasi (model yuklenemedi): {e}\n"
                f"  Oneri: compute_type'i 'int8'e dusurun veya cuDNN/CUDA kurulumunu kontrol edin.\n"
                f"  NOT: Sessizce CPU'ya DUSULMEDI (istendigi gibi).")
        raise RuntimeError(f"Whisper modeli yuklenemedi ({model_name}): {e}")

    t0 = time.perf_counter()
    try:
        segments, info = model.transcribe(
            str(wav_path), language=(language_hint or None),
            vad_filter=True, beam_size=beam)
        text = " ".join(s.text.strip() for s in segments).strip()
    except Exception as e:
        if _cuda_hatasi_mi(e):
            raise RuntimeError(
                f"CUDA OOM/hata (transcribe): {e}\n"
                f"  Oneri: compute_type int8 / daha kisa video. CPU'ya dusulmedi.")
        raise RuntimeError(f"STT hatasi: {e}")
    sure = time.perf_counter() - t0
    return text, info.language, sure
