
FROM searxng/searxng:latest

USER root

COPY settings.yml /etc/searxng/settings.yml
COPY gateway.py /app/gateway.py

RUN mkdir -p /app /var/cache/searxng \
    && chown -R searxng:searxng /etc/searxng /var/cache/searxng /app

ENV GRANIAN_HOST=127.0.0.1 \
    GRANIAN_PORT=8080 \
    GRANIAN_INTERFACE=wsgi \
    SEARXNG_LIMITER=false \
    SEARXNG_IMAGE_PROXY=false

USER searxng

EXPOSE 10000

ENTRYPOINT ["/usr/local/searxng/.venv/bin/python", "/app/gateway.py"]
