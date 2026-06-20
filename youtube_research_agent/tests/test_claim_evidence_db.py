"""YTI-F0B smoke/test — claim/evidence DB foundation + repository layer.

Çift çalışma modu:
  * Düz:    python tests/test_claim_evidence_db.py   (pytest GEREKMEZ — stdlib)
  * pytest: pytest -q tests/test_claim_evidence_db.py (test_* fonksiyonları)

Hepsi GEÇİCİ DB kullanır; canlı data/youtube.db'ye DOKUNMAZ. Gerçek DB üstündeki
idempotentlik, data/youtube.db'nin bir KOPYASI üzerinde doğrulanır (canlı dosya değişmez).
"""
from __future__ import annotations

import os
import shutil
import sqlite3
import sys
import tempfile

# Paket kökü (youtube_research_agent/) sys.path'e — komut nereden çalışırsa çalışsın import olsun.
_PKG_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PKG_ROOT not in sys.path:
    sys.path.insert(0, _PKG_ROOT)

from src import claim_evidence_repo as repo            # noqa: E402
from src import claim_evidence_schema                   # noqa: E402
from src import db                                      # noqa: E402
from src.utils import resolve_path                      # noqa: E402

OLD_TABLES = {"videos", "transcripts", "analyses", "job_log", "search_cache"}
NEW_TABLES = set(claim_evidence_schema.NEW_TABLES)


def _tables(conn: sqlite3.Connection) -> set:
    return {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}


def _table_sql(conn: sqlite3.Connection, name: str) -> str:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone()
    return row[0] if row else ""


def _temp_db_path() -> str:
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.remove(path)           # init_db dosyayı kendisi oluştursun
    return path


def _cleanup(path: str) -> None:
    for p in (path, path + "-wal", path + "-shm"):
        try:
            if os.path.exists(p):
                os.remove(p)
        except OSError:
            pass


def _insert_video(conn: sqlite3.Connection, video_id: str = "vid_test") -> str:
    """evidence_segments.video_id FK'sini sağlamak için minimal video satırı."""
    conn.execute(
        "INSERT INTO videos (video_id, channel_id, source_mode, category_key, product_name, status) "
        "VALUES (?,?,?,?,?,?)",
        (video_id, "chan_test", "PRODUCT_SEARCH", "dikey_supurge", "Test Urun", "ANALYZED"),
    )
    conn.commit()
    return video_id


def _setup_claim_and_segment(conn: sqlite3.Connection):
    """link testleri için minimal run + video + segment + claim kurar; (claim_id, segment_id) döner."""
    vid = _insert_video(conn, "vid_link")
    run_id = repo.create_product_run(conn, "dikey_supurge", "Test Urun", "EVIDENCE_EXTRACTION")
    seg_id = repo.insert_evidence_segment(
        conn, run_id, vid, "alıntı", "INDEPENDENT_EDITORIAL", "fiyat_performans")
    clm_id = repo.insert_insight_claim(
        conn, run_id, "dikey_supurge", "Test Urun", "PRO", "fiyat_performans", "iddia")
    return clm_id, seg_id


# --- testler ---------------------------------------------------------------

def test_init_creates_all_tables() -> None:
    """Temiz DB'de init_db -> 6 yeni + 5 eski tablo oluşur."""
    path = _temp_db_path()
    try:
        db.init_db(path)
        conn = db.get_conn(path)
        t = _tables(conn)
        assert NEW_TABLES <= t, f"eksik YENI tablo: {NEW_TABLES - t}"
        assert OLD_TABLES <= t, f"eksik ESKI tablo: {OLD_TABLES - t}"
        conn.close()
    finally:
        _cleanup(path)


