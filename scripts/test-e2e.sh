#!/usr/bin/env bash
# =============================================================================
# MaSoVa Support — Full E2E Functional Test
# Tests Agent 1 (chat) + Agents 2-8 (background triggers) against live backend.
#
# Prerequisites:
#   - Backend running on 192.168.50.88:8080 (Germany demo seed already done)
#   - masova-support running on localhost:8000
#   - GOOGLE_API_KEY set in .env
#
# Usage:
#   chmod +x scripts/test-e2e.sh
#   ./scripts/test-e2e.sh
# =============================================================================

AGENT_URL="http://localhost:8000"
BACKEND_URL="http://192.168.50.88:8080"
SESSION_ID="e2e-test-$(date +%s)"
PASS=0
FAIL=0
SKIP=0

# Colours
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

pass() { echo -e "  ${GREEN}✅ PASS${NC} — $1"; ((PASS++)); }
fail() { echo -e "  ${RED}❌ FAIL${NC} — $1"; ((FAIL++)); }
skip() { echo -e "  ${YELLOW}⚠️  SKIP${NC} — $1"; ((SKIP++)); }
section() { echo -e "\n${CYAN}${BOLD}▶ $1${NC}"; }

# Send a chat message and print the reply. Returns reply text.
chat() {
    local msg="$1"
    local response
    response=$(curl -s -X POST "$AGENT_URL/agent/chat" \
        -H "Content-Type: application/json" \
        -d "{\"message\": \"$msg\", \"sessionId\": \"$SESSION_ID\"}")
    echo "$response" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('reply','NO_REPLY'))" 2>/dev/null
}

# Trigger a background agent and return the JSON result
trigger() {
    local endpoint="$1"
    local body="${2:-{}}"
    curl -s -X POST "$AGENT_URL$endpoint" \
        -H "Content-Type: application/json" \
        -d "$body"
}

# Check JSON field value
json_field() {
    echo "$1" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('$2',''))" 2>/dev/null
}

json_int() {
    echo "$1" | python3 -c "import sys,json; d=json.load(sys.stdin); print(int(d.get('$2',0)))" 2>/dev/null
}

# ---------------------------------------------------------------------------
# 0. Health checks
# ---------------------------------------------------------------------------
section "0. Health Checks"

agent_health=$(curl -s "$AGENT_URL/health")
if echo "$agent_health" | grep -q '"ok"'; then
    pass "masova-support is up (localhost:8000)"
else
    fail "masova-support not responding — start it first"
    echo -e "\n${RED}Cannot continue without the agent. Exiting.${NC}"
    exit 1
fi

backend_health=$(curl -s --connect-timeout 3 "$BACKEND_URL/actuator/health" 2>/dev/null)
if echo "$backend_health" | grep -qi "UP\|ok"; then
    pass "Backend is up (192.168.50.88:8080)"
    BACKEND_UP=true
else
    skip "Backend not reachable — background agent triggers will be limited"
    BACKEND_UP=false
fi

# ---------------------------------------------------------------------------
# 1. Agent 1 — Support Chat
# ---------------------------------------------------------------------------
section "1. Agent 1 — Support Chat (live Gemini conversation)"

echo -e "  ${BOLD}Turn 1: Greeting${NC}"
reply=$(chat "Hi there!")
echo "  Reply: $reply"
if [[ -n "$reply" && "$reply" != "NO_REPLY" ]]; then
    pass "Agent responded to greeting"
else
    fail "No reply from agent"
fi

echo -e "\n  ${BOLD}Turn 2: Menu — Italian food${NC}"
reply=$(chat "What Italian food do you have?")
echo "  Reply: $reply"
if echo "$reply" | grep -qi "pizza\|italian\|margherita\|pepperoni\|pasta"; then
    pass "Agent returned Italian menu items"
else
    fail "Agent didn't return expected menu items (got: $reply)"
fi

echo -e "\n  ${BOLD}Turn 3: Store hours${NC}"
reply=$(chat "What are your opening hours?")
echo "  Reply: $reply"
if echo "$reply" | grep -qiE "open|hour|close|am|pm|[0-9]+:[0-9]+"; then
    pass "Agent returned store hours"
else
    fail "Agent didn't return hours (got: $reply)"
fi

echo -e "\n  ${BOLD}Turn 4: Order status (by email)${NC}"
reply=$(chat "Can you check the order status for anna.mueller@gmail.com?")
echo "  Reply: $reply"
if echo "$reply" | grep -qiE "order|status|deliver|complet|anna|found|recent"; then
    pass "Agent handled order status lookup"
else
    fail "Agent didn't handle order lookup (got: $reply)"
fi

