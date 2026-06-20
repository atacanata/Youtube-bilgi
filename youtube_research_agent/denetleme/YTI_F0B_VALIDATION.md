# YTI-F0B — Validation Raporu (v1)

> **Paket:** YTI-F0B — Claim/Evidence DB foundation + boş repository layer
> **Tür:** Eklemeli kod (yeni şema modülü + repo layer + tek satır init kancası + test). İş
> mantığı YOK. **Tarih:** 2026-06-20 · **Branch:** `yti-f0b-claim-evidence-db` · **Önceki:**
> [F0A sözleşmesi](YTI_F0A_CLAIM_EVIDENCE_CONTRACT_v1.md) · [F0B-0 precheck](YTI_F0B_PRECHECK_RAPORU.md)

---

## 1. Ne eklendi (diff kapsamı)

| Dosya | İşlem | İçerik |
|---|---|---|
| `src/claim_evidence_schema.py` | **YENİ** | 6 tablo + 8 index, saf `CREATE ... IF NOT EXISTS` DDL + `ensure_claim_evidence_schema()` |
| `src/claim_evidence_repo.py` | **YENİ** | 8 temel CRUD fonksiyonu (insert/select); iş mantığı yok |
| `src/db.py` | **DÜZENLE (2 satır)** | 1 import + `init_db` içinde 1 çağrı (`ensure_claim_evidence_schema`) |
| `tests/test_claim_evidence_db.py` | **YENİ** | 5 smoke/test; pytest'siz de çalışır (stdlib) |
| `denetleme/YTI_F0B_VALIDATION.md` | **YENİ** | bu dosya |

Mevcut iş mantığı modüllerine (`scorer`, `stt_runner`, `product_report_builder`, …) **0 değişiklik**.

## 2. Yeni 6 tablo + DDL kuralları

`product_runs · evidence_segments · insight_claims · claim_evidence_links · agent_runs · audit_events`

- Tümü `CREATE TABLE IF NOT EXISTS` → **idempotent**.
- TEXT birincil anahtarlar açıkça `TEXT NOT NULL PRIMARY KEY` (`run_id, segment_id, claim_id, agent_run_id`).
- `evidence_segments.run_id` ve `insight_claims.run_id`: `NOT NULL REFERENCES product_runs(run_id) ON DELETE CASCADE` (claim/evidence bir product-run snapshot'ına bağlı).
- `evidence_segments.video_id`: `NOT NULL REFERENCES videos(video_id) ON DELETE CASCADE` (mevcut tabloya **FK referansı**; ALTER değil).
- `audit_events.event_id`: `INTEGER PRIMARY KEY AUTOINCREMENT` (job_log ile tutarlı).
- Mevcut 5 tabloya **ALTER yok**, veriye dokunma yok.

## 3. db.py kancası (minimal)

```python
from src import claim_evidence_schema  # (yeni import)
...
def init_db(db_path):
    conn = get_conn(db_path)
    conn.executescript(SCHEMA)          # mevcut 5 tablo — DEĞİŞMEDİ
    migrate(conn)                       # mevcut migration — DEĞİŞMEDİ
    claim_evidence_schema.ensure_claim_evidence_schema(conn)  # YENİ: 6 tablo (eklemeli)
    conn.commit()
    return conn
```

`get_conn()` değişmedi → çalışan komutlar (report-products, stt-transcribe, …) **otomatik migrate
olmaz**; yeni tablolar yalnız `init-db` çağrılınca oluşur (mevcut desenle birebir aynı).

## 4. Repository layer (8 fonksiyon, iş mantığı yok)

`create_product_run` · `get_product_run` · `insert_evidence_segment` · `insert_insight_claim` ·
`link_claim_evidence` · `insert_agent_run` · `insert_audit_event` · `list_claims_for_product`

- ID'ler stdlib `uuid4` ile (`run_…/seg_…/clm_…/ar_…`). `audit_events.event_id` INTEGER autoincrement.
- **Bilinçli olarak YOK:** confidence hesabı, claim extraction, evidence üretimi, agent, Hemensec export.

## 5. Test / smoke sonuçları

Çalıştırma: `python tests/test_claim_evidence_db.py` (venv; pytest gerekmedi). Tümü **geçici DB**;
gerçek-DB idempotentliği canlı `data/youtube.db`'nin **kopyası** üzerinde doğrulandı (canlı dosya değişmedi).

```
PASS  test_init_creates_all_tables
PASS  test_init_idempotent_preserves_data
PASS  test_existing_five_tables_intact
PASS  test_repository_insert_select
  (gercek DB kopyasi: videos=581 korundu, 6 tablo eklendi, idempotent)
PASS  test_init_on_real_db_copy

=== SONUC: 5/5 gecti ===
```

Kapsanan başarı kriterleri:
- ✅ Temiz DB'de init 6 yeni + 5 eski tabloyu oluşturuyor.
- ✅ İkinci init idempotent; araya eklenen veri korunuyor.
- ✅ Eski 5 tablonun CREATE sql'i ikinci init sonrası **bit-aynı** (ALTER/rebuild yok).
- ✅ Temel insert/select round-trip (run→evidence→claim→link→agent→audit, list/get) çalışıyor.
- ✅ Repository layer import ediliyor.

## 6. Regresyon + canlı DB dokunulmazlığı

```
$ python main.py stt-quota
STT gunluk kota: 7/20 kullanildi | kalan: 13 | durum: ACIK     # CLI yeni import'la sorunsuz yükleniyor

# CANLI data/youtube.db (init-db ÇALIŞTIRILMADI):
tablolar: ['analyses', 'job_log', 'search_cache', 'sqlite_sequence', 'transcripts', 'videos']
```

- Canlı DB'de **yeni 6 tablonun hiçbiri yok** → F0B canlı veriyi/şemayı **dokunmadan** bıraktı.
- `sqlite_sequence` F0B öncesinde de vardı (`job_log.id AUTOINCREMENT`'in iç tablosu) — yeni değil.
- Yeni tablolar kullanıcı `python main.py init-db` çağırınca oluşacak (önce `data/youtube.db` yedeği önerilir).

## 7. Sınırların teyidi

YouTube search ❌ · STT ❌ · yt-dlp ❌ · indirme ❌ · LLM ❌ · ajan kodu ❌ · insight üretimi ❌ ·
report üretimi ❌ · Hemensec export ❌ · mevcut pipeline davranışı **değişmedi** · mevcut 5 tablo
**değişmedi** · `data/reports` & `data/analyses` git'e **eklenmedi** (gitignored).

PR diff'i yalnız: **schema + repo layer + db init kancası + test + validation**.

## 8. Sonraki paket

**F1 — Evidence çıkarımı (AGENT_1):** transcript → `evidence_segments` (kanonik niteliğe etiketli
birebir alıntı + source_quality), `agent_runs`/`audit_events` ile denetlenir. Confidence/claim
sentezi F2–F3'te. Bu pakette üretilen repository fonksiyonları o ajanların yazma yüzeyi olacak.

---
*Üretim: Claude Code routine (API'siz). Bu PR yalnız şema + repo + tek init kancası + test +
validation içerir; mevcut pipeline ve 5 tablo değişmedi. Ayrı PR; merge yok.*
