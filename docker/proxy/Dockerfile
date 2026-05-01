# syntax=docker/dockerfile:1.7@sha256:a57df69d0ea827fb7266491f2813635de6f17269be881f696fbfdf2d83dda33e

FROM node:24-alpine@sha256:d1b3b4da11eefd5941e7f0b9cf17783fc99d9c6fc34884a665f40a06dbdfc94f AS admin-build

WORKDIR /admin

ARG VITE_API_BASE=/api/v1
ENV VITE_API_BASE=${VITE_API_BASE}

COPY admin/package.json admin/package-lock.json ./
RUN npm ci

COPY admin ./
RUN npm run build

FROM nginx:1.29-alpine@sha256:5616878291a2eed594aee8db4dade5878cf7edcb475e59193904b198d9b830de AS runtime

COPY --from=admin-build /admin/dist /usr/share/nginx/html
COPY docker/proxy/templates/default.conf.template /etc/nginx/templates/default.conf.template

EXPOSE 8080
