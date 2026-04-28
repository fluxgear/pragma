# syntax=docker/dockerfile:1.7

FROM node:24-alpine AS admin-build

WORKDIR /admin

ARG VITE_API_BASE=/api/v1
ENV VITE_API_BASE=${VITE_API_BASE}

COPY admin/package.json admin/package-lock.json ./
RUN npm ci

COPY admin ./
RUN npm run build

FROM nginx:1.29-alpine AS runtime

COPY --from=admin-build /admin/dist /usr/share/nginx/html
COPY docker/proxy/templates/default.conf.template /etc/nginx/templates/default.conf.template

EXPOSE 8080
