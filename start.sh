#!/bin/bash

# Start all services for the Prediction Market Arbitrage System

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Starting Prediction Market Arbitrage System${NC}"

# Check if .env exists
if [ ! -f .env ]; then
    echo -e "${YELLOW}⚠️  .env file not found. Please run setup.sh first.${NC}"
    exit 1
fi

# Check if venv exists
if [ ! -d venv ]; then
    echo -e "${YELLOW}⚠️  Virtual environment not found. Please run setup.sh first.${NC}"
    exit 1
fi

# Function to cleanup on exit
cleanup() {
    echo -e "\n${YELLOW}Shutting down services...${NC}"
    pkill -P $$
    exit 0
}

trap cleanup SIGINT SIGTERM

# Start data collector in background
echo -e "${GREEN}Starting data collector...${NC}"
source venv/bin/activate
python -m src.scheduler &
SCHEDULER_PID=$!
echo -e "${GREEN}✓ Scheduler running (PID: $SCHEDULER_PID)${NC}"

# Wait a moment for scheduler to initialize
sleep 3

# Start Flask API in background
echo -e "${GREEN}Starting Flask API...${NC}"
python -m src.app &
API_PID=$!
echo -e "${GREEN}✓ API running on http://localhost:5000 (PID: $API_PID)${NC}"

# Wait for Flask to start
sleep 3

# Start React frontend
echo -e "${GREEN}Starting React frontend...${NC}"
cd frontend
npm start &
FRONTEND_PID=$!
cd ..
echo -e "${GREEN}✓ Frontend will open at http://localhost:3000 (PID: $FRONTEND_PID)${NC}"

echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✅ All services started successfully!${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════${NC}"
echo ""
echo "📊 Dashboard: http://localhost:3000"
echo "🔧 API:       http://localhost:5000"
echo ""
echo "Press Ctrl+C to stop all services"
echo ""

# Wait for all background processes
wait
