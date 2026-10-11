FROM node:20-bookworm-slim AS build

WORKDIR /app

ENV CI=1 \
    EXPO_NO_TELEMETRY=1 \
    npm_config_fund=false

COPY frontend/mobile/package.json frontend/mobile/package-lock.json ./
RUN npm ci

COPY frontend/mobile ./

ARG EXPO_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
ARG EXPO_PUBLIC_WS_BASE_URL=ws://127.0.0.1:8000
ARG EXPO_PUBLIC_DEMO_MODE=false
ENV EXPO_PUBLIC_API_BASE_URL=$EXPO_PUBLIC_API_BASE_URL \
    EXPO_PUBLIC_WS_BASE_URL=$EXPO_PUBLIC_WS_BASE_URL \
    EXPO_PUBLIC_DEMO_MODE=$EXPO_PUBLIC_DEMO_MODE

RUN npx expo export --platform web --output-dir dist --max-workers 2

FROM nginx:1.27-alpine

COPY docker/web/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
