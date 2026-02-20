#!/bin/bash
set -e
RED='\033[0;31m'; GREEN='\033[0;32m'; NC='\033[0m'

echo "🔍 Проверка enhanced-llm-retrieval"
echo "=================================="

PASS=0; FAIL=0
check() { if [ $? -eq 0 ]; then echo -e "${GREEN}✅ $1${NC}"; ((PASS++)); else echo -e "${RED}❌ $1${NC}"; ((FAIL++)); fi; }

echo -n "🐳 Docker... "; docker info >/dev/null 2>&1; check "Docker"
echo -n "📦 app... "; docker-compose ps | grep -q "llm-retrieval-app.*Up"; check "app"
echo -n "📦 ollama... "; docker-compose ps | grep -q "ollama-server.*Up"; check "ollama"
echo -n "📦 redis... "; docker-compose ps | grep -q "llm-redis.*Up"; check "redis"
echo -n "🤖 Ollama API... "; curl -s --max-time 5 http://localhost:11434/api/tags >/dev/null 2>&1; check "Ollama"
echo -n "🗄️  Redis... "; docker-compose exec -T redis redis-cli ping 2>/dev/null | grep -q "PONG"; check "Redis"

echo ""
echo "=================================="
echo -e "Итог: ${GREEN}$PASS OK${NC}, ${RED}$FAIL ошибок${NC}"
[ $FAIL -eq 0 ] && echo -e "${GREEN}🎉 Готово!${NC}" && exit 0 || exit 1