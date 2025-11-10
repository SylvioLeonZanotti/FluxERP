# app/models.py
from __future__ import annotations
from datetime import date
from typing import Optional
from sqlmodel import Field, SQLModel

class Cliente(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    nome: str
    email: str
    cidade: str
    estado: str

class Produto(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    nome: str
    categoria: str
    preco_base: float

class Pedido(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    data: date
    cliente_id: int = Field(foreign_key="cliente.id")

class ItemPedido(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    pedido_id: int = Field(foreign_key="pedido.id")
    produto_id: int = Field(foreign_key="produto.id")
    quantidade: int
    preco_unitario: float

class Pagamento(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    pedido_id: int = Field(foreign_key="pedido.id")
    forma: str   # cartao, pix, boleto
    valor: float
    status: str  # liquidado, pendente
