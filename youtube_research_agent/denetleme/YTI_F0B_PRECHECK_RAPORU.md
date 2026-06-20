# YTI-F0B-0 — PRECHECK Raporu (v1)

> **Paket:** YTI-F0B-0 — Claim/Evidence migration + repository layer öncesi precheck
> **Tür:** SALT-OKUMA keşif + dokümantasyon. Bu pakette **kod / migration / DB / Python iş
> mantığı / ajan kodu YOK**. İzin verilen tek değişiklik: **markdown doküman ekleme**.
> **Tarih:** 2026-06-20 · **Sürüm:** v1 · **Önceki:** [YTI-F0A sözleşmesi](YTI_F0A_CLAIM_EVIDENCE_CONTRACT_v1.md)
> **Sonraki (onaya tabi):** F0B — eklemeli migration + boş repository layer (kod)

---

## 0. Bu paketin sınırları (teyit)

Yapılmadı / yapılmayacak: `kod yazma` · `migration yazma` · `DB değiştirme` ·
`Python iş mantığı` · `ajan kodu` · `YouTube search` · `STT` · `yt-dlp` · `indirme` ·
`Hemensec prod`. **İzin verilen:** yalnız markdown doküman ekleme + (yalnız .md için) commit/PR.
**Merge yok.**

---

## 1. Mevcut dosya ağacı özeti

```
youtube_research_agent/
├── README.md            (⚠️ BAYAT: "Sprint 1, STT yok" diyor; oysa STT canlı)
├── config.yaml  requirements.txt  main.py
├── src/                 23 .py — düz tek katman, ham SQL modül içinde
├── prompts/             3 .md (analysis, product_insight, product_insight_dikey)
├── denetleme/           YTI_F0A_..._v1.md  +  (bu) YTI_F0B_PRECHECK_RAPORU.md
├── data/                youtube.db + analyses/(13) reports/(5) transcripts/(14)   [gitignored]
├── tmp/  __pycache__/
```

**Kritik yokluklar (doğrulandı):**
- ❌ `tests/` yok · `test_*.py` yok · `conftest.py` yok · `requirements.txt`'te `pytest` yok → **otomatik test yok**.
- ❌ `migrations/` / alembic yok.
- ❌ `repository/` / DAO / store katmanı yok.

---

## 2. Mevcut markdown dosyaları ve GitHub'a ekleme kararı

| Markdown | Sınıf | Git durumu | Aksiyon |
|---|---|---|---|
| `denetleme/YTI_F0A_CLAIM_EVIDENCE_CONTRACT_v1.md` | Proje dokümanı | untracked | ✅ **EKLE** |
| `denetleme/YTI_F0B_PRECHECK_RAPORU.md` (bu dosya) | Proje dokümanı | yeni | ✅ **EKLE** |
| `README.md` | Proje dokümanı | tracked | — (zaten repoda) |
| `prompts/analysis_prompt.md` | Prompt şablonu | tracked | — |
| `prompts/product_insight_prompt.md` | Prompt şablonu | tracked | — |
| `prompts/product_insight_prompt_dikey_supurge.md` | Prompt şablonu | tracked | — |
| `data/reports/dikey_supurge_report.md` | Çıktı (rapor) | ignored | ❌ ekleme |
| `data/reports/robot_supurge_report.md` | Çıktı (rapor) | ignored | ❌ ekleme |
| `data/reports/mert_report.md` | Çıktı (rapor) | ignored | ❌ ekleme |
| `data/reports/karsilastirma_dreame_x50_vs_roborock_s8maxv.md` | Çıktı (karşılaştırma) | ignored | ❌ ekleme |
| `data/reports/karsilastirma_dyson_v16_vs_dreame_z30.md` | Çıktı (karşılaştırma) | ignored | ❌ ekleme |
| `data/analyses/6Gq-z1BQ9is_product_prompt.md` | Geçici (üretilmiş prompt) | ignored | ❌ ekleme |

> **Sonuç:** GitHub'a yalnız **2 doküman** eklenir (her ikisi de `denetleme/`). `data/**` markdown'ları
> `.gitignore` ile dışlanmış üretim çıktısı/geçici dosyalardır; **eklenmez**. README + prompt'lar
> zaten tracked. Belirsiz/karar gerektiren başka markdown **yok**.

---

## 3. DB init / migration gerçek akışı

Migration sistemi **yok**; şema tamamen `src/db.py` içinde kod ile yönetilir.

