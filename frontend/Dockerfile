FROM node:22-alpine AS build

WORKDIR /app
COPY package*.json ./
RUN npm ci

COPY . ./
ARG VITE_BASE_PATH=/
ENV VITE_BASE_PATH=${VITE_BASE_PATH}
RUN npm run build

FROM caddy:2-alpine
COPY Caddyfile /etc/caddy/Caddyfile
COPY --from=build /app/dist /srv