def test_init_idempotent_preserves_data() -> None:
    """init_db iki kez çalışır (hata yok); araya eklenen veri korunur; tablo kümesi sabit."""
    path = _temp_db_path()
    try:
        db.init_db(path)
        conn = db.get_conn(path)
        _insert_video(conn, "vid_keep")
        before = _tables(conn)
        conn.close()

        db.init_db(path)                      # ikinci kez — idempotent olmalı
        conn = db.get_conn(path)
        after = _tables(conn)
        assert before == after, f"tablo kümesi değişti: {before ^ after}"
        n = conn.execute("SELECT COUNT(*) FROM videos WHERE video_id='vid_keep'").fetchone()[0]
        assert n == 1, "ikinci init mevcut veriyi bozdu"
        conn.close()
    finally:
        _cleanup(path)


def test_existing_five_tables_intact() -> None:
    """Eski 5 tablonun CREATE sql'i ikinci init sonrası DEĞİŞMEZ (ALTER/rebuild yok)."""
    path = _temp_db_path()
    try:
        db.init_db(path)
        conn = db.get_conn(path)
        sql_before = {name: _table_sql(conn, name) for name in OLD_TABLES}
        conn.close()

        db.init_db(path)
        conn = db.get_conn(path)
        for name in OLD_TABLES:
            assert _table_sql(conn, name) == sql_before[name], f"{name} DDL'i değişti"
        conn.close()
    finally:
        _cleanup(path)


def test_repository_insert_select() -> None:
    """Temel CRUD: run + evidence + claim + link + agent_run + audit_event; list/get çalışır."""
    path = _temp_db_path()
    try:
        db.init_db(path)
        conn = db.get_conn(path)
        vid = _insert_video(conn, "vid_repo")

        ar_id = repo.insert_agent_run(conn, "AGENT_TEST", model="claude-code-routine",
                                      output_ref={"k": "v"}, status="DONE")
        run_id = repo.create_product_run(conn, "dikey_supurge", "Test Urun",
                                         "EVIDENCE_EXTRACTION", agent_run_id=ar_id,
                                         input_video_count=1)
        assert repo.get_product_run(conn, run_id) is not None, "get_product_run None döndü"

        seg_id = repo.insert_evidence_segment(
            conn, run_id, vid, "birebir alıntı metni", "INDEPENDENT_EDITORIAL",
            "fiyat_performans", start_sec=12.0, end_sec=18.5, polarity="POSITIVE")
        clm_id = repo.insert_insight_claim(
            conn, run_id, "dikey_supurge", "Test Urun", "PRO", "fiyat_performans",
            "Fiyat/performans yüksek", video_count=1, independent_count=1,
            deterministic_confidence=0.33)
        repo.link_claim_evidence(conn, clm_id, seg_id, "SUPPORTS")
        repo.link_claim_evidence(conn, clm_id, seg_id, "SUPPORTS")  # tekrar -> IGNORE

        ev_id = repo.insert_audit_event(conn, ar_id, "CLAIM_CREATED", "claim", clm_id,
                                        detail_json={"attr": "fiyat_performans"})
        assert isinstance(ev_id, int), "audit event_id INTEGER olmalı"

        claims = repo.list_claims_for_product(conn, "Test Urun", "dikey_supurge")
        assert len(claims) == 1, f"beklenen 1 claim, bulunan {len(claims)}"
        assert claims[0]["canonical_attribute"] == "fiyat_performans"

        link_n = conn.execute(
            "SELECT COUNT(*) FROM claim_evidence_links WHERE claim_id=?", (clm_id,)).fetchone()[0]
        assert link_n == 1, "INSERT OR IGNORE çalışmadı (tekrar bağ eklendi)"
        seg_n = conn.execute(
            "SELECT COUNT(*) FROM evidence_segments WHERE run_id=?", (run_id,)).fetchone()[0]
        assert seg_n == 1, "evidence segment eklenmedi"
        conn.close()
    finally:
        _cleanup(path)


