# app/utils.py
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import List

from sqlmodel import SQLModel


def schema_markdown() -> str:
    """
    Gera um resumo em Markdown do esquema baseado nos modelos SQLModel locais.
    Lista tabelas, colunas (com tipo) e relacionamentos (FKs).
    """
    md_lines: List[str] = []
    metadata = SQLModel.metadata

    if not metadata.tables:
        return "/* Nenhuma tabela registrada em SQLModel.metadata */"

    # Ordena por nome para estabilidade
    for tbl_name in sorted(metadata.tables.keys()):
        table = metadata.tables[tbl_name]
        md_lines.append(f"### Tabela {tbl_name}")

        # Colunas
        cols = []
        for col in table.columns:
            col_type = str(col.type)
            # marcações úteis (PK / nullable)
            flags = []
            if col.primary_key:
                flags.append("PK")
            if not col.nullable:
                flags.append("NOT NULL")
            flag_txt = f" [{' ,'.join(flags)}]" if flags else ""
            cols.append(f"{col.name} {col_type}{flag_txt}")
        md_lines.append(f"Colunas: {', '.join(cols) if cols else '(nenhuma)'}")

        # FKs
        fks = []
        for fk in table.foreign_keys:
            # fk.column -> <ForeignKey target table.column>
            target_col = fk.column
            target_tbl = target_col.table.name if hasattr(target_col, "table") else "?"
            target_name = getattr(target_col, "name", "?")
            fks.append(f"{fk.parent.name} → {target_tbl}({target_name})")
        if fks:
            md_lines.append(f"Relacionamentos: {', '.join(fks)}")

        md_lines.append("")  # linha em branco entre tabelas

    return "\n".join(md_lines).strip() or "/* Esquema vazio */"


def schema_markdown_from_sqlite(db_path: Path) -> str:
    """
    Gera um resumo em Markdown do esquema (tabelas, colunas e FKs) a partir de um arquivo SQLite.
    Ignora tabelas internas do SQLite (sqlite_%).
    """
    if not db_path.exists():
        return f"/* Arquivo não encontrado: {db_path} */"

    lines: List[str] = []
    try:
        with sqlite3.connect(db_path) as con:
            # Lista tabelas de usuário
            cur = con.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name NOT LIKE 'sqlite_%' "
                "ORDER BY name"
            )
            tables = [row[0] for row in cur.fetchall()]
            if not tables:
                return "/* Banco sem tabelas de usuário */"

            for name in tables:
                lines.append(f"### Tabela {name}")

                # Colunas
                cols_info = con.execute(f"PRAGMA table_info({name})").fetchall()
                # PRAGMA table_info: cid, name, type, notnull, dflt_value, pk
                cols_txt = []
                for (_cid, cname, ctype, notnull, _dflt, pk) in cols_info:
                    flags = []
                    if pk == 1:
                        flags.append("PK")
                    if notnull == 1:
                        flags.append("NOT NULL")
                    flag_txt = f" [{' ,'.join(flags)}]" if flags else ""
                    cols_txt.append(f"{cname} {ctype or 'TEXT'}{flag_txt}")
                lines.append(f"Colunas: {', '.join(cols_txt) if cols_txt else '(nenhuma)'}")

                # Foreign Keys
                fk_info = con.execute(f"PRAGMA foreign_key_list({name})").fetchall()
                # PRAGMA foreign_key_list: id, seq, table, from, to, on_update, on_delete, match
                if fk_info:
                    rels = [f"{fk[3]} → {fk[2]}({fk[4]})" for fk in fk_info]
                    lines.append(f"Relacionamentos: {', '.join(rels)}")

                lines.append("")  # separador

    except Exception as e:
        return f"/* Erro ao ler SQLite: {e} */"

    return "\n".join(lines).strip() or "/* Banco sem tabelas de usuário */"

def known_tables(db_path: Path | None = None) -> set[str]:
    """
    Mantém compatibilidade com o sql_guard antigo.
    Se db_path for None, tenta 'erp.db' na raiz do projeto.
    """
    if db_path is None:
        db_path = Path(__file__).resolve().parent.parent / "erp.db"
    with sqlite3.connect(db_path) as con:
        cur = con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        return {r[0] for r in cur.fetchall()}