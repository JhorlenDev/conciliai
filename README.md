# ConcilIA

Primeira entrega de um sistema novo e independente para conferência de PDFs bancários com texto selecionável. Não há login, integração externa, IA ou lançamentos contábeis.

## O que funciona

- Cadastro e seleção de clientes.
- Criação de conciliação por cliente, banco e período.
- PostgreSQL com migration Alembic inicial.
- Upload auditável de PDFs de extrato, comprovantes e notas fiscais.
- Extração de lançamentos de extrato no formato de colunas separado por `|`.
- Extração conservadora de comprovantes PIX/TED, inclusive vários comprovantes por PDF.
- Armazenamento do texto bruto, arquivo de origem e página.
- Tabelas responsivas para revisar extratos e comprovantes extraídos.
- Testes unitários da extração e normalização prioritárias.

## Próxima etapa

- Extração estruturada de notas fiscais.
- Edição, exclusão, restauração e marcação de revisão na interface.
- Motor de conciliação e tela de resultado.
- Visualização/remoção/reprocessamento de arquivos pela interface.

## Execução

1. Copie as variáveis: `cp .env.example .env`. O PostgreSQL do projeto é exposto na porta `5433`, evitando conflito com instalações locais.
2. Inicie o banco: `docker compose up -d postgres`.
3. Backend:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

4. Frontend, em outro terminal:

```bash
cd frontend
npm install
npm run dev
```

Abra `http://localhost:3000`. A documentação da API está em `http://localhost:8000/docs`.

## Testes

Com o ambiente virtual do backend ativado:

```bash
cd backend
pytest
```

## Estrutura

- `frontend/`: Next.js, TypeScript, Tailwind e componentes de interface.
- `backend/`: FastAPI, SQLAlchemy, Alembic, PyMuPDF e RapidFuzz.
- `backend/alembic/`: migration inicial PostgreSQL.
- `backend/tests/`: testes da extração de comprovantes.
