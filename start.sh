#!/bin/bash

# Script per avviare Knowledge Navigator

echo "🚀 Avvio Knowledge Navigator..."

# Verifica Docker
if ! docker-compose ps | grep -q "Up"; then
    echo "📦 Avvio database..."
    docker-compose up -d
    sleep 5
fi

# Avvio Backend
echo "⚙️  Avvio backend..."
cd backend
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
echo $BACKEND_PID > /tmp/backend.pid
cd ..

# Avvio Frontend
echo "🎨 Avvio frontend..."
npm run dev &
FRONTEND_PID=$!
echo $FRONTEND_PID > /tmp/frontend.pid

sleep 5

echo ""
echo "✅ Servizi avviati!"
echo ""
echo "📊 Status:"
echo "  Backend:  http://localhost:8000"
echo "  Frontend: http://localhost:3003"
echo "  API Docs: http://localhost:8000/docs"
echo ""
echo "🛑 Per fermare: ./stop.sh o kill $(cat /tmp/backend.pid) $(cat /tmp/frontend.pid)"

