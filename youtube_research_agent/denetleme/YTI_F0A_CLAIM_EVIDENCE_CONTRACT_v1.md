# YTI-F0A — Claim / Evidence Mimari Sözleşmesi (v1)

> **Paket:** YTI-F0A — Claim/Evidence mimarisi sözleşmesi ve mevcut sistem keşfi
> **Tür:** SALT SÖZLEŞME / TASARIM. Bu doküman hiçbir kodu, tabloyu, migration'ı veya
> davranışı **değiştirmez**. Yalnızca mevcut durumu haritalar ve gelecek veri omurgasını
> sözleşme olarak tanımlar.
> **Tarih:** 2026-06-20 · **Sürüm:** v1.1 · **Durum:** Onay bekliyor (sonraki paket: F0B)
>
> **Revizyon v1.1 (F0B-0 P2 doküman düzeltmesi):** Yeni tabloların TEXT birincil anahtarları
> açıkça `NOT NULL` yapıldı; `evidence_segments.run_id` ve `insight_claims.run_id` artık
> `NOT NULL REFERENCES product_runs(run_id) ON DELETE CASCADE` (claim/evidence kayıtları bir
> product-run snapshot'ına bağlı olmalı). `audit_events.event_id` INTEGER AUTOINCREMENT → TEXT
> NOT NULL PRIMARY KEY (spine PK tutarlılığı). **Yalnız doküman; kod/DB/migration değişikliği yok.**

---

## 0. Bu paketin sınırları (teyit)

Aşağıdakilerin **hiçbiri** bu pakette yapılmadı / yapılmayacak:

`kod yazma` · `migration yazma` · `DB değiştirme` · `YouTube search` · `STT` · `yt-dlp` ·
`indirme` · `LLM ajan kodu` · `otonomi` · `Hemensec prod'a dokunma` · `mevcut pipeline'ı
değiştirme` · `yeni kategori açma`.

Bu dokümandaki tüm `CREATE TABLE`, JSON şema ve formüller **TASARIM**dır; uygulanmaları
**F0B ve sonrası** paketlere aittir. Mevcut tablolara (`videos`, `transcripts`, `analyses`,
`job_log`, `search_cache`) **dokunulmaz**; yeni yapı **yalnızca eklemeli** (additive) olacaktır.

---

## 1. Mevcut sistem özeti

`youtube_research_agent/`, YouTube ürün inceleme videolarından **API'siz** (Anthropic API yok;
sentezi **Claude Code routine** yapar) ürün istihbaratı üreten bir CLI hattıdır.

**Temel mimari ayrım (korunacak):**
- `videos.status` → **SÜREÇ** (state machine: videonun hattaki yeri)
- `transcripts.source_type` → **PROVENANCE** (metnin kaynağı: CAPTION/STT/MANUAL/…)
- `videos.source_mode` → **MOD** (`CHANNEL` | `PRODUCT_SEARCH`) — kanal analizi ile ürün
  istihbaratı veri yolları **karışmaz**.

**Akış (ürün modu):** `build-queries` → `search-products` (Data API, `search_cache` ile kota
koruması) → `score-products` (deterministik `relevance_score`) → transcript edinimi
(`stt-transcribe` yerel Whisper + ban koruması, ya da `import-product-transcript`) →
`analyze-products` (her video için prompt dosyası üretir; **analiz satırı YAZMAZ**) →
**Claude routine** transcript'i okur, JSON içgörü üretir → `import-product-insight`
(`analyses.product_insights_json` + `status=ANALYZED`) → `report-products` (Markdown rapor,
string-frekansı ile "(N videoda)" toplulaştırma).

**Bugünkü içgörünün biçimi:** video başına **serbest-metin JSON blob'u**
(`artilar`, `eksiler`, `sorunlar`, `rakip_karsilastirma`, `kriterler`, `satin_alma_etkenleri`,
`guvenilirlik`). Toplulaştırma, maddelerin **byte-aynı string** olmasına dayanır (Counter ile
sayılır). Güvenilirlik (bağımsız/sponsorlu) **serbest metin** olarak `guvenilirlik` alanındadır.