| Öğe | Yer (`src/db.py`) | Ne yapar | Risk |
|---|---|---|---|
| `SCHEMA` sabiti | 16-104 | 5 tablo + 3 index `CREATE ... IF NOT EXISTS` | yok (idempotent) |
| `init_db()` | 216-222 | `executescript(SCHEMA)` → `migrate()` → commit | **şemanın kurulduğu TEK yer** |
| `migrate()` | 131-149 | eksik `videos` kolonları `ALTER ADD`; `analyses.product_insights_json` ekle; `_ensure_status_check()`; 5 index `IF NOT EXISTS` | düşük (eklemeli) |
| `_ensure_status_check()` | 194-213 | status CHECK eskiyse `videos`'u **rebuild** (new→copy→drop→rename) | ⚠️ **tek yıkıcı yol** — mevcut DB'de `AUDIO_DOWNLOADING` var → **şu an no-op** |
| `get_conn()` | 107-114 | yalnız bağlanır (foreign_keys ON, Row factory) — **migrate ÇALIŞTIRMAZ** | yok |

**En kritik gerçek:** Çalışan pipeline komutları (`report-products`, `stt-transcribe`, …) `get_conn`
kullanır ve **asla otomatik migrate olmaz**. Şema yalnız `python main.py init-db` çağrılınca
kurulur/güncellenir; `init-db` idempotenttir (hep `IF NOT EXISTS` / koşullu `ALTER`).

---

## 4. Mevcut 5 tablonun tanımlandığı yer

Hepsi tek string sabitinde — `src/db.py`:
- `videos` (17-53) — PK `video_id`; `status` CHECK(13 değer); `source_mode` CHECK(CHANNEL|PRODUCT_SEARCH)
- `transcripts` (55-68) — PK `video_id` (**surrogate id YOK**); `source_type` CHECK(5 değer)
- `analyses` (70-82) — PK `video_id`; `product_insights_json`
- `job_log` (84-91) — PK `id` AUTOINC
- `search_cache` (97-103) — PK (`query`,`fetched_date`)

