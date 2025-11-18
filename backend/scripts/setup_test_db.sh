#!/bin/bash
# Script per creare il database di test per E2E tests

set -e

echo "🔧 Setting up test database for E2E tests..."

# Verifica che PostgreSQL sia in esecuzione
if ! docker-compose ps postgres | grep -q "Up"; then
    echo "⚠️  PostgreSQL non è in esecuzione. Avvio..."
    docker-compose up -d postgres
    echo "⏳ Attendo che PostgreSQL sia pronto..."
    sleep 5
fi

# Crea database di test (ignora errore se esiste già)
echo "📦 Creating test database..."
docker-compose exec -T postgres psql -U knavigator -c "CREATE DATABASE knowledge_navigator_test;" 2>/dev/null || \
    echo "ℹ️  Database 'knowledge_navigator_test' esiste già (ok)"

echo "✅ Test database setup completo!"
echo ""
echo "Ora puoi eseguire i test E2E:"
echo "  cd backend"
echo "  source venv/bin/activate"
echo "  pytest tests/test_proactivity_e2e.py -v"

