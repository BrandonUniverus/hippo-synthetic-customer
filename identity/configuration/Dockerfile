FROM python:3.13.1-slim-bookworm@sha256:031ebf3cde9f3719d2db385233bcb18df5162038e9cda20e64e08f49f4b47a2f

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_ROOT_USER_ACTION=ignore

WORKDIR /app

COPY identity/requirements.txt /app/identity/requirements.txt
RUN python -m pip install --no-cache-dir -r /app/identity/requirements.txt

COPY identity/__init__.py /app/identity/__init__.py
COPY identity/configuration /app/identity/configuration
COPY identity/realm /app/identity/realm
COPY identity/scripts/verify_identity.py /app/identity/scripts/verify_identity.py
COPY identity/scripts/verify_oidc_baseline.py /app/identity/scripts/verify_oidc_baseline.py
COPY identity/scripts/verify_saml_baseline.py /app/identity/scripts/verify_saml_baseline.py
COPY security/northlake-eem-security-v1.yaml /app/security/northlake-eem-security-v1.yaml

EXPOSE 8081

CMD ["python", "-m", "identity.configuration.server"]
