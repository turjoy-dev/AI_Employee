FROM node:20-alpine

WORKDIR /app

# Install dependencies cleanly from package-lock.json
COPY package*.json ./
RUN npm ci

# Copy frontend source
COPY . .

# Inline public backend URLs for browser API & WebSocket clients during build
ARG NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
ARG NEXT_PUBLIC_WS_URL=ws://localhost:8000

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL} \
    NEXT_PUBLIC_WS_URL=${NEXT_PUBLIC_WS_URL}

RUN npm run build

EXPOSE 3000

CMD ["npm", "start"]
