# **FluxERP**

**Aviso**: Apesar do nome, este projeto **não é um ERP**. É um **assistente de perguntas em linguagem natural sobre um banco de dados**. Você envia um arquivo `.db` (SQLite), faz perguntas em português simples e o sistema:
1) **Gera a consulta SQL** com IA (Ollama)  
2) **Exibe a SQL gerada** para conferência  
3) **Executa a SQL** no banco enviado (modo leitura)  
4) **Retorna os resultados** (JSON)  

O foco é **perguntar qualquer coisa sobre os dados** e **ver a SQL correspondente** de forma transparente.

## ✨ O que o sistema faz

- Recebe um banco **SQLite** (upload de `.db` ou uso de um `.db` existente)
- Converte **Linguagem Natural → SQL** com **Ollama** (LLM local)
- Mostra **a SQL gerada antes de executar**
- Executa **somente consultas de leitura** (SELECT) por segurança
- Retorna resultados em **JSON**
- Documentação interativa via **Swagger UI**


## 🧠 Integração com IA (Ollama)

Este projeto inclui capacidade de processamento via modelos **LLM locais** usando **Ollama**.  
Isso permite rodar análise de dados, preenchimento inteligente e automações sem depender de APIs pagas.

### Instale o Ollama
Baixe conforme seu sistema operacional:

https://ollama.com/download

Após instalar, execute (exemplo com o modelo `phi3`):

Ou outro modelo que desejar:
ollama pull llama3

Como testar se está funcionando❓ 

ollama run phi3 "Olá, tudo bem?"
Se responder, a IA local está pronta. 🆗

## ✨ **Principais Funcionalidades**

- API REST completa e documentada automaticamente (Swagger UI)
- Banco de dados local em SQLite (podendo ser trocado para Postgres facilmente)
- Estrutura limpa e escalável (seguindo boas práticas)
- Validação robusta de dados utilizando Pydantic
- Integração com Ollama para IA local
- Arquitetura pronta para módulos Financeiro, Estoque e Vendas


## 🚀 **Tecnologias Utilizadas**

| Tecnologia              | Função                     |
| ----------------------- | -------------------------- |
| **Python 3.12+**        | Linguagem principal        |
| **FastAPI**             | Criação da API backend     |
| **Uvicorn**             | Servidor ASGI              |
| **SQLAlchemy + SQLite** | Banco de dados local       |
| **Pydantic**            | Validação de modelos       |
| **Swagger UI**          | Documentação automática    |
| **Ollama (LLM local)**  | Processamento IA sem nuvem |


## 📂 **Estrutura do Projeto**

```
FluxERP/
├── app/
│   ├── main.py          # Ponto de entrada da API
│   ├── database.py      # Configuração do banco
│   ├── models.py        # Modelos ORM (SQLite / SQLAlchemy)
│   ├── utils.py         # Funções de suporte
│   ├── .env             # Configurações sensíveis (opcional)
│   └── .env.example     # Exemplo de configuração
├── uploads/
│   └── erp.db           # Banco SQLite
└── requirements.txt      # Dependências do projeto
```


## ⚙️ **Instalação e Execução**

### 1. Clone o repositório
```bash
git clone https://github.com/sylvioleonzanotti/FluxERP.git
cd FluxERP
```

### 2. Crie e ative o ambiente virtual
```bash
python -m venv .venv
source .venv/bin/activate     # Linux / Mac
.\.venv\Scripts\activate      # Windows
```

### 3. Instale as dependências
```bash
pip install -r requirements.txt
```

### 4. Inicie o servidor
```bash
uvicorn app.main:app --reload --port 8001
```

### 5. Certifique-se de que o Ollama está rodando
```bash
ollama serve
```

### 6. Acesse no navegador:
```
http://127.0.0.1:8001/
```

### 7. Acesse no navegador a documentação:
```
http://127.0.0.1:8001/docs
```

Você terá acesso ao painel visual interativo da API. ✨


## 🗄️ Banco de Dados

O banco padrão utilizado é **SQLite**, armazenado no diretório `uploads/`.

Para resetar:
```bash
rm uploads/erp.db
```

Ou recriar via script:
```bash
python app/database.py
```

Se quiser migrar para **PostgreSQL**, basta:
- Editar `database.py` e alterar o `DATABASE_URL`
- Instalar `psycopg2-binary` ou `asyncpg`


## 🧱 Qualidades do FluxERP

| Característica | Benefício |
|---------------|-----------|
| Código limpo e organizado | Fácil manutenção |
| Sem dependências pesadas | Roda até em máquinas simples |
| Estrutura modular | Escalável para sistemas maiores |
| Banco local ou remoto | Flexível para dev → produção |
| API documentada automaticamente | Desenvolvimento rápido |


**Request (JSON):**
json
{
  "question": "Quais clientes compraram mais de R$ 500 em novembro?"
}
```
**Resposta (JSON):**
{
  "sql": "SELECT c.nome, SUM(p.total) AS total ...",
  "rows": [
    {"nome": "ACME Ltda", "total": 1200.50},
    {"nome": "Mercury SA", "total": 750.00}
  ]
}

```
## 🔮 Rumo à evolução

Algumas funcionalidades futuras planejadas:

- Autenticação com JWT
- Controle de permissões por usuário/nível de acesso
- Dashboard administrativo (Web UI)
- Módulo Financeiro + Estoque + Vendas
- Conexão nativa com PostgreSQL / MySQL
- Versão SaaS multi-tenant

> O FluxERP é o ponto de partida ideal para quem deseja construir um ERP moderno do zero com arquitetura profissional.

## 📸 **Screenshots interface**
<img width="1919" height="946" alt="image" src="https://github.com/user-attachments/assets/04eb8e1b-9446-4fcd-ac4c-3adfeb0a35d0" />



## 📄 Licença

Este projeto pode ser utilizado livremente para estudo, uso interno ou evolução própria.

