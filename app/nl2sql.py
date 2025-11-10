# app/nl2sql.py
from __future__ import annotations

"""
Gera SQL (SQLite) a partir de pergunta em PT-BR usando um modelo local via Ollama.
- Saída SEMPRE é SQL puro (apenas SELECT), sem cercas markdown.
- Carrega .env do diretório app/ (OLLAMA_BASE_URL, OLLAMA_MODEL, OLLAMA_TIMEOUT).
- Faz limpeza agressiva de markdown/backticks/labels e extrai bloco SQL se vier cercado.
- Inclui um utilitário opcional `summarize_result` (híbrido: NL→SQL→Execução→Resumo).

Dependências: httpx, python-dotenv
"""

import os
import re
import json
import asyncio
from pathlib import Path
from typing import Iterable, Sequence

import httpx
from dotenv import load_dotenv

# Garante que carregamos o .env correto (dentro de app/)
load_dotenv(dotenv_path=Path(__file__).parent / ".env")

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b-instruct")
OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "60"))

# ---------- Low level: chamada ao Ollama (chat) ----------

async def _ollama_chat(messages: list[dict], temperature: float = 0.0) -> str:
    """
    Chama /api/chat do Ollama e retorna o conteúdo textual da última mensagem.
    `messages` é no formato OpenAI-like: [{"role":"user"|"system"|"assistant","content":"..."}]
    """
    url = f"{OLLAMA_BASE_URL}/api/chat"
    payload = {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
        "options": {"temperature": temperature},
    }
    async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT) as cli:
        r = await cli.post(url, json=payload)
        r.raise_for_status()
        data = r.json()
        # Estrutura típica do Ollama: {"message":{"role":"assistant","content":"..."}}
        return (data.get("message") or {}).get("content", "") or ""


# ---------- Helpers de limpeza ----------

_CODEBLOCK_RE = re.compile(
    r"```(?:sql|SQL)?\s*(?P<body>[\s\S]*?)```", re.IGNORECASE
)

def _extract_sql_from_codeblock(text: str) -> str | None:
    """
    Se a LLM devolver um bloco cercado por ```sql ... ```, extrai só o conteúdo.
    """
    m = _CODEBLOCK_RE.search(text)
    if not m:
        return None
    return m.group("body").strip()


def _strip_markdown(text: str) -> str:
    """
    Remove cercas, prefixos "sql:" ou "SQL:", e linhas vazias iniciais.
    Mantém apenas o que parece ser a consulta.
    """
    text = text.strip()

    # Se houver codeblock, priorize-o.
    block = _extract_sql_from_codeblock(text)
    if block:
        text = block

    # Remove crases soltas
    text = text.strip("`").strip()

    # Remover prefixos como "SQL:", "sql:", "Consulta SQL:", etc.
    text = re.sub(r"^\s*(?i:sql|consulta|query)\s*:\s*", "", text).strip()

    # Caso o modelo escreva "SELECT ..." numa linha após algum cabeçalho
    # pegue a partir da primeira ocorrência de SELECT.
    m = re.search(r"(?is)\bselect\b", text)
    if m:
        text = text[m.start():].strip()

    # Remove ponto-e-vírgula final duplicado
    text = re.sub(r";+\s*$", "", text)

    return text.strip()


def _looks_like_select(sql: str) -> bool:
    """
    Heurística mínima: deve começar com SELECT (ignorando comentários/linhas vazias).
    """
    # Remove comentários SQL comuns
    s = re.sub(r"--.*?$", "", sql, flags=re.MULTILINE)
    s = re.sub(r"/\*[\s\S]*?\*/", "", s)  # /* ... */
    s = s.strip().lower()
    return s.startswith("select")


# ---------- Prompting ----------

_SQL_SYSTEM_INSTRUCTIONS = (
    "Você é um gerador de consultas SQL para SQLite. "
    "Responda APENAS com a consulta SQL, sem markdown, sem texto extra, sem explicações. "
    "Use exatamente os nomes de tabelas e colunas fornecidos. "
    "Gere somente SELECT (NUNCA use INSERT, UPDATE, DELETE, DROP, CREATE). "
    "Se precisar ordenar/limitar, use LIMIT com parcimônia."
)

