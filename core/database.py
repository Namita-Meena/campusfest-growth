"""Persistence layer.

Production: Supabase PostgreSQL through the official supabase-py client, using a
SECRET key that only exists in Streamlit's server-side secrets. Row Level
Security is enabled on every table with no public policies (sql/schema.sql), so
the database cannot be read or written with the publishable key.

Local development / tests: if no Supabase credentials are configured, the app
falls back to a local SQLite file. That fallback is NOT persistent on Streamlit
Community Cloud and the sidebar says so.

The original 2025 dataset is never stored here: it is read-only (core/historical.py).
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from pathlib import Path

from . import seed

PK = {"settings": "key", "campaigns": "id", "campaign_metrics": "id", "experiment_results": "id",
      "tasks": "id", "decision_logs": "id"}
JSON_COLS = {"settings": ["value"], "experiment_results": ["inputs"]}
_LOCAL_DB = Path(__file__).resolve().parent.parent / "data" / "simulated" / "local_workspace.sqlite"


def get_secret(name: str, default=None):
    val = os.environ.get(name)
    if val:
        return val
    try:
        import streamlit as st
        if name in st.secrets:
            return st.secrets[name]
    except Exception:
        pass
    return default


class SQLiteStore:
    """Tiny document store (one JSON blob per row) used only without Supabase."""
    backend = "Local SQLite (not persistent on Streamlit Cloud)"

    def __init__(self, path=None):
        self.path = str(path or os.environ.get("CAMPUSFEST_LOCAL_DB") or _LOCAL_DB)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        for t in PK:
            self._conn.execute(f"create table if not exists {t} (pk text primary key, data text not null)")
        self._conn.commit()

    def fetch(self, table):
        with self._lock:
            cur = self._conn.execute(f"select data from {table}")
            return [json.loads(r[0]) for r in cur.fetchall()]

    def upsert(self, table, rows):
        if not rows:
            return
        with self._lock:
            self._conn.executemany(f"insert or replace into {table} (pk, data) values (?, ?)",
                                   [(str(r[PK[table]]), json.dumps(r, default=str)) for r in rows])
            self._conn.commit()

    def delete(self, table, ids):
        with self._lock:
            self._conn.executemany(f"delete from {table} where pk = ?", [(str(i),) for i in ids])
            self._conn.commit()

    def clear(self, table):
        with self._lock:
            self._conn.execute(f"delete from {table}")
            self._conn.commit()


class SupabaseStore:
    backend = "Supabase PostgreSQL (persistent)"

    def __init__(self, url, key):
        from supabase import create_client
        self.client = create_client(url, key)

    def fetch(self, table):
        return self.client.table(table).select("*").execute().data or []

    def upsert(self, table, rows):
        if rows:
            self.client.table(table).upsert(rows, on_conflict=PK[table]).execute()

    def delete(self, table, ids):
        if ids:
            self.client.table(table).delete().in_(PK[table], [str(i) for i in ids]).execute()

    def clear(self, table):
        self.client.table(table).delete().neq(PK[table], "__never__").execute()


_store = None
_cache = {"at": 0.0, "data": None}
_CACHE_SECONDS = 20
_lock = threading.Lock()
last_error = None


def get_store():
    """Return the active store, creating it (and seeding an empty workspace) once."""
    global _store, last_error
    if _store is None:
        with _lock:
            if _store is None:
                url, key = get_secret("SUPABASE_URL"), get_secret("SUPABASE_KEY")
                store = None
                if url and key:
                    try:
                        store = SupabaseStore(str(url).strip(), str(key).strip())
                        store.fetch("settings")  # connectivity + schema check
                    except Exception as e:  # fall back but remember why
                        last_error = f"Supabase connection failed: {type(e).__name__}: {e}"
                        store = None
                if store is None:
                    store = SQLiteStore()
                if not store.fetch("campaigns"):
                    _write_seed(store)
                _store = store
    return _store


def use_store(store):
    """Tests: inject a store explicitly."""
    global _store
    _store = store
    invalidate()
    if not store.fetch("campaigns"):
        _write_seed(store)


def _write_seed(store):
    store.upsert("settings", seed.seed_settings())
    store.upsert("campaigns", seed.seed_campaigns())
    store.upsert("campaign_metrics", seed.seed_metrics())
    store.upsert("experiment_results", seed.seed_experiments())
    store.upsert("tasks", seed.seed_tasks())


def reset_demo():
    """Restore the simulated workspace to its seeded week-4 scenario. Historical data is untouched."""
    store = get_store()
    for t in PK:
        store.clear(t)
    _write_seed(store)
    invalidate()


def invalidate():
    _cache["data"] = None


def load_all(force=False) -> dict:
    """All workspace tables as lists of dicts (cached for a few seconds, cleared on every write)."""
    if force or _cache["data"] is None or time.time() - _cache["at"] > _CACHE_SECONDS:
        store = get_store()
        data = {t: store.fetch(t) for t in PK}
        data["settings"] = {r["key"]: r["value"] for r in data["settings"]}
        _cache.update(at=time.time(), data=data)
    return _cache["data"]


def upsert(table, rows):
    get_store().upsert(table, rows if isinstance(rows, list) else [rows])
    invalidate()


def delete(table, ids):
    get_store().delete(table, ids if isinstance(ids, list) else [ids])
    invalidate()


def save_setting(key, value):
    upsert("settings", [{"key": key, "value": value}])
