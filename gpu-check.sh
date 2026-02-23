#!/bin/bash
# gpu-check-wsl.sh — диагностика GPU специально для WSL2

echo "🔍 Диагностика GPU для WSL2 + Docker"
echo "======================================"

echo -e "\n1. 🐧 Проверка внутри WSL:"
if command -v nvidia-smi &> /dev/null; then
    echo "✅ nvidia-smi доступен в WSL"
    nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1
else
    echo "❌ nvidia-smi не найден в WSL"
    echo "💡 Убедитесь, что в Docker Desktop включена интеграция с Ubuntu-22.04"
fi

echo -e "\n2. 🐳 Docker GPU тест (внутри контейнера):"
# Тест с правильным runtime для WSL2
if docker run --rm --runtime=nvidia --gpus all ubuntu:22.04 \
    bash -c "apt-get update -qq && apt-get install -y -qq nvidia-utils-535 > /dev/null 2>&1; nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null" 2>/dev/null; then
    echo "✅ Docker видит GPU"
else
    echo "❌ Docker не видит GPU"
    echo "💡 Попробуйте:"
    echo "   1. Перезапустить Docker Desktop"
    echo "   2. Выполнить в PowerShell: wsl --shutdown"
    echo "   3. Проверить: Settings → Resources → WSL Integration → Ubuntu-22.04 ✅"
fi

echo -e "\n3. 🔍 Проверка docker-compose:"
if grep -q "runtime: nvidia" docker-compose.gpu.yml 2>/dev/null; then
    echo "✅ runtime: nvidia указан в docker-compose.gpu.yml"
else
    echo "⚠️  runtime: nvidia НЕ указан — добавьте!"
fi

echo -e "\n4. 📦 Проверка переменных окружения:"
grep -E "FORCE_CPU|CUDA|NVIDIA" .env 2>/dev/null || echo "⚠️  Нет GPU-переменных в .env"

echo -e "\n✅ Диагностика завершена"