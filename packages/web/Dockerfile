# Dockerfile pour le frontend Next.js
FROM node:18-alpine AS base

# Installation des dépendances uniquement quand c'est nécessaire
FROM base AS deps
# Vérifier https://github.com/nodejs/docker-node/tree/b4117f9333da4138b03a546ec926ef50a31506c3#nodealpine
# pour comprendre pourquoi libc6-compat pourrait être nécessaire.
RUN apk add --no-cache libc6-compat
WORKDIR /app

# Installer les dépendances basées sur le gestionnaire de paquets préféré
COPY package.json package-lock.json* ./
RUN \
  if [ -f package-lock.json ]; then npm ci --only=production; \
  else echo "Lockfile introuvable." && exit 1; \
  fi

# Rebuild le code source uniquement quand c'est nécessaire
FROM base AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .

# Next.js collecte des données de télémétrie complètement anonymes sur l'utilisation générale.
# En savoir plus ici: https://nextjs.org/telemetry
# Décommentez la ligne suivante pour désactiver la télémétrie lors du build.
# ENV NEXT_TELEMETRY_DISABLED 1

RUN npm run build

# Image de production, copie tous les fichiers et lance Next.js
FROM base AS runner
WORKDIR /app

ENV NODE_ENV production
# Décommentez la ligne suivante pour désactiver la télémétrie lors de l'exécution.
# ENV NEXT_TELEMETRY_DISABLED 1

RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

COPY --from=builder /app/public ./public

# Définir automatiquement les permissions sur le répertoire de sortie
RUN mkdir .next
RUN chown nextjs:nodejs .next

# Tirer parti de la sortie de fichier trace pour réduire la taille de l'image
# https://nextjs.org/docs/advanced-features/output-file-tracing
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000

ENV PORT 3000
ENV HOSTNAME "0.0.0.0"

# Le serveur.js est créé par next build depuis le mode de sortie
CMD ["node", "server.js"]