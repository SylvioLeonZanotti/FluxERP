# app/main.py
from __future__ import annotations

import os
import traceback
import uuid
from pathlib import Path
from typing import Any, List, Optional, Tuple

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlmodel import Session

from .db import get_session, get_session_for, init_db
from .nl2sql import question_to_sql  # <- sua versão já com suporte a schema_md (opcional)
from .sql_guard import sanitize
from .utils import schema_markdown_from_sqlite

# -----------------------------------------------------------------------------
# Config
# -----------------------------------------------------------------------------
load_dotenv()

RESULT_LIMIT: int = int(os.getenv("RESULT_LIMIT", "200"))
_UI_PATH = Path(__file__).parent / "ui" / "index.html"
_UPLOAD_DIR = Path(__file__).parent / "uploads"
_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Mapa in-memory: db_id -> path
_DB_REGISTRY: dict[str, Path] = {}

app = FastAPI(title="Agente NL - SQL", version="1.1")

# -----------------------------------------------------------------------------
# Models
# -----------------------------------------------------------------------------
class AskRequest(BaseModel):
    pergunta: str
    db_id: Optional[str] = None  # opcional: usa a base enviada


class AskResponse(BaseModel):
    ok: bool
    sql: Optional[str]
    rows: Optional[List[List[Any]]]
    columns: Optional[List[str]]
    mensagem: Optional[str]
    ambiguidade: Optional[str] = None
    answer: Optional[str] = None  # se seu nl2sql gerar resposta natural

# -----------------------------------------------------------------------------
# Startup
# -----------------------------------------------------------------------------
@app.on_event("startup")
def _startup() -> None:
    """Cria as tabelas do demo (erp.db) para quem não quiser enviar .db."""
    init_db()

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def _resolve_db(db_id: Optional[str]) -> Tuple[Session, Optional[Path]]:
    """
    Retorna (Session, db_path) para a base escolhida.
    - se db_id vier preenchido e existir no registry, usa essa base
    - caso contrário, usa a base demo padrão (erp.db)
    """
    if db_id and db_id in _DB_REGISTRY:
        db_path = _DB_REGISTRY[db_id]
        return get_session_for(db_path), db_path
    return get_session(), None  # base padrão

def _schema_md_for(db_path: Optional[Path]) -> str:
    """Gera markdown do schema da base informada (ou vazio se usar engine padrão
       e você preferir manter o comportamento antigo)."""
    if db_path is None:
        # Opcional: se quiser também descrever o schema da base padrão,
        # aponte para o caminho do erp.db aqui.
        default_db = Path(__file__).resolve().parent.parent / "erp.db"
        if default_db.exists():
            return schema_markdown_from_sqlite(default_db)
        return ""
    return schema_markdown_from_sqlite(db_path)

# -----------------------------------------------------------------------------
# Routes
# -----------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
def home() -> HTMLResponse:
    if not _UI_PATH.exists():
        return HTMLResponse("<h3>ui/index.html não encontrado</h3>", status_code=404)
    return HTMLResponse(_UI_PATH.read_text(encoding="utf-8"))

@app.get("/health")
def health() -> dict:
    return {"status": "ok"}

@app.post("/db/upload")
async def upload_db(file: UploadFile = File(...)) -> JSONResponse:
    """
    Recebe um arquivo .db, salva em app/uploads/ e registra um db_id para uso na sessão.
    Retorna { db_id: "...", name: "arquivo.db" }.
    """
    try:
        name = Path(file.filename or "base.db").name
        if not name.lower().endswith(".db"):
            return JSONResponse(
                status_code=400,
                content={"detail": "Envie um arquivo .db (SQLite)."},
            )
        db_id = uuid.uuid4().hex
        dst = _UPLOAD_DIR / f"{db_id}_{name}"
        content = await file.read()
        dst.write_bytes(content)
        _DB_REGISTRY[db_id] = dst
        return JSONResponse({"db_id": db_id, "name": name})
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"detail": f"Falha no upload: {e}"})


@app.post("/ask", response_model=AskResponse)
async def ask(payload: AskRequest) -> AskResponse:
    """
    Fluxo:
      1) valida pergunta
      2) escolhe base (padrão ou enviada)
      3) gera SQL via LLM (passando o schema quando disponível)
      4) sanitiza (apenas SELECT + LIMIT)
      5) executa e retorna resultado
    Nunca retorna 400 em casos esperados; volta ok=false + mensagem para a UI.
    """
    pergunta = (payload.pergunta or "").strip()
    if len(pergunta) < 3:
        return AskResponse(ok=False, sql=None, rows=None, columns=None,
                           mensagem="Pergunta muito curta.")

    # 1) resolve DB e schema (seu nl2sql pode usar isso no prompt)
    session, db_path = _resolve_db(payload.db_id)
    schema_md = _schema_md_for(db_path)

    # 2) NL -> SQL
    try:
        # se seu nl2sql aceitar schema_md como 2º argumento:
        # sql, answer = await question_to_sql(pergunta, schema_md=schema_md)
        # Aqui mantemos compatível caso só retorne SQL:
        result = await question_to_sql(pergunta, schema_md=schema_md)  # adapte ao seu nl2sql
        if isinstance(result, tuple):
            sql, answer = result
        else:
            sql, answer = result, None
        if not sql:
            return AskResponse(ok=False, sql=None, rows=None, columns=None,
                               mensagem="Falha ao gerar SQL.")
    except Exception as e:
        traceback.print_exc()
        return AskResponse(ok=False, sql=None, rows=None, columns=None,
                           mensagem=f"Erro ao gerar SQL: {e}")

    # 3) Guardrail
    ok, safe_sql_or_err = sanitize(sql, RESULT_LIMIT)
    if not ok:
        # devolve o SQL bruto para debug visual e a mensagem amigável
        return AskResponse(ok=False, sql=sql, rows=None, columns=None,
                           mensagem=safe_sql_or_err)

    safe_sql = safe_sql_or_err

    # 4) Execução
    try:
        with session as s:  # type: Session
            result = s.exec(text(safe_sql))
            rows = [list(r) for r in result.fetchall()]
            columns = list(result.keys())
    except Exception as e:
        traceback.print_exc()
        # NÃO levanta 400; devolve ok=false para a UI mostrar
        return AskResponse(ok=False, sql=safe_sql, rows=None, columns=None,
                           mensagem=f"Erro ao executar SQL: {e}")

    return AskResponse(ok=True, sql=safe_sql, rows=rows, columns=columns,
                       mensagem=None, answer=answer)

# Rota opcional para compatibilidade com sua UI antiga
@app.get("/ui", response_class=HTMLResponse)
def ui() -> HTMLResponse:
    return home()
