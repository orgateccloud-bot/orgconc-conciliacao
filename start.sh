#!/bin/bash
# ============================================================
# Orgconc — Script de Inicializacao para Uso Interno
# ============================================================
# Uso: bash start.sh
# Requer: Docker Desktop instalado
# ============================================================

set -e

# Le versao unica do arquivo VERSION
VERSION=$(cat VERSION 2>/dev/null || echo "0.0.0")

echo ""
echo "  ██████╗ ██████╗  ██████╗  ██████╗ ███╗   ██╗ ██████╗"
echo " ██╔═══██╗██╔══██╗██╔════╝ ██╔════╝ ████╗  ██║██╔════╝"
echo " ██║   ██║██████╔╝██║  ███╗██║      ██╔██╗ ██║██║     "
echo " ██║   ██║██╔══██╗██║   ██║██║      ██║╚██╗██║██║     "
echo " ╚██████╔╝██║  ██║╚██████╔╝╚██████╗ ██║ ╚████║╚██████╗"
echo "  ╚═════╝ ╚═╝  ╚═╝ ╚═════╝  ╚═════╝ ╚═╝  ╚═══╝ ╚═════╝"
echo ""
echo " Conciliacao Bancaria Inteligente — ORGATEC v${VERSION}"
echo ""

# Verificar Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker nao encontrado. Instale Docker Desktop:"
    echo "   https://www.docker.com/products/docker-desktop"
    exit 1
fi

# Criar arquivo .env se nao existir
if [ ! -f .env ]; then
    echo "📋 Criando arquivo .env com credenciais do Supabase..."
    cat > .env << 'EOF'
# Supabase — Banco de dados (ja configurado)
SUPABASE_URL=https://cmnbmckwvkfexfkegxsf.supabase.co
SUPABASE_ANON_KEY=PREENCHER_COM_ANON_KEY
SUPABASE_SERVICE_ROLE_KEY=PREENCHER_COM_SERVICE_ROLE_KEY

# Autenticacao
JWT_SECRET=orgconc-jwt-secret-interno-2026-mudar-em-producao
ORGCONC_AUTH_TOKEN=orgconc-token-interno-2026

# Configuracoes
ORGCONC_CORS_ORIGINS=http://localhost,http://localhost:80,http://127.0.0.1
EOF
    echo ""
    echo "⚠️  IMPORTANTE: Edite o arquivo .env e preencha:"
    echo "   - SUPABASE_ANON_KEY"
    echo "   - SUPABASE_SERVICE_ROLE_KEY"
    echo ""
    echo "   Encontre as chaves em:"
    echo "   https://supabase.com/dashboard/project/cmnbmckwvkfexfkegxsf/settings/api-keys/legacy"
    echo ""
    read -p "Pressione ENTER apos editar o .env para continuar..."
fi

echo "🐳 Iniciando Orgconc com Docker Compose..."
docker compose up -d --build

echo ""
echo "✅ Orgconc iniciado com sucesso!"
echo ""
echo "  📊 Dashboard:  http://localhost/frontend/dashboard_trust.html"
echo "  🔐 Login:      http://localhost/frontend/login.html"
echo "  🔌 API:        http://localhost:8000"
echo "  ❤️  Health:     http://localhost:8000/health"
echo ""
echo "  Para parar: docker compose down"
echo "  Para logs:  docker compose logs -f"
echo ""