def test_link_idempotent_no_error() -> None:
    """Aynı (claim, segment) ikinci kez linklenince hata YOK, no-op (tek satır kalır)."""
    path = _temp_db_path()
    try:
        db.init_db(path)
        conn = db.get_conn(path)
        clm_id, seg_id = _setup_claim_and_segment(conn)
        repo.link_claim_evidence(conn, clm_id, seg_id, "SUPPORTS")
        repo.link_claim_evidence(conn, clm_id, seg_id, "SUPPORTS")   # tekrar -> no-op
        n = conn.execute("SELECT COUNT(*) FROM claim_evidence_links "
                         "WHERE claim_id=? AND segment_id=?", (clm_id, seg_id)).fetchone()[0]
        assert n == 1, f"idempotent değil: {n} satır"
        conn.close()
    finally:
        _cleanup(path)


def test_link_invalid_relation_raises() -> None:
    """Geçersiz relation (BAD_RELATION) CHECK ihlali -> LOUD hata; sessizce yutulmamalı."""
    path = _temp_db_path()
    try:
        db.init_db(path)
        conn = db.get_conn(path)
        clm_id, seg_id = _setup_claim_and_segment(conn)
        raised = False
        try:
            repo.link_claim_evidence(conn, clm_id, seg_id, "BAD_RELATION")
        except sqlite3.IntegrityError:
            raised = True
        assert raised, "geçersiz relation sessizce yutuldu (IntegrityError bekleniyordu)"
        n = conn.execute("SELECT COUNT(*) FROM claim_evidence_links").fetchone()[0]
        assert n == 0, "geçersiz relation tabloya yazıldı (yazılmamalıydı)"
        conn.close()
    finally:
        _cleanup(path)


def test_init_on_real_db_copy() -> None:
    """Canlı data/youtube.db'nin KOPYASI üzerinde: eski veri+tablolar korunur, 6 tablo eklenir,
    ikinci init idempotenttir. Canlı dosyaya DOKUNULMAZ. (DB yoksa atlanır.)"""
    live = resolve_path("data/youtube.db")
    if not live.exists():
        print("  (atlandi: data/youtube.db yok)")
        return
    path = _temp_db_path()
    try:
        shutil.copy(str(live), path)
        conn = db.get_conn(path)
        old_present = OLD_TABLES <= _tables(conn)
        vids_before = conn.execute("SELECT COUNT(*) FROM videos").fetchone()[0]
        conn.close()
        assert old_present, "kopyada eski tablolar eksik"

        db.init_db(path)                      # 6 yeni tabloyu ekler
        conn = db.get_conn(path)
        t = _tables(conn)
        assert NEW_TABLES <= t, f"kopyaya yeni tablolar eklenmedi: {NEW_TABLES - t}"
        assert OLD_TABLES <= t, "kopyada eski tablolar kayboldu"
        vids_after = conn.execute("SELECT COUNT(*) FROM videos").fetchone()[0]
        assert vids_after == vids_before, f"videos satır sayısı değişti {vids_before}->{vids_after}"
        conn.close()

        db.init_db(path)                      # idempotent
        conn = db.get_conn(path)
        assert conn.execute("SELECT COUNT(*) FROM videos").fetchone()[0] == vids_before
        conn.close()
        print(f"  (gercek DB kopyasi: videos={vids_before} korundu, 6 tablo eklendi, idempotent)")
    finally:
        _cleanup(path)


_ALL = [
    test_init_creates_all_tables,
    test_init_idempotent_preserves_data,
    test_existing_five_tables_intact,
    test_repository_insert_select,
    test_link_idempotent_no_error,
    test_link_invalid_relation_raises,
    test_init_on_real_db_copy,
]


def _main() -> int:
    failed = 0
    for t in _ALL:
        try:
            t()
            print(f"PASS  {t.__name__}")
        except Exception as e:                # noqa: BLE001
            failed += 1
            print(f"FAIL  {t.__name__}: {e}")
    print(f"\n=== SONUC: {len(_ALL) - failed}/{len(_ALL)} gecti ===")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(_main())