**Bu mimarinin sınırı (F0'ın varlık nedeni):**
1. Sayım, Claude'un **kanonik string'i birebir** yazmasına bağlı → kırılgan.
2. Bir iddianın **transcript'te nereden** geldiği (zaman aralığı/alıntı) **kayıtlı değil** →
   izlenebilir kanıt yok.
3. `independent_count` / `sponsored_count` **deterministik hesaplanamıyor** (güvenilirlik
   serbest metin).
4. **Çelişki** (örn. Z30 ağırlık: bir kaynak "hafif", diğeri "arka ağır/yorucu") iki ayrı
   satır olarak görünür; çelişki olarak **işaretlenmez**.
5. Analizin **provenance'ı** (hangi routine, ne zaman, hangi sürüm) izlenmez.

F0A bu beş sınırı kapatacak **claim → evidence → video → source_quality** omurgasını
sözleşmeye bağlar.

---

## 2. Mevcut tablo / akış haritası (gerçek şema)

### 2.1 Tablolar (kaynak: `src/db.py`)

| Tablo | PK | Önemli kolonlar | Not |
|---|---|---|---|
| `videos` | `video_id` | `source_mode` CHECK(CHANNEL\|PRODUCT_SEARCH), `category_key`, `product_name`, `search_query`, `search_intent`, `relevance_score`, `relevance_reason`, `status` CHECK(13 değer), `view_count`, `duration_sec`, `language_hint`, `channel_name`, `channel_id` | Metadata + süreç durumu |
| `transcripts` | `video_id` (FK→videos, CASCADE) | `source_type` CHECK(5 değer), `language`, `text`, `char_count`, `content_hash` | **Zaman damgası YOK** (yalnız tam metin); ayrıca diske `data/transcripts/{video_id}.txt` |
| `analyses` | `video_id` (FK→videos, CASCADE) | `product_insights_json` (Sprint 3), `model`, ayrıca kanal alanları (`short_summary`, `actionable_ideas_json`, …) | İçgörü serbest-metin JSON; 1 satır = 1 video |
| `job_log` | `id` AUTOINC | `video_id`, `stage`, `status` CHECK(ok\|error\|info), `message`, `created_at` | Append-only iş günlüğü |
| `search_cache` | (`query`,`fetched_date`) | `result_count`, `quota_cost` | Aynı gün aynı sorguyu API'ye tekrar göndermez |

`videos.status` kümesi: `DISCOVERED, SCORED, SKIPPED, NEEDS_TRANSCRIPT, AUDIO_DOWNLOADING,
TRANSCRIBING, TRANSCRIBED, NEEDS_MANUAL_TRANSCRIPT, NEEDS_AUDIO_STT, ANALYZING, ANALYZED,
DONE, FAILED`.
`transcripts.source_type` kümesi: `CAPTION_TRANSCRIPT, AUDIO_STT, MANUAL_TRANSCRIPT,
USER_UPLOADED_AUDIO, AUTHORIZED_VIDEO`.

### 2.2 Çıktıların üretildiği yerler (gerçek)

| Çıktı | Üretici (modül) | Konum |
|---|---|---|
| Ürün raporu (Markdown) | `src/product_report_builder.py::build_product_report` | `data/reports/{category_key}_report.md` |
| Karşılaştırma raporu | **Claude routine (elle)** | `data/reports/karsilastirma_*.md` |
| Analiz prompt'u | `src/product_insight_analyzer.py::analyze_products` | `data/analyses/{video_id}_product_prompt.md` |
| İçgörü JSON (Claude çıktısı) | **Claude routine** → `import-product-insight` saklar | dosya: `data/analyses/{video_id}_insight.json`; DB: `analyses.product_insights_json` |
| Transcript | `src/transcript_import.py::save_transcript` | DB `transcripts.text` + `data/transcripts/{video_id}.txt` |
| Toplulaştırma sayımı | `product_report_builder._freq` (Counter, `most_common(15)`, key `[:200]`) | rapor içi "(N videoda)" |

> Tüm `data/**` ve `config/.env` **`.gitignore`'da** (doğrulandı: `data/reports/*.md`,
> `data/analyses/*.json`). Repoya yalnızca kod/config/prompt gider.

### 2.3 Deterministik vs Claude-routine ayrımı (bugün)

- **Deterministik (kod):** sorgu üretimi, kota muhasebesi, `relevance_score` (anahtar
  kelime/intent/süre/izlenme), durum geçişleri, string-frekans sayımı.
