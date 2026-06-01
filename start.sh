#!/bin/bash
# ============================================================
# Orgconc - Script de Inicializacao para Uso Interno
# ============================================================
# Uso: bash start.sh
# Requer: Docker Desktop instalado
# ============================================================

set -e

echo ""
echo "  ╔═══════════════════════════════════════╗"
echo "  ║   ORGCONC - Conciliacao Bancaria      ║"
echo "  ║   ORGATEC v0.9.0 - Uso Interno        ║"
echo "  ╚═══════════════════════════════════════╝"
echo ""

# Verificar Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker nao encontrado. Instale Docker Desktop:"
        echo "   https://www.docker.com/products/docker-desktop"
            exit 1
            fi

            echo "✅ Docker encontrado: $(docker --version)"

            # Criar arquivo .env se nao existir
            if [ ! -f .env ]; then
                echo ""
                    echo "📋 Criando arquivo .env..."
                        cp .env.example .env
                            echo ""
                                echo "⚠️  IMPORTANTE: Preencha as keys do Supabase no arquivo .env"
                                    echo ""
                                        echo "   As keys estao em:"
                                            echo "   https://supabase.com/dashboard/project/cmnbmckwvkfexfkegxsf/settings/api-keys/legacy"
                                                echo ""
                                                    echo "   Edite o .env e substitua:"
                                                        echo "   SUPABASE_ANON_KEY=PREENCHER_COM_ANON_KEY"
                                                            echo "   SUPABASE_SERVICE_ROLE_KEY=PREENCHER_COM_SERVICE_ROLE_KEY"
                                                            echo "   DATABASE_URL=PREENCHER_COM_DB_PASSWORD (Settings->Database->Connection string)"
                                                                echo ""
                                                                    read -p "   Pressione ENTER apos editar o .env para continuar..."
                                                                    fi

                                                                    # Verifica se as keys foram preenchidas
                                                                    if grep -q "PREENCHER_COM" .env 2>/dev/null; then
                                                                        echo ""
                                                                            echo "❌ ERRO: As keys do Supabase nao foram preenchidas no .env"
                                                                                echo "   Edite o arquivo .env e preencha SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY e DATABASE_URL"
                                                                                    echo ""
                                                                                        exit 1
                                                                                        fi

                                                                                        echo ""
                                                                                        echo "🐳 Iniciando Orgconc com Docker Compose..."
                                                                                        docker compose up -d --build

                                                                                        echo ""
                                                                                        echo "⏳ Aguardando servicos iniciarem (10s)..."
                                                                                        sleep 10

                                                                                        # Verifica health
                                                                                        if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
                                                                                            echo "✅ API Backend: ONLINE"
                                                                                            else
                                                                                                echo "⚠️  API Backend: ainda iniciando... aguarde alguns segundos e acesse o dashboard"
                                                                                                fi

                                                                                                echo ""
                                                                                                echo "╔══════════════════════════════════════════════════════╗"
                                                                                                echo "║              ORGCONC INICIADO!                       ║"
                                                                                                echo "╠══════════════════════════════════════════════════════╣"
                                                                                                echo "║  🌐 UI (React): cd orgconc-react && npm run dev      ║"
                                                                                                echo "║  🔌 API:       http://localhost:8000                 ║"
                                                                                                echo "║  📖 API Docs:  http://localhost:8000/docs            ║"
                                                                                                echo "║  ❤️  Health:    http://localhost:8000/health          ║"
                                                                                                echo "╠══════════════════════════════════════════════════════╣"
                                                                                                echo "║  Para parar:   docker compose down                   ║"
                                                                                                echo "║  Para logs:    docker compose logs -f                ║"
                                                                                                echo "╚══════════════════════════════════════════════════════╝"
                                                                                                echo ""
