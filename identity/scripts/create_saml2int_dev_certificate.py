#!/usr/bin/env python3
"""Mint the development stand-in public certificate for the Northlake Saml2Int profile.

EnergyHippo owns the real service-provider credential. This tool exists only so the
local lab can exercise the Saml2Int path without one: it writes a self-signed public
certificate and immediately discards the matching private key, preserving the lab
invariant that no private-key material is ever requested or stored.
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from identity.configuration.saml import describe_public_certificate  # noqa: E402

DEFAULT_DAYS = 365
SUBJECT = x509.Name(
    [
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Northlake Synthetic Identity Lab"),
        x509.NameAttribute(NameOID.COMMON_NAME, "Northlake Development Saml2Int SP"),
    ]
)


def create_development_certificate(days: int) -> bytes:
    """Return the DER public certificate; the private key is discarded on return."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = datetime.now(UTC)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(SUBJECT)
        .issuer_name(SUBJECT)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=days))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                key_encipherment=True,
                content_commitment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(
            x509.SubjectKeyIdentifier.from_public_key(private_key.public_key()),
            critical=False,
        )
        .sign(private_key, hashes.SHA256())
    )
    return certificate.public_bytes(serialization.Encoding.DER)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--certificate-file",
        type=Path,
        default=REPOSITORY_ROOT / "identity" / ".runtime" / "certs" / "saml2int-sp-public.cer",
    )
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace a stored certificate that is still currently valid.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if not 1 <= args.days <= 7300:
        print("[ERROR] Choose a lifetime between 1 and 7300 days.", file=sys.stderr)
        return 1

    certificate_path = args.certificate_file.resolve()
    if certificate_path.is_file():
        existing = describe_public_certificate(certificate_path.read_bytes())
        if existing["valid"] and not args.force:
            print(
                "[ERROR] A currently valid certificate is already stored at "
                f"{certificate_path}.\n"
                f"        Subject: {existing['subject']}\n"
                f"        Expires: {existing['notAfterUtc']}\n"
                "        This may be EnergyHippo's real public certificate. Pass --force "
                "only if you meant to replace it with a development stand-in.",
                file=sys.stderr,
            )
            return 1
        print(f"[..] Replacing the stored certificate: {existing.get('reason', 'forced replacement.')}")

    der = create_development_certificate(args.days)
    certificate_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = certificate_path.with_suffix(f"{certificate_path.suffix}.tmp")
    temporary_path.write_bytes(der)
    temporary_path.replace(certificate_path)

    summary = describe_public_certificate(der)
    print(f"[OK] Wrote a {args.days}-day development Saml2Int certificate to {certificate_path}.")
    print(f"     Subject:    {summary['subject']}")
    print(f"     Thumbprint: {summary['sha256Thumbprint']}")
    print(f"     Valid until:{summary['notAfterUtc']}")
    print(
        "     The matching private key was discarded and never written. Northlake still "
        "cannot prove decryption; that remains the installed EnergyHippo path."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
