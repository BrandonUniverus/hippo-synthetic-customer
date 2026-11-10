FROM python:3.13.1-slim-bookworm@sha256:031ebf3cde9f3719d2db385233bcb18df5162038e9cda20e64e08f49f4b47a2f AS producer
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONTZPATH="" NORTHLAKE_STATE=/state
WORKDIR /app
COPY generators/requirements.txt /app/generators/requirements.txt
COPY services/sources/requirements.txt /app/services/sources/requirements.txt
RUN python -m pip install --no-cache-dir -r /app/services/sources/requirements.txt
COPY services /app/services
COPY generators /app/generators
COPY data /app/data
COPY identity/branding /app/identity/branding
COPY documents/rate-tariffs /app/documents/rate-tariffs
COPY implementation/stage-2-hierarchy/04-points.yaml /app/implementation/stage-2-hierarchy/04-points.yaml
COPY implementation/stage-3-gateways-and-data/02-gateways.yaml /app/implementation/stage-3-gateways-and-data/02-gateways.yaml
COPY documents/intake-package/sample-data/acquisuite /app/documents/intake-package/sample-data/acquisuite
VOLUME /state
ENTRYPOINT ["python", "-m", "services.sources"]
CMD ["run"]

FROM caddy:2.11.4-alpine@sha256:5f5c8640aae01df9654968d946d8f1a56c497f1dd5c5cda4cf95ab7c14d58648 AS web
COPY services/sources/Caddyfile /etc/caddy/Caddyfile
EXPOSE 8080
