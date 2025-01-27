FROM nginx:alpine

ENV NGINX_DIR=/etc/nginx

COPY docker/nginx/index.html /usr/share/nginx/html/index.html

RUN mkdir -p ${NGINX_DIR}/sites-available
RUN mkdir -p ${NGINX_DIR}/sites-enabled

COPY docker/nginx/setup/nginx.conf ${NGINX_DIR}
COPY docker/nginx/setup/sites-available/* ${NGINX_DIR}/sites-available

RUN ln -s ${NGINX_DIR}/sites-available/site.conf ${NGINX_DIR}/sites-enabled/ts_plugin.conf

EXPOSE 80