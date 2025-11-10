# app/seed.py
from __future__ import annotations
from datetime import date
from random import randint, choice, random, seed as rndseed
from pathlib import Path
from sqlalchemy import text
from sqlmodel import Session
from .db import engine, init_db, DB_PATH
from .models import Cliente, Produto, Pedido, ItemPedido, Pagamento

# ---------- Parâmetros do seed (ajuste à vontade) ----------
ANOS = [2023, 2024, 2025]
CLIENTES = 200
PRODUTOS = 60
PEDIDOS_POR_MES_MIN = 40
PEDIDOS_POR_MES_MAX = 80
ITENS_POR_PEDIDO_MIN = 1
ITENS_POR_PEDIDO_MAX = 4
FORMAS = ["cartao", "pix", "boleto"]
CIDADES = [
    ("São Paulo","SP"), ("Rio de Janeiro","RJ"), ("Belo Horizonte","MG"),
    ("Curitiba","PR"), ("Porto Alegre","RS"), ("Salvador","BA"),
    ("Fortaleza","CE"), ("Recife","PE"), ("Florianópolis","SC"),
]
CATEGORIAS = ["Eletrônicos","Acessórios","Mobiliário","Papelaria","Serviços"]

rndseed(42)  # determinístico

def _mk_nome_prod(i: int) -> str:
    base = ["Notebook","Mouse","Teclado","Cadeira","Monitor","Impressora","Headset","HD Externo",
            "Webcam","Cabo HDMI","Caderno","Caneta","Suporte Notebook","Mesa Escritório"]
    return f"{choice(base)} {i}"

def run() -> None:
    init_db()
    print(f"Usando DB em: {Path(DB_PATH).resolve()}")

    with Session(engine) as s:
        # limpa na ordem certa (FKs)
        s.exec(text("DELETE FROM pagamento"))
        s.exec(text("DELETE FROM itempedido"))
        s.exec(text("DELETE FROM pedido"))
        s.exec(text("DELETE FROM produto"))
        s.exec(text("DELETE FROM cliente"))

        # clientes
        clientes: list[Cliente] = []
        for i in range(CLIENTES):
            cidade, uf = choice(CIDADES)
            c = Cliente(
                nome=f"Cliente {i+1}",
                email=f"cliente{i+1}@ex.com",
                cidade=cidade,
                estado=uf,
            )
            s.add(c); clientes.append(c)

        # produtos
        produtos: list[Produto] = []
        for i in range(PRODUTOS):
            nome = _mk_nome_prod(i+1)
            cat = choice(CATEGORIAS)
            preco = round(50 + 3000 * random(), 2)
            p = Produto(nome=nome, categoria=cat, preco_base=preco)
            s.add(p); produtos.append(p)

        s.commit()  # garante IDs

        # pedidos + itens + pagamentos
        total_pedidos = 0
        for ano in ANOS:
            for mes in range(1, 13):
                for _ in range(randint(PEDIDOS_POR_MES_MIN, PEDIDOS_POR_MES_MAX)):
                    cli = choice(clientes)
                    ped = Pedido(data=date(ano, mes, randint(1, 28)), cliente_id=cli.id)
                    s.add(ped); s.flush()  # libera ped.id

                    total = 0.0
                    for _ in range(randint(ITENS_POR_PEDIDO_MIN, ITENS_POR_PEDIDO_MAX)):
                        pr = choice(produtos)
                        q = randint(1, 5)
                        price = round(pr.preco_base * (0.85 + 0.35 * random()), 2)
                        s.add(ItemPedido(pedido_id=ped.id, produto_id=pr.id, quantidade=q, preco_unitario=price))
                        total += q * price

                    s.add(Pagamento(pedido_id=ped.id, forma=choice(FORMAS), valor=round(total, 2), status="liquidado"))
                    total_pedidos += 1

        s.commit()

        # contagens finais
        def count(tbl): return s.exec(text(f"SELECT COUNT(*) FROM {tbl}")).one()[0]
        print("Contagens após seed:")
        print("  clientes :", count("cliente"))
        print("  produtos :", count("produto"))
        print("  pedidos  :", count("pedido"))
        print("  itens    :", count("itempedido"))
        print("  pagamentos:", count("pagamento"))

if __name__ == "__main__":
    run()
    print("Seed OK ✔")
