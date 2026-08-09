# Testing Guide untuk AI Agentic IDE

Panduan lengkap untuk menguji sistem Anda sebelum production.

## 🎯 Testing Strategy

### Phase 1: Manual Smoke Tests (15 menit)
Validasi bahwa sistem bisa running dengan baik.

### Phase 2: Automated Tests (1-2 jam)
Gunakan test framework untuk validasi komprehensif.

### Phase 3: Real-World Testing (1 minggu)
Gunakan untuk pekerjaan sehari-hari dan track metrics.

---

## ✅ Phase 1: Manual Smoke Tests

### 1.1 Server Health Check

```bash
# Start server
cd /home/aseps/MCP/mcp-unified
bash mcp-run.sh

# Check health endpoint
curl http://localhost:8000/health

# Expected response:
# {
#   "status": "healthy",
#   "version": "1.0.0",
#   "uptime": 123.45
# }
```

**✅ Pass criteria**: Server responds dengan status 200 dan "healthy"

### 1.2 Simple Tool Call Test

```bash
# Test list_dir tool
curl -X POST http://localhost:8000/tools/call \
  -H "Content-Type: application/json" \
  -d '{
    "tool": "list_dir",
    "params": {"path": "."}
  }'

# Expected: List of files di current directory
```

**✅ Pass criteria**: Response berisi list files tanpa error

### 1.3 Memory System Test

```bash
# Save memory
curl -X POST http://localhost:8000/tools/call \
  -H "Content-Type: application/json" \
  -d '{
    "tool": "memory_save",
    "params": {
      "key": "test_memory",
      "content": "This is a test memory",
      "tags": ["test"]
    }
  }'

# Search memory
curl -X POST http://localhost:8000/tools/call \
  -H "Content-Type: application/json" \
  -d '{
    "tool": "memory_search",
    "params": {"query": "test memory"}
  }'

# Expected: Found the saved memory
```

**✅ Pass criteria**: Memory saved dan bisa di-retrieve

### 1.4 Basic Code Task

```bash
# Test simple code task
curl -X POST http://localhost:8000/execute \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Fix this syntax error: def hello()\n    print(\"Hello\")"
  }'

# Expected: Corrected code with colon added
```

**✅ Pass criteria**: Code terkoreksi dengan benar

### 1.5 Token Counting

```bash
# Test token counting endpoint
curl http://localhost:8000/metrics/tokens

# Expected response:
# {
#   "total_tokens_today": 1234,
#   "budget_limit": 100000,
#   "remaining": 98766,
#   "usage_percentage": 1.23
# }
```

**✅ Pass criteria**: Token counting berfungsi

---

## 🤖 Phase 2: Automated Testing

### 2.1 Setup Testing Environment

```bash
# Install dependencies
pip install pytest pytest-asyncio httpx structlog

# Create test config
cat > test_config.json << EOF
{
  "mcp_server_url": "http://localhost:8000",
  "timeout": 30,
  "token_budget_limit": 10000,
  "max_cost_per_task": 0.10
}
EOF
```

### 2.2 Run Test Suites

```bash
# Run ALL tests
python test_framework.py --all

# Run specific suites
python test_framework.py --suite capabilities
python test_framework.py --suite performance
python test_framework.py --suite self-healing
python test_framework.py --suite tokens
```

### 2.3 Expected Results

#### Capability Tests
- ✅ 6/6 coding scenarios pass
- ✅ 2/2 workspace scenarios pass
- ✅ Success rate > 85%

#### Performance Tests
- ✅ P50 latency < 3s for simple tasks
- ✅ P95 latency < 5s for simple tasks
- ✅ P99 latency < 10s for simple tasks
- ✅ Throughput > 2 requests/second

#### Self-Healing Tests
- ✅ Auto-fix syntax errors (1 retry max)
- ✅ Handle import errors gracefully
- ✅ Timeout recovery works

#### Token Management Tests
- ✅ Large files compressed properly
- ✅ Context stays within budget
- ✅ Compression ratio > 2x for large inputs

### 2.4 Review Test Results

```bash
# Results tersimpan di:
ls test_results_*.json

# Analyze results
python -m json.tool test_results_20250126_143022.json | less

# Key metrics to check:
# - success_rate >= 0.85
# - avg_duration < expected
# - total_cost < budget
# - no critical errors
```

---

## 🌍 Phase 3: Real-World Testing

### Week 1: Daily Usage Checklist

#### Monday: Code Editing
- [ ] Fix 3 bugs di existing code
- [ ] Refactor 2 functions
- [ ] Add type hints to 1 module
- [ ] Track: success rate, time saved, tokens used

#### Tuesday: New Features
- [ ] Implement 1 small feature (< 100 LOC)
- [ ] Write unit tests for it
- [ ] Track: code quality, test coverage, self-healing events

#### Wednesday: Documentation
- [ ] Generate README for 1 project
- [ ] Create API documentation
- [ ] Track: document quality, manual edits needed

#### Thursday: Debugging
- [ ] Debug 2 complex issues
- [ ] Use memory to store findings
- [ ] Track: time to resolution, memory retrieval accuracy

#### Friday: Workspace Tasks
- [ ] Generate 1 report
- [ ] Process data files
- [ ] Create presentation outline
- [ ] Track: task completion, output quality

