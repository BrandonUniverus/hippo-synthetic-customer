FROM python:3.13.1-slim-bookworm@sha256:031ebf3cde9f3719d2db385233bcb18df5162038e9cda20e64e08f49f4b47a2f

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY identity/requirements.txt /app/identity/requirements.txt
RUN python -m pip install --no-cache-dir -r /app/identity/requirements.txt

COPY identity/__init__.py /app/identity/__init__.py
COPY identity/customer /app/identity/customer

EXPOSE 8082

CMD ["python", "-m", "identity.customer.server"]
