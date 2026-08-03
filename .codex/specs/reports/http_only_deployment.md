# HttpOnly Auth Deployment Note

Use one backend instance and expose it under each frontend domain with Nginx.
Each frontend should call the backend through the same-origin path:

```env
REACT_APP_MICRO_BACKEND_ENDPOINT=/api
```

This avoids third-party-cookie blocking because the browser sees the API calls as
same-origin for each frontend domain. `AUTH_COOKIE_PARTITIONED_ORIGINS` is only
for origins that cannot use this same-site proxy path.

Add this `/api/` proxy block inside each frontend `server` block:

```nginx
location /api/ {
    proxy_pass http://127.0.0.1:8000/;
    proxy_http_version 1.1;

    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-Host $host;

    proxy_redirect off;
}
```

If the backend is available as the Docker service on the same Docker network,
use:

```nginx
proxy_pass http://ts-plugin:8000/;
```

For separate local compose projects, the frontend compose uses:

```nginx
proxy_pass http://host.docker.internal/;
```

Production shape on one VM:

```nginx
server {
    listen 443 ssl http2;
    server_name terminology.tib.eu;

    location /ts/ {
        root /var/www/tib;
        try_files $uri /ts/index.html;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $host;
        proxy_redirect off;
    }
}

server {
    listen 443 ssl http2;
    server_name terminology.nfdi4chem.de;

    location /ts/ {
        root /var/www/nfdi4chem;
        try_files $uri /ts/index.html;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $host;
        proxy_redirect off;
    }
}

server {
    listen 443 ssl http2;
    server_name terminology.nfdi4ing.de;

    location /ts/ {
        root /var/www/nfdi4ing;
        try_files $uri /ts/index.html;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $host;
        proxy_redirect off;
    }
}
```