### Daily Metrics to Track

```bash
# Check daily metrics
curl http://localhost:8000/metrics/summary

# Log to spreadsheet:
# Date | Tasks | Success% | Tokens | Cost | Time Saved | Manual Fixes
```

### Week 1 Success Criteria
- ✅ Complete 80% of daily tasks successfully
- ✅ Self-healing rate > 60%
- ✅ Daily cost < $2
- ✅ Time saved > 2 hours/day
- ✅ < 3 critical bugs encountered

---

## 🐛 Common Issues & Fixes

### Issue 1: Server Won't Start

**Symptoms**: `docker-run.sh` fails atau timeout

**Debug**:
```bash
# Check PostgreSQL
docker ps | grep mcp-pg

# Check logs
docker logs mcp-pg
tail -f /home/aseps/MCP/logs/mcp-unified.log

# Check port
netstat -tlnp | grep 8000
```

**Fix**:
```bash
# Restart PostgreSQL
docker restart mcp-pg

# Clear port if occupied
kill $(lsof -ti:8000)
```

### Issue 2: Memory Search Returns Nothing

**Symptoms**: `memory_search` returns empty results

**Debug**:
```bash
# Check if embeddings are being created
docker exec mcp-pg psql -U aseps -d mcp -c "SELECT COUNT(*) FROM memories;"

# Check pgvector extension
docker exec mcp-pg psql -U aseps -d mcp -c "SELECT * FROM pg_extension WHERE extname='vector';"
```

**Fix**:
```bash
# Re-initialize database
docker exec -i mcp-pg psql -U aseps -d mcp < /home/aseps/MCP/init_db.sql
```

### Issue 3: High Token Usage

**Symptoms**: Daily budget exceeded in few hours

**Debug**:
```bash
# Check token usage by task type
curl http://localhost:8000/metrics/tokens/breakdown

# Check if context compression is working
curl http://localhost:8000/metrics/compression
```

**Fix**:
```bash
# Adjust token budgets in config
vim /home/aseps/MCP/mcp-unified/config.yaml

# Reduce max_tokens for simple tasks:
# simple_task_budget: 3000 -> 2000
```

### Issue 4: Self-Healing Not Working

**Symptoms**: Errors tidak auto-recover

**Debug**:
```bash
# Check self-healing logs
grep "self_healing" /home/aseps/MCP/logs/mcp-unified.log

# Check retry count
curl http://localhost:8000/metrics/self-healing
```

**Fix**:
```bash
# Verify error handlers are registered
curl http://localhost:8000/debug/handlers

# Expected: List of registered error types
```

---

## 📊 Success Metrics Dashboard

### Create Simple Dashboard

```bash
# Create monitoring script
cat > monitor.sh << 'EOF'
#!/bin/bash
while true; do
  clear
  echo "=== AI Agentic IDE Monitor ==="
  echo ""
  
  # Fetch metrics
  METRICS=$(curl -s http://localhost:8000/metrics/summary)
  
  echo "📊 Today's Stats:"
  echo "$METRICS" | jq '.today'
  
  echo ""
  echo "💰 This Week:"
  echo "$METRICS" | jq '.this_week'
  
  echo ""
  echo "🎯 Success Rate:"
  echo "$METRICS" | jq '.today.tasks_completed / (.today.tasks_completed + .today.tasks_failed) * 100' | xargs printf "%.1f%%\n"
  
  sleep 5
done
EOF

chmod +x monitor.sh
./monitor.sh
```

### Key Performance Indicators (KPIs)

| Metric | Target | Current | Status |
|--------|--------|---------|--------|
| Success Rate | > 85% | ___ % | ⏳ |
| Avg Latency (simple) | < 5s | ___ s | ⏳ |
| Daily Cost | < $2 | $ ___ | ⏳ |
| Self-Healing Rate | > 70% | ___ % | ⏳ |
| Time Saved/Day | > 2h | ___ h | ⏳ |

---

## 🎯 Before Going to Production

### Checklist

- [ ] All smoke tests pass
- [ ] Automated test suite success rate > 85%
- [ ] 1 week real-world usage completed
- [ ] Success metrics meet targets
- [ ] No critical bugs in last 3 days
- [ ] Token management working (daily cost < budget)
- [ ] Self-healing working for common errors
- [ ] Monitoring dashboard operational
- [ ] Backup & recovery tested
- [ ] Documentation complete

### Final Validation

```bash
# Run comprehensive validation
python test_framework.py --all > validation_report.txt

# Review report
cat validation_report.txt

# If all pass:
echo "✅ System ready for production!"

# If failures:
echo "⚠️  Review failures and fix before production"
```

---

## 📞 Support & Next Steps

### If Tests Fail

1. Check logs: `/home/aseps/MCP/logs/`
2. Verify database: `docker exec mcp-pg psql -U aseps -d mcp`
3. Test individual components
4. Review error patterns
5. Adjust thresholds if needed

### After Successful Testing

1. Enable production monitoring
2. Set up automated backups
3. Configure alerts for failures
4. Start tracking ROI metrics
5. Plan iterative improvements

### Continuous Improvement

- Review weekly metrics
- Identify failure patterns
- Update test scenarios
- Optimize token usage
- Enhance self-healing rules