_SQL_USER_TEMPLATE = """\
Esquema (SQLite):
{schema_md}

Pergunta (pt-BR):
{question}

Regras adicionais:
- Apenas SELECT.
- Sem comentários.
- Sem rodeios. Apenas a consulta.
- Se a pergunta for ambígua, assuma o caso mais comum (ex.: agregação por mês no ano citado).
- Prefira funções SQLite como strftime para agregações temporais.

SQL:
"""

async def question_to_sql(
    question: str,
    schema_md: str | None = None,
    *,
    retries: int = 1,
    temperature: float = 0.0,
) -> str | None:
    """
    Gera SQL puro (apenas SELECT) a partir de `question` + `schema_md`.
    - Limpa cercas/markdown automaticamente.
    - Retorna None se não houver como extrair SELECT plausível.

    `retries` faz 1 re-tentativa com instrução ainda mais rígida caso a primeira falhe.
    """
    schema_txt = schema_md or "/* Schema indisponível */"
    user_prompt = _SQL_USER_TEMPLATE.format(schema_md=schema_txt, question=question)

    async def _once(extra_hint: str = "") -> str | None:
        msgs = [
            {"role": "system", "content": _SQL_SYSTEM_INSTRUCTIONS + extra_hint},
            {"role": "user", "content": user_prompt},
        ]
        raw = await _ollama_chat(msgs, temperature=temperature)
        sql = _strip_markdown(raw)
        if not sql or not _looks_like_select(sql):
            return None
        return sql

    sql = await _once()
    if sql:
        return sql

    # Uma re-tentativa, apertando as regras
    for _ in range(max(0, retries)):
        strict = (
            " Responda EXATAMENTE uma única linha iniciando com SELECT e termine sem ponto-e-vírgula. "
            "Não inclua markdown ou explicações."
        )
        sql = await _once(strict)
        if sql:
            return sql

    return None


# ---------- (Opcional) Resumo textual do resultado ----------

_SUMMARY_SYSTEM = (
    "Você é um assistente analítico. Receberá o SQL executado, colunas e primeiras linhas do resultado. "
    "Responda em português do Brasil de forma concisa e factual. "
    "Use apenas os dados fornecidos; não extrapole."
)

_SUMMARY_USER_TEMPLATE = """\
Pergunta original:
{question}

SQL executado:
{sql}

Colunas:
{columns}

Amostra de linhas (até {max_rows}):
{rows_json}

Instruções:
- Resuma o achado principal em 2-4 frases objetivas.
- Se houver período/agrupamento, destaque a tendência (cresceu, caiu, picos/vales).
- Evite jargão técnico; foque em linguagem de gestão.
"""

async def summarize_result(
    question: str,
    columns: Sequence[str],
    rows: Iterable[Sequence[object]],
    sql: str,
    *,
    sample_rows: int = 20,
    max_chars: int = 500,
    temperature: float = 0.0,
) -> str:
    """
    Gera um texto curto (pt-BR) explicando o resultado.
    NÃO usa o banco; apenas resume `columns` + `rows` (amostra).

    Pode ser chamado no main.py após executar o SQL.
    """
    rows_list = list(rows)[: sample_rows]
    payload = _SUMMARY_USER_TEMPLATE.format(
        question=question,
        sql=sql,
        columns=json.dumps(list(columns), ensure_ascii=False),
        rows_json=json.dumps(rows_list, ensure_ascii=False),
        max_rows=sample_rows,
    )
    msgs = [
        {"role": "system", "content": _SUMMARY_SYSTEM},
        {"role": "user", "content": payload},
    ]
    out = await _ollama_chat(msgs, temperature=temperature)
    out = out.strip()
    if len(out) > max_chars:
        out = out[: max_chars - 3].rstrip() + "..."
    return out
