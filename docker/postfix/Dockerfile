FROM debian:bookworm-slim

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends postfix ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY main.cf /etc/postfix/main.cf
COPY entrypoint.sh /usr/local/bin/postfix-entrypoint

CMD ["sh", "/usr/local/bin/postfix-entrypoint"]
