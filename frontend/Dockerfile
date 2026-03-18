# =============================================================================
# Dockerfile Frontend – AdminDocs (React + Vite + Tailwind)
# Multi-stage :
#   1. Build : Node.js compile le frontend (npm run build)
#   2. Serve : Nginx sert les fichiers statiques + proxy /api vers team-backend
# =============================================================================

# ---- Stage 1 : Build ----
FROM node:18-alpine AS builder

WORKDIR /app

# Installer les dépendances
COPY package.json package-lock.json ./
RUN npm ci --silent

# Copier les sources et builder
COPY . .
# VITE_API_URL vide → axios utilisera /api (relatif, géré par nginx)
ENV VITE_API_URL=/api
RUN npm run build

# ---- Stage 2 : Serve avec nginx ----
FROM nginx:alpine

# Copier les fichiers buildés
COPY --from=builder /app/dist /usr/share/nginx/html

# Copier la config nginx (proxy /api → team-backend:4000)
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 3000

CMD ["nginx", "-g", "daemon off;"]
