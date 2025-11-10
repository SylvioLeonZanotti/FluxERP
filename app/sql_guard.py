# app/sql_guard.py
from __future__ import annotations
import re
from typing import Tuple

# Palavras perigosas/DDL/DML fora SELECT
_BAD_TOKENS = (
    r"\binsert\b", r"\bupdate\b", r"\bdelete\b", r"\bdrop\b", r"\btruncate\b",
    r"\balter\b", r"\bcreate\b", r"\battach\b", r"\bvaccum\b", r"\bpragma\b",
    r"\breindex\b", r"\breplace\b", r"\bgrant\b", r"\brevoke\b"
)
_BAD_RE = re.compile("|".join(_BAD_TOKENS), re.IGNORECASE)

# Comentários SQL e fences markdown
_COMMENT_RE = re.compile(r"(--[^\n]*\n)|(/\*.*?\*/)", re.DOTALL)
_FENCE_RE = re.compile(r"^```(?:sql)?\s*|```$", re.IGNORECASE | re.MULTILINE)

def _strip_markdown_and_comments(sql: str) -> str:
    sql = _FENCE_RE.sub("", sql).strip()
    # garante quebra no final de linha para remover comentários linha
    if not sql.endswith("\n"):
        sql += "\n"
    sql = _COMMENT_RE.sub("\n", sql).strip()
    return sql

def _only_select(sql: str) -> bool:
    # ignora espaços, parênteses iniciais e WITH RECURSIVE
    s = sql.lstrip()
    return s[:6].lower() == "select" or s[:4].lower() == "with"

def _has_semicolon(sql: str) -> bool:
    # bloqueia múltiplas sentenças
    return ";" in sql

def _inject_limit(sql: str, max_rows: int) -> str:
    # Se já houver LIMIT, mantém; senão injeta
    # Heurística simples: adiciona no final
    if re.search(r"\blimit\s+\d+", sql, flags=re.IGNORECASE):
        return sql
    suffix = " LIMIT {}".format(max_rows)
    # remove ponto-e-vírgula final, se existir
    sql = sql.rstrip().rstrip(";")
    return sql + suffix

def sanitize(sql: str, max_rows: int) -> Tuple[bool, str]:
    """
    Valida uma query gerada pela LLM. Permite apenas SELECT/CTE e injeta LIMIT.
    Retorna (ok, sql_ou_msg).
    """
    if not sql or not isinstance(sql, str):
        return False, "SQL vazio."

    sql_clean = _strip_markdown_and_comments(sql)

    if _BAD_RE.search(sql_clean):
        return False, "Comando não permitido. Apenas SELECT/CTE são aceitos."

    if not _only_select(sql_clean):
        return False, "Apenas SELECT é permitido."

    if _has_semicolon(sql_clean):
        return False, "Múltiplas sentenças não são permitidas."

    safe_sql = _inject_limit(sql_clean, max_rows)
    return True, safe_sql