- **Claude-routine (API'siz, elle):** transcript → içgörü JSON, güvenilirlik yorumu,
  karşılaştırma raporları. ← **F0'da bu adımların kanıtı ve denetimi yapılandırılacak.**

---

## 3. Önerilen yeni tablolar (SÖZLEŞME — F0B'de uygulanacak)

Tasarım ilkeleri: (a) mevcut 5 tabloya dokunma; (b) yeni tablolar `video_id` üzerinden
mevcut veriye **referans verir**, kopyalamaz; (c) her şey **eklemeli**; (d) yazımlar
denetlenebilir (`agent_runs` + `audit_events`).

```sql
-- (TASARIM) Bir ürün için tek bir analiz "koşusu" / sürümlü anlık görüntü.
-- Claim ve evidence bu koşuya bağlanır → tekrarlanabilirlik + "as of" ihracı.
CREATE TABLE product_runs (
    run_id            TEXT NOT NULL PRIMARY KEY,   -- ULID/uuid (kod üretir; F0B)
    category_key      TEXT NOT NULL,               -- mevcut videos.category_key ile uyumlu
    product_name      TEXT NOT NULL,               -- mevcut videos.product_name ile uyumlu
    run_type          TEXT NOT NULL                -- pipeline aşaması
        CHECK (run_type IN ('EVIDENCE_EXTRACTION','CLAIM_SYNTHESIS',
                            'CONFLICT_RESOLUTION','EXPORT')),
    input_video_count    INTEGER DEFAULT 0,
    analyzed_video_count INTEGER DEFAULT 0,
    status            TEXT NOT NULL DEFAULT 'RUNNING'
        CHECK (status IN ('RUNNING','DONE','PARTIAL','FAILED')),
    agent_run_id      TEXT,                         -- FK→agent_runs (bu koşuyu yürüten routine)
    schema_version    TEXT NOT NULL DEFAULT 'f0',
    started_at        TEXT DEFAULT (datetime('now')),
    finished_at       TEXT,
    notes             TEXT
);

-- (TASARIM) Atomik kanıt: bir transcript'in, bir kanonik niteliğe dair bir parçası.
CREATE TABLE evidence_segments (
    segment_id        TEXT NOT NULL PRIMARY KEY,   -- kod üretir (F0B)
    run_id            TEXT NOT NULL REFERENCES product_runs(run_id) ON DELETE CASCADE,
    video_id          TEXT NOT NULL REFERENCES videos(video_id) ON DELETE CASCADE,
    transcript_id     TEXT,                         -- bkz. RİSK R2 (transcripts'te surrogate id yok)
    start_sec         REAL,                         -- bkz. RİSK R1 (mevcut STT zaman damgası atıyor)
    end_sec           REAL,
    text              TEXT NOT NULL,                -- transcript'ten BİREBİR alıntı (uydurma yok)
    source_quality    TEXT NOT NULL                -- video kaynağının güveni (§7 enum)
        CHECK (source_quality IN ('INDEPENDENT_PURCHASE','INDEPENDENT_EDITORIAL',
                            'REVIEW_UNIT','SPONSORED','BRAND_OFFICIAL','RETAILER','UNKNOWN')),
    category_attribute TEXT NOT NULL,               -- kanonik nitelik anahtarı (§8/§9)
    polarity          TEXT DEFAULT 'NEUTRAL'
        CHECK (polarity IN ('POSITIVE','NEGATIVE','NEUTRAL')),
    extraction_confidence REAL,                     -- 0..1 (Agent-1'in öz-güveni; deterministik DEĞİL)
    created_by_agent_run TEXT,                       -- FK→agent_runs
    created_at        TEXT DEFAULT (datetime('now'))
);

-- (TASARIM) Sentezlenmiş iddia: ürün × kanonik nitelik × tür başına bir satır.
CREATE TABLE insight_claims (
    claim_id          TEXT NOT NULL PRIMARY KEY,
    run_id            TEXT NOT NULL REFERENCES product_runs(run_id) ON DELETE CASCADE,
    category_key      TEXT NOT NULL,
    product_name      TEXT NOT NULL,
    claim_type        TEXT NOT NULL                -- §4
        CHECK (claim_type IN ('FEATURE_PRESENT','PRO','CON','PROBLEM',
                            'COMPARISON','PURCHASE_FACTOR','SPEC','RELIABILITY')),
    canonical_attribute TEXT NOT NULL,              -- §8/§9 anahtarı (JOIN/sayım anahtarı)
    claim_text        TEXT NOT NULL,               -- okunabilir kanonik ifade (TR)
    -- aşağıdaki sayımlar TÜREVDİR (claim_evidence_links'ten deterministik hesaplanır):
    video_count       INTEGER NOT NULL DEFAULT 0,  -- destekleyen DISTINCT video
    independent_count INTEGER NOT NULL DEFAULT 0,
    sponsored_count   INTEGER NOT NULL DEFAULT 0,
    unknown_count     INTEGER NOT NULL DEFAULT 0,
    conflict_status   TEXT NOT NULL DEFAULT 'NONE'
        CHECK (conflict_status IN ('NONE','MINOR','MAJOR')),
    conflict_note     TEXT,
    deterministic_confidence REAL NOT NULL DEFAULT 0,  -- §6 formülü (0..1)
    hemensec_ready    INTEGER NOT NULL DEFAULT 0,      -- 0/1, §6 eşikleri
    created_at        TEXT DEFAULT (datetime('now')),
    updated_at        TEXT DEFAULT (datetime('now'))
);

-- (TASARIM) Claim ↔ Evidence çok-çok bağ. Çelişki burada doğar (CONTRADICTS bağı varsa).
CREATE TABLE claim_evidence_links (
    claim_id          TEXT NOT NULL REFERENCES insight_claims(claim_id) ON DELETE CASCADE,
    segment_id        TEXT NOT NULL REFERENCES evidence_segments(segment_id) ON DELETE CASCADE,
    relation          TEXT NOT NULL DEFAULT 'SUPPORTS'
        CHECK (relation IN ('SUPPORTS','CONTRADICTS','QUALIFIES')),
    created_at        TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (claim_id, segment_id)
);

-- (TASARIM) Her Claude-routine/ajan yürütmesinin provenance kaydı (Agent 1/2/3/4 burada izlenir).
CREATE TABLE agent_runs (
    agent_run_id      TEXT NOT NULL PRIMARY KEY,
    agent_name        TEXT NOT NULL,               -- 'AGENT_1_EVIDENCE', 'AGENT_2_CLAIM', ...
    agent_role        TEXT,
    model             TEXT,                         -- 'claude-code-routine' / model kimliği
    input_ref         TEXT,                         -- run_id / video_id / prompt yolu
    output_ref        TEXT,                         -- üretilen segment/claim id'leri (JSON)
    status            TEXT NOT NULL DEFAULT 'RUNNING'
        CHECK (status IN ('RUNNING','DONE','FAILED')),
    started_at        TEXT DEFAULT (datetime('now')),
    finished_at       TEXT,
    notes             TEXT
);

-- (TASARIM) Append-only denetim izi (job_log'un claim/evidence/export katmanı karşılığı).
CREATE TABLE audit_events (
    event_id          TEXT NOT NULL PRIMARY KEY,   -- F0B-0 P2: INTEGER AUTOINCREMENT yerine TEXT uuid (spine PK tutarliligi; siralama ts ile)
    ts                TEXT DEFAULT (datetime('now')),
    actor             TEXT NOT NULL,               -- agent_run_id | 'cli' | 'human'
    event_type        TEXT NOT NULL
        CHECK (event_type IN ('EVIDENCE_ADDED','CLAIM_CREATED','CLAIM_UPDATED',
                            'CONFLICT_FLAGGED','HEMENSEC_MARKED_READY','EXPORTED','OVERRIDE')),
    entity_type       TEXT NOT NULL CHECK (entity_type IN ('segment','claim','run','export')),
    entity_id         TEXT NOT NULL,
    detail_json       TEXT,                         -- önce/sonra diff veya bağlam
    reason            TEXT
);
```

**Önerilen indeksler (F0B):** `evidence_segments(video_id)`, `evidence_segments(category_attribute)`,
`insight_claims(product_name, category_key)`, `insight_claims(hemensec_ready)`,
`claim_evidence_links(segment_id)`, `audit_events(entity_type, entity_id)`.

### 3.1 Eski içgörü alanı → yeni claim_type eşlemesi (süreklilik)

| Bugünkü `product_insights_json` alanı | Yeni `claim_type` | Not |
|---|---|---|
| `artilar[]` | `PRO` | her madde → bir claim (kanonik niteliğe bağlanır) |
| `eksiler[]` | `CON` | |
| `sorunlar[]` | `PROBLEM` | |
| `rakip_karsilastirma[]` | `COMPARISON` | karşı ürün `conflict`/karşılaştırma metası ile |
| `satin_alma_etkenleri[]` | `PURCHASE_FACTOR` | |
| `kriterler[]` | (claim değil) | hangi `canonical_attribute`'ların **ele alındığını** işaretler |
| `guvenilirlik` (serbest metin) | → `evidence_segments.source_quality` (yapısal) + `RELIABILITY` claim | video başına yapısallaştırılır |

> Mevcut 13 içgörü JSON'u (X50, S8 MaxV, V16, Z30 …) F0'da **yeniden analizle** veya
> **yarı-otomatik backfill** ile claim/evidence'e taşınabilir; backfill **kayıplıdır**
> (eski metinde zaman damgası/alıntı sınırı yok). Bkz. RİSK R1/R5.

---

## 4. Claim JSON şeması (ihracat biçimi)

```json
{
  "claim_id": "clm_01J...",
  "run_id": "run_01J...",
  "category_key": "dikey_supurge",
  "product_name": "Dreame Z30",
  "claim_type": "PRO",
  "canonical_attribute": "fiyat_performans",
  "claim_text": "Fiyat/performans yüksek — Dyson'a kıyasla belirgin daha ucuz",
  "polarity": "POSITIVE",
  "evidence_segment_ids": ["seg_a1", "seg_b2", "seg_c3"],
  "video_count": 3,
  "independent_count": 3,
  "sponsored_count": 0,
  "unknown_count": 0,
  "conflict_status": "NONE",
  "conflict_note": null,
  "deterministic_confidence": 1.0,
  "hemensec_ready": true,
  "generated_at": "2026-06-20T00:00:00Z"
}
```

**Kurallar:**
- `claim_text` **kanonik** (tek doğru ifade); sayım artık string eşitliğine değil
  `canonical_attribute` + `claim_type`'a dayanır → bugünkü "byte-aynı string" kırılganlığı biter.
- `evidence_segment_ids` boş olamaz (kanıtsız claim yasak — "uydurma yok" kuralının yapısal hâli).
- `video_count`, `independent_count`, `sponsored_count` **türevdir**; `claim_evidence_links` +
  `evidence_segments.source_quality`'den **deterministik** üretilir (Claude yazmaz).

---

## 5. Evidence segment JSON şeması

```json
{
  "segment_id": "seg_b2",
  "video_id": "yWqP8zB8weU",
  "transcript_id": "yWqP8zB8weU",
  "start_sec": 412.0,
  "end_sec": 437.5,
  "text": "at full price the Z30 is the better value compared to the Dyson",
  "source_quality": "INDEPENDENT_EDITORIAL",
  "category_attribute": "fiyat_performans",
  "polarity": "POSITIVE",
  "relation_to_claim": "SUPPORTS"
}
```

**Kurallar:**
- `text` transcript'ten **birebir** kesit olmalı (parafraz/uydurma yasak; denetlenebilirlik).
- `start_sec/end_sec` ideal olarak Whisper segment zaman damgalarından gelir → bkz. RİSK R1.
- `category_attribute` mutlaka §8/§9 listesinden bir **anahtar** (serbest metin değil).
- `source_quality` video/kaynak düzeyinde bir kez belirlenir; tüm segmentleri miras alır.

---

## 6. Agent audit şeması + deterministic confidence

### 6.1 Agent run / audit JSON

```json
{
  "agent_run": {
    "agent_run_id": "ar_01J...",
    "agent_name": "AGENT_1_EVIDENCE",
    "agent_role": "transcript -> evidence_segments (kanonik niteliğe etiketli alıntı)",
    "model": "claude-code-routine",
    "input_ref": "video_id=yWqP8zB8weU; prompt=prompts/...md",
    "output_ref": {"segment_ids": ["seg_b2", "seg_b3"]},
    "status": "DONE",
    "started_at": "2026-06-20T00:00:00Z",
    "finished_at": "2026-06-20T00:00:09Z"
  },
  "audit_event": {
    "event_type": "EVIDENCE_ADDED",
    "actor": "ar_01J...",
    "entity_type": "segment",
    "entity_id": "seg_b2",
    "detail_json": {"category_attribute": "fiyat_performans", "polarity": "POSITIVE"},
    "reason": "Agent-1 çıkarımı"
  }
}
```

Önerilen ajan rolleri (F1+; **bu pakette kodlanmaz**):
`AGENT_1_EVIDENCE` (transcript → evidence_segments) · `AGENT_2_CLAIM` (evidence → insight_claims) ·
`AGENT_3_CONFLICT` (çelişki + source_quality doğrulama) · `AGENT_4_EXPORT_GATE`
(hemensec_ready kapısı). Her biri `agent_runs` + `audit_events` yazar.

### 6.2 deterministic_confidence formülü (taslak v0)

Yalnızca **deterministik** girdiler (LLM öz-güveni KULLANILMAZ):

```
Sabitler (ayarlanabilir):
  w_ind     = 1.0    # bağımsız video ağırlığı
  w_spo     = 0.4    # sponsorlu/firma-ilişkili video ağırlığı
  w_unk     = 0.15   # bilinmeyen kaynak
  TARGET    = 3.0    # ~3 bağımsız video = tam kapsama
  cf(NONE)  = 1.00 ;  cf(MINOR) = 0.75 ;  cf(MAJOR) = 0.45   # çelişki faktörü

Adımlar:
  W        = w_ind*independent_count + w_spo*sponsored_count + w_unk*unknown_count
  coverage = min(1.0, W / TARGET)
  dc       = round(coverage * cf(conflict_status), 2)
  # bağımsız kaynak yoksa tavan 0.50 (sponsorlu-yalnız iddia yüksek güven olamaz)
  if independent_count == 0:  dc = min(dc, 0.50)

hemensec_ready = (dc >= 0.60) AND (independent_count >= 1) AND (conflict_status != 'MAJOR')
```

**Gerçek veriyle doğrulama (önceki oturumun V16/Z30 verisi):**

| Claim | ind / spo | conflict | W | coverage | dc | ready? |
|---|---|---|---|---|---|---|
| Z30 `fiyat_performans` (PRO) | 3 / 0 | NONE | 3.0 | 1.00 | **1.00** | ✅ |
| Z30 `islak_temizlik` (PRO, H2H) | 1 / 0 | NONE | 1.0 | 0.33 | **0.33** | ❌ (dc<0.6) |
| V16 `sac_dolanmasi` (PRO) | 0 / 2 | NONE | 0.8 | 0.27 | **0.27** | ❌ (ind=0 → tavan + eşik) |
| Z30 `agirlik_denge` | 2 / 0 | **MAJOR** (hafif↔arka-ağır) | 2.0 | 0.67 | **0.30** | ❌ (MAJOR) |

> Bu tablo, önceki oturumda elle bulduğumuz **kaynak asimetrisini** (V16'nın 2/2 firma-ilişkili
> kaynağı → hiçbir V16 PRO claim'i Hemensec-ready olamaz) artık **deterministik ve denetlenebilir**
> kıldığını gösterir. Formül v0'dır; eşikler F3'te kalibre edilir.

---

## 7. source_quality enum'u (kaynak güven sınıfları)

| Değer | Anlam | Sayım kovası |
|---|---|---|
| `INDEPENDENT_PURCHASE` | Kanal cihazı kendi parasıyla almış | **independent** |
| `INDEPENDENT_EDITORIAL` | Bağımsız yayın/inceleme, açık sponsor yok | **independent** |
| `REVIEW_UNIT` | İnceleme ünitesi gönderilmiş (PR olası, firma ilişkisi) | **sponsored** |
| `SPONSORED` | Açık reklam/sponsorlu içerik | **sponsored** |
| `BRAND_OFFICIAL` | Markanın kendi kanalı | **sponsored** |
| `RETAILER` | Satıcı/mağaza kanalı | **sponsored** |
| `UNKNOWN` | Sınıflandırılamadı | **unknown** (sayımda ayrı) |

> Kritik kural: `REVIEW_UNIT` **independent değildir** (firma ilişkisi var). Bugünkü V16
> kaynaklarımız (`gqZqCrLzh0I`=PR/launch, `zWnQqHhSLMQ`=review unit) bu sınıfa düşer →
> `independent_count=0`. Bu sınıflama, `guvenilirlik` serbest-metninden **yapısal alana** taşınır.

---

## 8. Robot süpürge — kanonik nitelik listesi

(Kaynak: X50 Ultra vs S8 MaxV Ultra karşılaştırma kriterleri + robot domeni.)
Anahtar (ASCII, JOIN için sabit) · TR etiket:

| `canonical_attribute` | Etiket |
|---|---|
| `esik_asma` | Eşik / rampa tırmanma |
| `hali_performansi` | Halı toplama + halı algılama/kaldırma |
| `emis_gucu` | Emiş gücü (Pa) |
| `navigasyon_kapsama` | Navigasyon / harita / kapsama (LiDAR/kamera) |
| `paspaslama` | Paspas (titreşim/dönen ped, ısıtmalı su, ped kaldırma) |
| `kose_kenar` | Köşe / kenar (flexiarm, uzayan fırça-paspas) |
| `engelden_kacinma` | Engelden kaçınma (AI/obstacle) |
| `kamera_evcil_ai` | Kamera + AI nesne/evcil tanıma, güvenlik kamerası |
| `istasyon_otomasyonu` | İstasyon (oto boşaltma/yıkama/kurutma/deterjan) |
| `sac_dolanmasi` | Saç/tüy dolanması (anti-tangle ana fırça) |
| `gurultu` | Gürültü |
| `batarya` | Batarya / çalışma süresi-kapsamı |
| `toz_haznesi_robot` | Robot içi toz haznesi |
| `uygulama_akilli_ev` | Uygulama / harita düzenleme / no-go / sesli asistan |
| `takilma_sorunlari` | Takılma / sıkışma / arıza şikâyetleri |
| `fiyat` | Fiyat |
| `yedek_parca_servis` | Yedek parça / servis |
| `bakim_temizlik` | Bakım (paspas pedi/fırça/istasyon temizliği) |

---

## 9. Dikey süpürge — kanonik nitelik listesi

(Kaynak: V16 / Z30 dikey analiz çalışması + `product_insight_prompt_dikey_supurge.md`.)

| `canonical_attribute` | Etiket |
|---|---|
| `sac_dolanmasi` | Saç/tüy dolanması (anti-tangle) — **KRİTİK** |
| `emis_gucu` | Emiş gücü (Airwatt) |
| `batarya` | Batarya / çalışma süresi |
| `agirlik_denge` | Ağırlık / denge |
| `toz_haznesi` | Toz haznesi (kapasite + boşaltma kolaylığı) |
| `filtre` | Filtre (HEPA / yıkanabilir) |
| `baslik_cesitliligi` | Başlık çeşitliliği (motorlu/mini/yumuşak rulo/aydınlatmalı/pet) |
| `gurultu` | Gürültü |
| `islak_temizlik` | Islak temizlik / paspas modülü (Submarine / Pro Aqua) |
| `led_aydinlatma` | LED aydınlatma (zemin/başlık) |
| `mobilya_alti_erisim` | Mobilya altı erişim (eğilme / esnek boru) |
| `zemin_guvenligi` | Zemin güvenliği (parke / tekerlek) |
| `fiyat_performans` | Fiyat / performans |
| `yedek_parca_servis` | Yedek parça / servis |
| `kurulum_saklama` | Kurulum / saklama (duvar montaj / stand / şarj) |
| `kullanim_ergonomi` | Kullanım ergonomisi (tetik/düğme, tutuş) |
| `bakim_temizlik` | Bakım (hazne/filtre temizleme kolaylığı) |

> `sac_dolanmasi`, `emis_gucu`, `batarya`, `gurultu`, `fiyat/…`, `yedek_parca_servis`,
> `bakim_temizlik` iki listede **ortak**; ihracatta nitelik anahtarı kategoriyle
> birlikte (`category_key` + `canonical_attribute`) benzersizleşir.

---

## 10. Hemensec export contract taslağı

**Amaç:** Hemensec'e yalnızca **kanıta dayalı, eşik geçmiş** ürün iddialarını, kaynak-kalite
kırılımı ve güvenle vermek. **Ham transcript, ses, API anahtarı, iç skorlar ve `hemensec_ready=false`
claim'ler ASLA ihraç edilmez.**

```json
{
  "contract_version": "hemensec-export-1",
  "generated_at": "2026-06-20T00:00:00Z",
  "source_system": "youtube_research_agent",
  "product": {
    "category_key": "dikey_supurge",
    "product_name": "Dreame Z30",
    "run_id": "run_01J..."
  },
  "provenance": {
    "video_count_total": 3,
    "independent_videos": 3,
    "sponsored_videos": 0,
    "unknown_videos": 0,
    "analysis_method": "claude-code-routine (API'siz)",
    "disclaimer": "Bulgular videolarda SÖYLENENLERE dayanır; bağımsız laboratuvar testi değildir."
  },
  "claims": [
    {
      "canonical_attribute": "fiyat_performans",
      "claim_type": "PRO",
      "claim_text": "Fiyat/performans yüksek — Dyson'a kıyasla belirgin daha ucuz",
      "video_count": 3,
      "independent_count": 3,
      "sponsored_count": 0,
      "conflict_status": "NONE",
      "deterministic_confidence": 1.0,
      "evidence_excerpts": [
        {"video_id": "yWqP8zB8weU", "source_quality": "INDEPENDENT_EDITORIAL",
         "start_sec": 412.0, "end_sec": 437.5, "text": "<=200 krk birebir alıntı"}
      ]
    }
  ],
  "excluded_counts": {"not_ready_claims": 7, "major_conflict_claims": 1}
}
```

**Sözleşme kuralları:**
1. **Filtre:** yalnız `hemensec_ready = true` claim'ler `claims[]`'e girer; gerisi yalnız
   `excluded_counts` olarak sayılır (şeffaflık; sessiz kırpma yok).
2. **Kanıt kesiti:** her claim için en fazla birkaç **kısa** (≤200 krk) birebir alıntı +
   kaynak-kalite etiketi; **tam transcript verilmez** (telif/ToS — bkz. RİSK R6).
3. **Sayımlar deterministik**; Hemensec tarafı bunları yeniden hesaplamak zorunda kalmaz.
4. **Versiyonlu + "as of"**: `contract_version` + `run_id` ile tekrar üretilebilir; eski
   ihraç sabit kalır.
5. **Çıkış kapısı:** ihraç `AGENT_4_EXPORT_GATE`/CLI ile **explicit** tetiklenir; her ihraç
   `audit_events(EXPORTED)` yazar. **Otonomi yok.**
6. **Yön:** tek yönlü (yalnız okuma-üretme → dosya). Hemensec prod tablolarına **yazılmaz**;
   teslim, repo dışı bir export dosyası/uç noktası ile yapılır (F-EXPORT paketinde tanımlanır).

---

## 11. Riskler

| # | Risk | Etki | Azaltma |
|---|---|---|---|
| **R1** | Mevcut STT (`whisper_transcriber`) yalnız **tam metin** döndürüyor; segment **zaman damgası atılıyor**. `evidence_segments.start_sec/end_sec` doldurulamaz. | Kanıt zaman aralığı yok → izlenebilirlik zayıf | F0B/F1'de Whisper **segment çıktısını sakla** (kod değişikliği, ayrı pakette); o zamana dek `start/end` NULL + metin-eşleştirme fallback |
| **R2** | `transcripts` PK = `video_id`; **surrogate `transcript_id` yok**. | FK tasarımı belirsiz | `transcript_id = video_id` kabul et **veya** F0B'de transcripts'e surrogate `id` ekle (eklemeli) |
| **R3** | `source_quality` bugün **serbest metin** (`guvenilirlik`). Yapısal sınıflama yeni bir adım gerektirir. | `independent/sponsored_count` üretilemez | F1'de sınıflandırma ajanı + (gerekirse) `videos`'a eklemeli `source_quality` kolonu / ayrı `sources` tablosu |
| **R4** | Eski 13 içgörü JSON'u kanonik-string tabanlı; **çelişki/polarity/nitelik anahtarı yok**. | Backfill kayıplı | Tercihen **yeniden analiz**; değilse yarı-otomatik backfill + `audit_events` ile işaretleme |
| **R5** | Kanonik nitelik listeleri zamanla genişler (yeni model/özellik). | Anahtar kayması/çakışma | Listeyi **sürümle** (`schema_version`), yeni anahtarı yalnız ekle; eskiyi silme |
| **R6** | Hemensec'e transcript alıntısı = **telif/ToS** sorunu olabilir. | Hukuki | Kısa (≤200 krk) alıntı + kaynak künyesi; tam metin asla; gerekiyorsa yalnız parafraz/sayı |
| **R7** | Determinizm sınırı: evidence çıkarımı ve claim sentezi **Claude-routine** (öznel). | Tekrar-üretilebilirlik | Girdi/çıktı `agent_runs`'ta sabitlenir; `confidence` yalnız deterministik girdilerden; insan override `audit_events`'e yazılır |
| **R8** | Kapsam kayması: yeni katman mevcut pipeline'a sızabilir. | Çalışan sistem bozulur | Yeni tablolar **salt eklemeli**; mevcut 5 tabloya/komuta **dokunma**; F0B'de "boş repository layer" (iş mantığı yok) |
| **R9** | YouTube kota varsayımı güncellendi: `search.list` ~100 çağrı/gün ayrı bucket; invalid request + pagination maliyet doğurur. | Acquisition fazını etkiler | **Bu pakette search yok**; acquisition/otonomi fazında (F-ACQ) kota muhasebesine yansıt |

---

## 12. Sonraki paket önerisi — **F0B: migration + boş repository layer**

Kapsam (yalnız iskelet; iş mantığı/ajan **yok**):
1. **Eklemeli migration**: §3'teki 6 tabloyu + indeksleri oluştur (mevcut 5 tabloya dokunma;
   `init_db`/`migrate` idempotent kalır).
2. (Opsiyon) `transcripts`'e surrogate `id` ekle — R2.
3. **Boş repository layer**: `src/repository/*.py` — sadece CRUD imzaları + tip/şema doğrulama
   + birim testleri; **karar/sentez yok**.
4. **Smoke test**: yeni tablolar oluşuyor, eski akış (`report-products` vb.) **bozulmadan**
   çalışıyor (regresyon).
5. Ajan 1/2/3/4 **kodlanmaz** (sonraki paketler: F1 evidence, F2 claim, F3 conflict+confidence,
   F4 export-gate; ardından F-ACQ acquisition/kota, F-EXPORT Hemensec teslim).

**Başarı kriteri (F0A — bu paket):**
- [x] Mevcut sisteme dokunulmadı (yalnız okuma + 1 yeni doküman).
- [x] Yeni mimari **yalnız sözleşme** olarak yazıldı.
- [x] Claim/evidence zinciri netleşti (claim ↔ link ↔ segment ↔ video ↔ source_quality).
- [x] Eklenecek tablolar net (`product_runs, evidence_segments, insight_claims,
      claim_evidence_links, agent_runs, audit_events`).
- [x] Hemensec'e neyin gidebileceği net (yalnız `hemensec_ready` claim + kısa alıntı; ham veri yok).
- [x] Ajan 1/2/3/4 kodlanmadı.
- [x] Sonraki paket **F0B** olarak açılabilir.

---
*Üretim: Claude Code routine (API'siz). Bu doküman `youtube_research_agent/denetleme/` altındadır
ve mevcut çalışan hattı değiştirmez. Tüm DDL/şema/formül TASARIM'dır; uygulama F0B+.*
