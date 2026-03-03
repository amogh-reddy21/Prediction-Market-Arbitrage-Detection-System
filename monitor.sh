#!/bin/bash
# Live monitoring dashboard for arbitrage system

clear

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

while true; do
    clear
    echo -e "${CYAN}╔════════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║          PREDICTION MARKET ARBITRAGE - LIVE MONITOR                ║${NC}"
    echo -e "${CYAN}╚════════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    # Check if scheduler is running
    SCHEDULER_PID=$(pgrep -f "python -m src.scheduler")
    if [ -n "$SCHEDULER_PID" ]; then
        echo -e "${GREEN}🟢 SCHEDULER: RUNNING${NC} (PID: $SCHEDULER_PID)"
    else
        echo -e "${RED}🔴 SCHEDULER: STOPPED${NC}"
    fi
    
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${YELLOW}📊 API HEALTH STATUS${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    mysql -u root -pPapichulo1221! arbitrage_db -e "
        SELECT 
            platform as Platform,
            status as Status,
            DATE_FORMAT(last_successful_call, '%H:%i:%s') as 'Last Call',
            consecutive_failures as Failures
        FROM api_health 
        ORDER BY platform;
    " 2>/dev/null
    
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${YELLOW}📈 DATABASE STATISTICS${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    mysql -u root -pPapichulo1221! arbitrage_db -e "
        SELECT 
            (SELECT COUNT(*) FROM matched_contracts) as 'Matched Contracts',
            (SELECT COUNT(*) FROM prices) as 'Price Records',
            (SELECT COUNT(*) FROM opportunities) as 'Opportunities',
            (SELECT COUNT(*) FROM bayesian_state) as 'Bayesian States';
    " 2>/dev/null
    
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${YELLOW}🎯 RECENT OPPORTUNITIES${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    OPPS=$(mysql -u root -pPapichulo1221! arbitrage_db -e "SELECT COUNT(*) FROM opportunities;" 2>/dev/null | tail -1)
    if [ "$OPPS" -gt 0 ]; then
        mysql -u root -pPapichulo1221! arbitrage_db -e "
            SELECT 
                id,
                ROUND(raw_spread * 100, 2) as 'Raw %',
                ROUND(fee_adjusted_spread * 100, 2) as 'Adjusted %',
                status,
                DATE_FORMAT(created_at, '%H:%i:%s') as Time
            FROM opportunities 
            ORDER BY created_at DESC 
            LIMIT 5;
        " 2>/dev/null
    else
        echo -e "${YELLOW}No opportunities detected yet. Waiting for matching markets...${NC}"
    fi
    
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${YELLOW}📝 LATEST LOG ENTRIES${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    tail -5 logs/scheduler.log 2>/dev/null | grep -E "INFO|WARNING|ERROR|SUCCESS" | tail -3
    
    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}Last updated: $(date '+%Y-%m-%d %H:%M:%S')${NC}"
    echo -e "${CYAN}Refreshing in 10 seconds... (Ctrl+C to exit)${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    
    sleep 10
done
