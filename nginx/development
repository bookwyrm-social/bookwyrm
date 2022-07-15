include /etc/nginx/conf.d/server_config;

upstream web {
    server web:8000;
}

server {
    listen 80;

    location ~ ^/(login|password-reset|resend-link) {
        limit_req zone=loginlimit;

        proxy_pass http://web;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header Host $host;
        proxy_redirect off;
    }

    location / {
        proxy_pass http://web;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header Host $host;
        proxy_redirect off;
    }

    location /images/ {
        alias /app/images/;
    }

    location /static/ {
        alias /app/static/;
    }
}
