#!/bin/bash

set -e

# =========================
# CONFIG
# =========================
COMPOSE_FILE="docker-compose.yml"
PROJECT_NAME="admindocs"
LOG_FILE="start.log"

# =========================
# UTILS
# =========================
log() {
    echo -e "\033[1;34m[INFO]\033[0m $1"
}

success() {
    echo -e "\033[1;32m[SUCCESS]\033[0m $1"
}

error() {
    echo -e "\033[1;31m[ERROR]\033[0m $1"
}

warn() {
    echo -e "\033[1;33m[WARNING]\033[0m $1"
}

# =========================
# CHECKS
# =========================
log "Vérification des prérequis..."

# Docker installé ?
if ! command -v docker &> /dev/null; then
    error "Docker n'est pas installé."
    exit 1
fi

# Docker running ?
if ! docker info &> /dev/null; then
    error "Docker n'est pas démarré."
    exit 1
fi

# Docker Compose ?
if ! docker compose version &> /dev/null; then
    error "Docker Compose (v2) requis."
    exit 1
fi

success "Docker OK"


# =========================
# FILE CHECKS
# =========================
log "Vérification des fichiers..."

if [ ! -f "$COMPOSE_FILE" ]; then
    error "$COMPOSE_FILE introuvable"
    exit 1
fi

if [ ! -f ".env" ]; then
    warn ".env manquant → création depuis .env.example si dispo"
    if [ -f ".env.example" ]; then
        cp .env.example .env
        success ".env créé"
    else
        error "Aucun .env trouvé"
        exit 1
    fi
fi

check_container_health() {
    SERVICE_NAME=$1

    echo -n "→ $SERVICE_NAME ... "

    for i in {1..20}; do
        STATUS=$(docker inspect --format='{{.State.Health.Status}}' ${PROJECT_NAME}-${SERVICE_NAME}-1 2>/dev/null || echo "notfound")

        if [ "$STATUS" = "healthy" ]; then
            echo -e "\033[1;32mOK\033[0m"
            return
        fi

        sleep 2
    done

    echo -e "\033[1;31mFAIL\033[0m"
}

success "Fichiers OK"

# =========================
# BUILD
# =========================
log "Build des images..."

docker compose -f $COMPOSE_FILE -p $PROJECT_NAME build > /dev/null
success "Build terminé"

# =========================
# START
# =========================
log "Démarrage des services..."

docker compose -f $COMPOSE_FILE -p $PROJECT_NAME up -d > /dev/null
success "Services lancés"

# =========================
# WAIT FOR HEALTH
# =========================
# log "Attente des services critiques..."

# sleep 5

# check_service() {
#     SERVICE_NAME=$1
#     URL=$2

#     echo -n "→ $SERVICE_NAME ... "

#     for i in {1..15}; do
#         if curl -s $URL > /dev/null; then
#             echo -e "\033[1;32mOK\033[0m"
#             return
#         fi
#         sleep 2
#     done

#     echo -e "\033[1;31mFAIL\033[0m"
# }

# check_service "Frontend" "http://localhost:3000"
# check_service "Backend" "http://localhost:4000/api/health"
# check_service "OCR" "http://localhost:8000/health"
# check_service "Anomaly" "http://localhost:8002/health"
# check_service "Business" "http://localhost:8003/health"
# check_service "Airflow" "http://localhost:8081/api/v2/version"
# check_service "MinIO" "http://localhost:9000/minio/health/live"
# check_container_health "postgres-docs"
# check_container_health "redis"

# =========================
# INFOS FINALES
# =========================
echo ""
success "Application prête 🚀"
echo ""
echo "Accès :"
echo "→ Frontend      : http://localhost:3000"
echo "→ Backend API   : http://localhost:4000"
echo "→ Airflow       : http://localhost:8081"
echo "→ MinIO Console : http://localhost:8900"
echo ""
echo "Logs : docker compose logs -f"
echo "Stop : docker compose down"
echo ""