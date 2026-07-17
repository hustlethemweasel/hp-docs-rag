FROM node:22-alpine AS deps
WORKDIR /frontend
COPY package.json package-lock.json ./
RUN npm ci

FROM node:22-alpine AS builder
WORKDIR /frontend
COPY --from=deps /frontend/node_modules ./node_modules
COPY . .
# Inlined into the client bundle at build time (see .env.example).
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
RUN npm run build

FROM node:22-alpine AS runner
WORKDIR /frontend
ENV NODE_ENV=production
COPY --from=builder /frontend/public ./public
COPY --from=builder /frontend/.next/standalone ./
COPY --from=builder /frontend/.next/static ./.next/static

EXPOSE 3000
ENV PORT=3000
CMD ["node", "server.js"]
