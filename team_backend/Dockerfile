# Dockerfile pour le backend Express du groupe (branche feature/frontend-admindocs)
# Backend Node.js Express : upload, documents, CRM, conformité
FROM node:18-alpine
WORKDIR /app

# Installer curl pour le healthcheck
RUN apk add --no-cache curl

COPY backend/package.json .
RUN npm install

COPY backend/src ./src

# Créer les dossiers nécessaires
RUN mkdir -p src/uploads src/data

EXPOSE 4000
CMD ["node", "src/server.js"]