> Ayrıca `videos` şeması rebuild için `_VIDEOS_REBUILD_DDL`'de (153-191) **bir kez daha** tekrar
> ediyor (ikiz tanım — F0B'de bu yola DOKUNULMAYACAK).

---

## 5. Mevcut test / smoke komutları

Otomatik test **yok**. Mevcut "smoke" yalnız CLI:
`python main.py init-db` · `list --status ...` · `report-products --category ...` · `stt-quota`.
README komut listesi mevcut ama **bayat** (ürün/STT komutlarını yansıtmıyor). → F0B'de test
altyapısı **sıfırdan** kurulacak.

---

## 6. Repository layer var mı?

**Yok.** Veri erişimi modüllere gömülü ham SQL (örn. `product_report_builder.py` doğrudan
`conn.execute(...)`). F0B'nin "boş repository layer"ı tamamen yeni olacak.

---

## 7. 6 yeni tabloyu eklemek için **en az riskli yer**

**Öneri: ayrı modül + tek satırlık `init_db` kancası** (mevcut `SCHEMA` string'ine ve `migrate()`'e dokunma).

- ✅ **YENİ** `src/claims_schema.py` → `CLAIMS_SCHEMA` sabiti: 6 tablo + indexler, **yalnız `CREATE ... IF NOT EXISTS`**.
- ✅ `db.init_db()`'ye **tek satır**: `migrate()`'ten sonra `conn.executescript(claims_schema.CLAIMS_SCHEMA)`.
- ❌ `SCHEMA` sabitine, `migrate()`'e, `_ensure_status_check`/`_VIDEOS_REBUILD_DDL`'ye **dokunma**.
- ❌ Mevcut 5 tabloya **hiç `ALTER` yok**. (transcript_id için `transcripts`'e dokunmadan `transcript_id = video_id` kullan.)

Gerekçe: ayrı script bütünlüğü böler; doğrudan `SCHEMA`'ya gömmek çekirdek string'i kirletir.
Ayrı modül + tek kanca = **izole, geri-alınabilir, eklemeli, tek yıkıcı yoldan uzak.**

6 tablo (F0A sözleşmesinden): `product_runs`, `evidence_segments`, `insight_claims`,
`claim_evidence_links`, `agent_runs`, `audit_events`.

---

## 8. Önerilen F0B dosya değişiklik listesi

| Dosya | İşlem | İçerik |
|---|---|---|
| `src/claims_schema.py` | **YENİ** | 6 tablo + index DDL (saf, `IF NOT EXISTS`) |
| `src/db.py` | **DÜZENLE (1 satır)** | `init_db` içine `executescript(CLAIMS_SCHEMA)` kancası (eklemeli) |
| `src/repository/__init__.py` | **YENİ** | paket |
| `src/repository/{runs,evidence,claims,links,agent_runs,audit}_repo.py` | **YENİ** | CRUD **imzaları** + doğrulama; **iş mantığı/sentez YOK** |
| `tests/conftest.py` | **YENİ** | geçici-DB fixture (asla `data/youtube.db`'ye dokunmaz) |
| `tests/test_claims_schema.py` | **YENİ** | tablolar oluşuyor / idempotent / eski 5 tablo değişmedi |
| `tests/test_repository_smoke.py` | **YENİ** | CRUD round-trip (geçici DB) |
| `requirements.txt` | **DÜZENLE** | `pytest` ekle (dev) |
| `main.py` | (opsiyon) | yeni tablolar `init-db`'ye gömülü → ayrı komut gerekmez |

**Mevcut koda toplam temas:** sadece `db.py`'de **1 satır** + `requirements.txt`'e **1 satır**.
Geri kalanı tümü **yeni dosya**. Mevcut iş mantığı modüllerine **0 değişiklik**.

---

## 9. Önerilen test komutları

```bash
# 0) GÜVENLİK: gerçek DB'yi yedekle (ilk init-db'den önce)
cp data/youtube.db data/youtube.db.bak

# 1) otomatik (geçici DB — gerçek DB'ye dokunmaz)
pytest -q

# 2) idempotent + regresyon (gerçek DB)
python main.py init-db          # 2 kez → hata yok, tablo sayısı sabit
python main.py report-products --category dikey_supurge   # eski hat çalışıyor mu
python main.py stt-quota

# 3) doğrula: 5 eski + 6 yeni = 11 tablo; eski tabloların sqlite_master.sql'i değişmemiş
```

---

## 10. Riskler

| Risk | Cevap |
|---|---|
| Mevcut DB bozulur mu? | **Hayır** — yalnız `CREATE ... IF NOT EXISTS`; mevcut 5 tabloya `ALTER` yok; tek yıkıcı yol (`videos` rebuild) zaten no-op; yeni tablolar izole. |
| Eski pipeline etkilenir mi? | **Hayır** — yeni tablolar mevcut komutlarca kullanılmaz; `get_conn` değişmez. Tek init_db kancası akışın **sonuna** ekler. (Not: yeni tablolar için bir kez `init-db` koşmak gerekir.) |
| İdempotent migration nasıl garanti? | `CREATE TABLE/INDEX IF NOT EXISTS` (tekrar-koşulabilir); `ALTER`/`INSERT`/veri kopyası **yok**. Test: `init-db` iki kez → hata yok + tablo sayısı sabit. |
| Test nasıl? | **Geçici DB** (pytest `tmp_path`), asla `data/youtube.db` değil. Tablo oluşumu, idempotentlik, eski 5 tablonun `sqlite_master.sql` diff'i, CRUD round-trip, eski komut regresyonu. |

Devralınan F0A riskleri (hatırlatma): **R1** STT segment zaman damgası atılıyor (`start/end_sec` için ileride gerekli) · **R2** `transcripts` surrogate id'siz · **R3** `source_quality` bugün serbest metin. F0B'de bunların hiçbiri çözülmez (kapsam dışı); şema NULLable/`video_id` ile uyumlu kalır.

---

## 🟢 "Kod yazmaya güvenli mi?" kararı → **EVET (yeşil)**, koşullarla

1. **Yalnız eklemeli**: sadece `CREATE TABLE/INDEX IF NOT EXISTS`; mevcut 5 tabloya **hiç ALTER yok**.
2. Yeni DDL **ayrı modülde** izole; `db.py`'de **tek satır** kanca; `migrate()`/`_ensure_status_check`/`_VIDEOS_REBUILD_DDL`'ye **dokunma**.
3. Testler **geçici DB**'de; ilk gerçek `init-db`'den önce `youtube.db` **yedeklenir**.
4. `transcripts`'e F0B'de **dokunulmaz** (`transcript_id = video_id`).
5. Ajan 1/2/3/4 ve sentez mantığı **kodlanmaz** (repository sadece CRUD iskeleti).

---

## ❓ Emin olunmayan / onay istenen noktalar

1. **transcript_id (R2):** F0B'de `transcripts`'e surrogate `id` **eklemeyelim**, `transcript_id = video_id`. (öneri: ertele)
2. **start_sec/end_sec (R1):** Şema NULLable; F0B'de STT segment zaman damgası **YOK**. (teyit?)
3. **Giriş noktası:** yeni tablolar mevcut `init-db`'ye gömülü mü, ayrı `init-claims-db` mı? (öneri: `init-db`)
4. **pytest:** `requirements.txt`'e `pytest` (dev) eklemek serbest mi? (öneri: ekle)
5. **ID üretimi:** stdlib `uuid4` (yeni bağımlılık yok) mu, ULID mü? (öneri: uuid4)
6. **README:** bayat — F0B'de düzelteyim mi, kapsam dışı mı? (öneri: tek satır not, kapsamı şişirme)

---
*Üretim: Claude Code routine (API'siz). Bu doküman `youtube_research_agent/denetleme/` altındadır ve
mevcut çalışan hattı değiştirmez. Bu PR yalnız .md doküman içerir; kod/migration/DB değişikliği yoktur.*
