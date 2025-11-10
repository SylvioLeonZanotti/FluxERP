from sqlalchemy import event
from sqlmodel import SQLModel, Session, create_engine
from pathlib import Path
from functools import lru_cache

DB_PATH = (Path(__file__).resolve().parent.parent / "erp.db").resolve()

def _on_sqlite_connect(dbapi_conn, _conn_record):
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA foreign_keys = ON;")
    cur.execute("PRAGMA journal_mode = WAL;")
    cur.execute("PRAGMA synchronous = NORMAL;")
    cur.close()

def _make_engine(db_file: Path):
    engine = create_engine(
        f"sqlite:///{db_file}",
        connect_args={"check_same_thread": False},
        pool_pre_ping=True,
        future=True,
    )
    # registra o hook no Engine síncrono
    event.listen(engine, "connect", _on_sqlite_connect)
    return engine

_default_engine = _make_engine(DB_PATH)

def init_db() -> None:
    from . import models  # registra tabelas
    SQLModel.metadata.create_all(_default_engine)

def get_session() -> Session:
    return Session(_default_engine)

@lru_cache(maxsize=32)
def _engine_for(path_str: str):
    return _make_engine(Path(path_str))

def get_session_for(db_path: Path) -> Session:
    return Session(_engine_for(str(db_path.resolve())))