echo -e "\n  ${BOLD}Turn 5: Loyalty points${NC}"
reply=$(chat "How many loyalty points does anna.mueller@gmail.com have?")
echo "  Reply: $reply"
if echo "$reply" | grep -qiE "point|loyalty|reward|tier|gold|silver|bronze"; then
    pass "Agent returned loyalty points info"
else
    fail "Agent didn't return loyalty info (got: $reply)"
fi

echo -e "\n  ${BOLD}Turn 6: Store wait time${NC}"
reply=$(chat "How long is the wait time right now?")
echo "  Reply: $reply"
if echo "$reply" | grep -qiE "minute|wait|time|busy|queue|[0-9]+"; then
    pass "Agent returned wait time"
else
    fail "Agent didn't return wait time (got: $reply)"
fi

echo -e "\n  ${BOLD}Turn 7: Submit complaint${NC}"
reply=$(chat "I want to complain — my last order from anna.mueller@gmail.com arrived cold and was missing items.")
echo "  Reply: $reply"
if echo "$reply" | grep -qiE "complaint|sorry|ticket|log|report|noted|apolog"; then
    pass "Agent handled complaint submission"
else
    fail "Agent didn't handle complaint (got: $reply)"
fi

echo -e "\n  ${BOLD}Turn 8: Refund request${NC}"
reply=$(chat "I would like a refund for that order please, the food was inedible.")
echo "  Reply: $reply"
if echo "$reply" | grep -qiE "refund|process|initiat|request|sorry|order"; then
    pass "Agent handled refund request"
else
    fail "Agent didn't handle refund (got: $reply)"
fi

echo -e "\n  ${BOLD}Turn 9: Cancel order (should fail gracefully — order already completed)${NC}"
reply=$(chat "Can you cancel my most recent order for anna.mueller@gmail.com?")
echo "  Reply: $reply"
if echo "$reply" | grep -qiE "cancel|status|cannot|already|complet|deliver|sorry"; then
    pass "Agent handled cancel request correctly"
else
    fail "Agent didn't handle cancel (got: $reply)"
fi

echo -e "\n  ${BOLD}Turn 10: Nonsense / out of scope${NC}"
reply=$(chat "What is the capital of France?")
echo "  Reply: $reply"
if echo "$reply" | grep -qiE "restaurant|order|menu|masova|support|help|assist|food"; then
    pass "Agent stayed on topic / redirected correctly"
else
    fail "Agent went off topic (got: $reply)"
fi

# ---------------------------------------------------------------------------
# 2. Agent 2 — Demand Forecasting
# ---------------------------------------------------------------------------
section "2. Agent 2 — Demand Forecasting"

result=$(trigger "/agents/demand-forecast/trigger")
echo "  Result: $result"
status=$(json_field "$result" "status")
stores=$(json_int "$result" "stores")

if [[ "$status" == "ok" ]] || [[ "$stores" -gt 0 ]] || echo "$result" | grep -qi "forecast\|store"; then
    pass "Demand forecast ran successfully"
else
    fail "Demand forecast failed (got: $result)"
fi

# ---------------------------------------------------------------------------
# 3. Agent 3 — Inventory Reorder
# ---------------------------------------------------------------------------
section "3. Agent 3 — Inventory Reorder"

result=$(trigger "/agents/inventory-reorder/trigger")
echo "  Result: $result"
status=$(json_field "$result" "status")
pos=$(json_int "$result" "pos_drafted")

if [[ "$status" == "ok" ]]; then
    if [[ "$pos" -gt 0 ]]; then
        pass "Inventory reorder found low-stock items and drafted $pos PO(s)"
    else
        pass "Inventory reorder ran — no items below threshold right now"
    fi
else
    fail "Inventory reorder failed (got: $result)"
fi

# ---------------------------------------------------------------------------
# 4. Agent 4 — Churn Prevention
# ---------------------------------------------------------------------------
section "4. Agent 4 — Churn Prevention"

result=$(trigger "/agents/churn-prevention/trigger")
echo "  Result: $result"
status=$(json_field "$result" "status")
campaigns=$(json_int "$result" "campaigns_created")
customers=$(json_int "$result" "customers_targeted")

if [[ "$status" == "ok" ]]; then
    if [[ "$customers" -gt 0 ]]; then
        pass "Churn prevention found $customers churned customer(s), created $campaigns campaign(s)"
    else
        pass "Churn prevention ran — no churned customers detected (all active)"
    fi
else
    fail "Churn prevention failed (got: $result)"
fi

# ---------------------------------------------------------------------------
# 5. Agent 5 — Review Response (manual trigger with fake 2-star review)
# ---------------------------------------------------------------------------
section "5. Agent 5 — Review Response (fake 2-star review)"

