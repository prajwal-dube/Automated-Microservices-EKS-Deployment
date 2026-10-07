FROM node:22-alpine AS build
WORKDIR /app
COPY package*.json ./
# Direct versions are pinned. Commit a generated package-lock.json for full repeatability.
RUN if [ -f package-lock.json ]; then npm ci; else npm install --no-audit --no-fund; fi
COPY index.html vite.config.js ./
COPY src ./src
RUN npm run build

FROM nginx:1.28-alpine AS runtime
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/nginx.conf.template
COPY entrypoint.sh /entrypoint.sh
RUN chmod 755 /entrypoint.sh
USER 101:101
EXPOSE 8080
ENTRYPOINT ["/entrypoint.sh"]
