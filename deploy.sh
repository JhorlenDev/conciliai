#!/usr/bin/env bash
set -e

echo "=== Atualizando código ==="
cd /root/conciliai
cp .env /tmp/conciliai-env-producao.backup
git pull origin main

echo "=== Verificando PostgreSQL ==="
docker compose up -d

echo "=== Atualizando backend ==="
cd /root/conciliai/backend
source .venv/bin/activate

set -a
source ../.env
set +a

pip install -r requirements.txt

if [ -f alembic.ini ]; then
    echo "Executando migrations..."
    alembic upgrade head
else
    echo "Criando/verificando tabelas..."
    PYTHONPATH=. python -c "import app.models; from app.core.database import Base, engine; Base.metadata.create_all(bind=engine); print('Banco verificado')"
fi

deactivate

echo "=== Compilando frontend ==="
cd /root/conciliai/frontend

set -a
source ../.env
set +a

echo "API utilizada: $NEXT_PUBLIC_API_URL"
npm install
npm run build

echo "=== Reiniciando sistema ==="
cd /root/conciliai

set -a
source .env
set +a

pm2 restart all --update-env
pm2 save

echo "=== Verificando serviços ==="
pm2 status
docker compose ps

curl -fsS http://localhost:8009/api/clientes > /dev/null
curl -fsS http://localhost:8009/api/processos-conciliacao > /dev/null

echo ""
echo "======================================"
echo "CONCILIAI ATUALIZADO COM SUCESSO!"
echo "Frontend: http://191.252.181.8:3009"
echo "======================================"