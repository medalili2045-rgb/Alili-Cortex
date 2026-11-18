
FROM searxng/searxng:latest

COPY settings.yml /etc/searxng/settings.yml

ENV SEARXNG_PORT=10000
ENV GRANIAN_HOST=0.0.0.0
ENV SEARXNG_LIMITER=false
ENV SEARXNG_IMAGE_PROXY=false

EXPOSE 10000
