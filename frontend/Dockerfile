# =============================================================================
# Multi-stage Dockerfile for DMARC Frontend
# =============================================================================

# -----------------------------------------------------------------------------
# Stage 1: Builder - Install dependencies and run tests
# -----------------------------------------------------------------------------
FROM node:20-alpine AS builder

WORKDIR /build

# Install dependencies
COPY package*.json ./
RUN npm ci --only=production 2>/dev/null || npm install --only=production 2>/dev/null || true

# Copy source files
COPY . .

# -----------------------------------------------------------------------------
# Stage 2: Production - Minimal nginx image
# -----------------------------------------------------------------------------
FROM nginx:1.25-alpine AS production

# Security: Remove default nginx config and server tokens
RUN rm -rf /etc/nginx/conf.d/default.conf && \
    sed -i 's/server_tokens on/server_tokens off/' /etc/nginx/nginx.conf 2>/dev/null || true

# Create non-root user for nginx
RUN addgroup -g 1000 -S dmarc && \
    adduser -u 1000 -S dmarc -G dmarc

# Create nginx config for SPA with security headers
COPY <<EOF /etc/nginx/conf.d/default.conf
server {
    listen 80;
    listen [::]:80;
    server_name _;

    root /usr/share/nginx/html;
    index index.html;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_proxied any;
    gzip_types text/plain text/css text/xml text/javascript application/javascript application/json application/xml+rss;

    # Cache static assets
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # Proxy API requests to backend
    location /api {
        proxy_pass http://backend:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_cache_bypass \$http_upgrade;
        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;
    }

    # Health endpoint proxy
    location /health {
        proxy_pass http://backend:8000/health;
    }

    # Handle SPA routing
    location / {
        try_files \$uri \$uri/ /index.html;
    }

    # Deny access to hidden files
    location ~ /\. {
        deny all;
        access_log off;
        log_not_found off;
    }
}
EOF

# Copy static files from builder
COPY --from=builder /build/index.html /usr/share/nginx/html/
COPY --from=builder /build/css /usr/share/nginx/html/css/
COPY --from=builder /build/js /usr/share/nginx/html/js/

# Set proper permissions
RUN chown -R nginx:nginx /usr/share/nginx/html && \
    chmod -R 755 /usr/share/nginx/html && \
    chown -R nginx:nginx /var/cache/nginx && \
    chown -R nginx:nginx /var/log/nginx && \
    touch /var/run/nginx.pid && \
    chown -R nginx:nginx /var/run/nginx.pid

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:80/ || exit 1

EXPOSE 80

# Run as nginx user
USER nginx

CMD ["nginx", "-g", "daemon off;"]

# -----------------------------------------------------------------------------
# Stage 3: Development - With live reload support
# -----------------------------------------------------------------------------
FROM node:20-alpine AS development

WORKDIR /app

# Install live-server for development
RUN npm install -g live-server

# Copy source files
COPY . .

EXPOSE 3000

CMD ["live-server", "--host=0.0.0.0", "--port=3000", "--no-browser"]
