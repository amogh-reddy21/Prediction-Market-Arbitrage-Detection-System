#!/bin/bash
# Simple script to start the arbitrage system

cd "/Users/amoghreddy/Desktop/Prediction Markets"

# Kill any existing processes
pkill -f "python.*src.scheduler" 2>/dev/null
pkill -f "python.*src.app" 2>/dev/null
sleep 1

echo "🚀 Starting Prediction Market Arbitrage System..."
echo ""

# Start scheduler in background
nohup "/Users/amoghreddy/Desktop/Prediction Markets/venv/bin/python" -m src.scheduler > logs/scheduler_main.log 2>&1 &
SCHEDULER_PID=$!
echo "✅ Scheduler started (PID: $SCHEDULER_PID)"

# Wait for scheduler to initialize
sleep 3

# Start API server in background
nohup "/Users/amoghreddy/Desktop/Prediction Markets/venv/bin/python" -m src.app > logs/api_main.log 2>&1 &
API_PID=$!
echo "✅ API server started (PID: $API_PID)"

sleep 2

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ System Running!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📊 API Health: http://localhost:5001/api/health"
echo "🔍 Live Opportunities: http://localhost:5001/api/live"
echo "📈 Statistics: http://localhost:5001/api/statistics"
echo ""
echo "📋 Logs:"
echo "   Scheduler: tail -f logs/scheduler_main.log"
echo "   API: tail -f logs/api_main.log"
echo ""
echo "🛑 To stop: pkill -f 'python.*src'"
echo ""