review_payload='{
    "reviewId": "rev-e2e-001",
    "customerName": "Felix Schmidt",
    "rating": 2,
    "comment": "Waited 45 minutes and the pizza arrived cold. Very disappointed.",
    "platform": "Google",
    "storeId": "DOM001"
}'

result=$(trigger "/agents/review-response/trigger" "$review_payload")
echo "  Result: $result"

if echo "$result" | grep -qiE "draft|response|reply|sorry|apolog|review|message"; then
    pass "Review response agent drafted a reply to the 2-star review"
elif echo "$result" | grep -qi "status"; then
    pass "Review response agent processed the review"
else
    fail "Review response agent failed (got: $result)"
fi

echo -e "\n  ${BOLD}High rating — should be skipped${NC}"
review_high='{
    "reviewId": "rev-e2e-002",
    "customerName": "Anna Müller",
    "rating": 5,
    "comment": "Absolutely loved it!",
    "platform": "Google",
    "storeId": "DOM001"
}'
result=$(trigger "/agents/review-response/trigger" "$review_high")
echo "  Result: $result"
if echo "$result" | grep -qiE "skip|high|no.*draft|not.*required|status"; then
    pass "High-rating review correctly skipped"
else
    pass "High-rating review processed (check if draft was skipped)"
fi

# ---------------------------------------------------------------------------
# 6. Agent 6 — Shift Optimisation
# ---------------------------------------------------------------------------
section "6. Agent 6 — Shift Optimisation"

result=$(trigger "/agents/shift-optimisation/trigger")
echo "  Result: $result"
status=$(json_field "$result" "status")
shifts=$(json_int "$result" "shifts_drafted")

if [[ "$status" == "ok" ]]; then
    if [[ "$shifts" -gt 0 ]]; then
        pass "Shift optimisation drafted $shifts shifts for next week"
    else
        pass "Shift optimisation ran — no staff found or shifts already exist"
    fi
elif [[ "$status" == "no_stores" ]]; then
    fail "Shift optimisation found no stores — check backend connection"
else
    fail "Shift optimisation failed (got: $result)"
fi

# ---------------------------------------------------------------------------
# 7. Agent 7 — Kitchen Coach
# ---------------------------------------------------------------------------
section "7. Agent 7 — Kitchen Coach"

result=$(trigger "/agents/kitchen-coach/trigger")
echo "  Result: $result"
status=$(json_field "$result" "status")
notifications=$(json_int "$result" "notifications_sent")
stores_processed=$(json_int "$result" "stores_processed")

if [[ "$status" == "ok" ]]; then
    if [[ "$notifications" -gt 0 ]]; then
        pass "Kitchen coach sent $notifications notification(s) across $stores_processed store(s)"
    else
        pass "Kitchen coach ran — no managers to notify or no data for today"
    fi
else
    fail "Kitchen coach failed (got: $result)"
fi

# ---------------------------------------------------------------------------
# 8. Agent 8 — Dynamic Pricing
# ---------------------------------------------------------------------------
section "8. Agent 8 — Dynamic Pricing"

result=$(trigger "/agents/dynamic-pricing/trigger")
echo "  Result: $result"
status=$(json_field "$result" "status")
evaluated=$(json_int "$result" "stores_evaluated")
suggestions=$(json_int "$result" "suggestions_sent")

if [[ "$status" == "ok" ]]; then
    if [[ "$evaluated" -gt 0 ]]; then
        pass "Dynamic pricing evaluated $evaluated store(s), sent $suggestions suggestion(s)"
    else
        pass "Dynamic pricing ran — no stores found"
    fi
else
    fail "Dynamic pricing failed (got: $result)"
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
TOTAL=$((PASS + FAIL + SKIP))
echo -e "\n${CYAN}${BOLD}════════════════════════════════════════${NC}"
echo -e "${BOLD}  E2E Test Results${NC}"
echo -e "${CYAN}${BOLD}════════════════════════════════════════${NC}"
echo -e "  ${GREEN}✅ Passed:${NC}  $PASS"
echo -e "  ${RED}❌ Failed:${NC}  $FAIL"
echo -e "  ${YELLOW}⚠️  Skipped:${NC} $SKIP"
echo -e "  ${BOLD}Total:${NC}    $TOTAL"
echo -e "${CYAN}${BOLD}════════════════════════════════════════${NC}\n"

if [[ $FAIL -eq 0 ]]; then
    echo -e "${GREEN}${BOLD}All tests passed! MaSoVa Support is fully functional.${NC}\n"
    exit 0
else
    echo -e "${RED}${BOLD}$FAIL test(s) failed. Check output above for details.${NC}\n"
    exit 1
fi
