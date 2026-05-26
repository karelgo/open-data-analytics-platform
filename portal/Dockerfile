# syntax=docker/dockerfile:1.7
#
# ODAP Portal — multi-stage:
#   1. node:lts-alpine bouwt de Astro static site.
#   2. nginxinc/nginx-unprivileged serveert de output (non-root op :8080).
#
# In K8s draait een sidecar oauth2-proxy ervoor (:4180 -> :8080) voor SSO.
#
# Build VANUIT REPO-ROOT zodat opa-policies-src/data mee-gekopieerd kan
# worden voor de prebuild-stap (single source of truth voor rol-mappings):
#
#   docker build -f portal/Dockerfile -t odap/portal:dev .

FROM node:20-alpine AS build
WORKDIR /app

# 1. Astro/portal-bron + node deps.
# --legacy-peer-deps omdat de embed-ui-shell branch @types/react@19 introduceerde
# terwijl @astrojs/react@3.x nog 17/18 peer-pinned heeft. Niet runtime-relevant
# (Astro-React-island wordt niet gebruikt op de pagina's die we bouwen) maar
# blokkeert wel een verse npm ci.
COPY portal/package.json portal/package-lock.json* ./
RUN if [ -f package-lock.json ]; then npm ci --legacy-peer-deps; else npm install --legacy-peer-deps; fi

# 2. Brondata uit OPA op de plek die scripts/sync-data.mjs verwacht
#    (../opa-policies-src/data, gerekend vanaf /app).
COPY opa-policies-src/data /opa-policies-src/data

# 3. Canonical docs/ — portal-pages kunnen markdown importeren via
#    Vite-alias `@docs/foo.md` (zie portal/astro.config.mjs). Alias
#    resolved naar `/docs/` in deze container; lokaal naar `<repo>/docs/`.
COPY docs /docs

# 4. Portal-bestanden.
COPY portal/ ./

RUN npm run build

# ---

FROM nginxinc/nginx-unprivileged:1.27-alpine AS runtime
USER 0
RUN rm -rf /etc/nginx/conf.d/*.conf /usr/share/nginx/html/*
COPY portal/nginx.conf /etc/nginx/nginx.conf
COPY --from=build /app/dist/ /usr/share/nginx/html/
RUN chown -R 101:101 /usr/share/nginx/html
USER 101
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s \
  CMD wget -qO- http://127.0.0.1:8080/api/health || exit 1
CMD ["nginx", "-g", "daemon off;"]
