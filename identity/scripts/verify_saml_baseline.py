"""Focused provider-side verification for configurable Northlake SAML profiles."""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import ssl
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from lxml import etree


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from identity.scripts import verify_identity as identity_verifier
from identity.scripts.verify_oidc_baseline import _install_host_override


XML_ENCRYPTION_NAMESPACE = "http://www.w3.org/2001/04/xmlenc#"
XML_ENCRYPTION_11_NAMESPACE = "http://www.w3.org/2009/xmlenc11#"
XML_SIGNATURE_NAMESPACE = "http://www.w3.org/2000/09/xmldsig#"
AES_256_GCM = "http://www.w3.org/2009/xmlenc11#aes256-gcm"
RSA_OAEP_11 = "http://www.w3.org/2009/xmlenc11#rsa-oaep"
SHA_256 = "http://www.w3.org/2001/04/xmlenc#sha256"
MGF1_SHA_256 = "http://www.w3.org/2009/xmlenc11#mgf1sha256"
NAMESPACES = {
    **identity_verifier.SAML_NAMESPACES,
    "xenc": XML_ENCRYPTION_NAMESPACE,
    "xenc11": XML_ENCRYPTION_11_NAMESPACE,
    "ds": XML_SIGNATURE_NAMESPACE,
}


def _verify_unsigned_saml2int_request_rejected(
    profile: dict[str, Any],
    context: ssl.SSLContext,
) -> None:
    client = profile["clients"]["saml2Int"]
    _, _, authentication_url = identity_verifier._saml_authentication_url(
        profile,
        client["defaultAssertionConsumerServiceUrl"],
        "saml2Int",
    )
    try:
        with urlopen(
            Request(
                authentication_url,
                headers={"User-Agent": identity_verifier.VERIFIER_USER_AGENT},
            ),
            context=context,
            timeout=20,
        ) as response:
            status = response.status
            body = response.read()
    except HTTPError as error:
        status = error.code
        body = error.read()
    forms = identity_verifier._forms(body)
    if any("login-actions/authenticate" in form.action for form in forms):
        raise identity_verifier.VerificationError(
            "Saml2Int accepted an unsigned AuthnRequest and displayed a login form."
        )
    if any("SAMLResponse" in form.inputs for form in forms):
        raise identity_verifier.VerificationError(
            "Saml2Int accepted an unsigned AuthnRequest and returned a response."
        )
    if status not in {200, 400, 403}:
        raise identity_verifier.VerificationError(
            f"Unsigned Saml2Int AuthnRequest returned unexpected HTTP {status}."
        )
    print("[OK] Saml2Int rejects an unsigned SP-initiated AuthnRequest.")


def _verify_saml2int_admin_certificate(
    profile: dict[str, Any],
    context: ssl.SSLContext,
) -> None:
    client_profile = profile["clients"]["saml2Int"]
    admin_token = identity_verifier._json_request(
        f"{profile['baseUrl']}/realms/master/protocol/openid-connect/token",
        context,
        data={
            "grant_type": "password",
            "client_id": "admin-cli",
            "username": profile["admin"]["username"],
            "password": profile["admin"]["password"],
        },
    )["access_token"]
    clients = identity_verifier._json_request(
        f"{profile['baseUrl']}/admin/realms/{profile['realm']}/clients",
        context,
        bearer=admin_token,
    )
    client = next(
        (item for item in clients if item.get("clientId") == client_profile["clientId"]),
        None,
    )
    if client is None:
        raise identity_verifier.VerificationError("Saml2Int client was not installed.")
    attributes = client.get("attributes", {})
    encoded_certificate = attributes.get("saml.encryption.certificate", "")
    try:
        certificate_der = base64.b64decode(encoded_certificate, validate=True)
    except (binascii.Error, ValueError) as error:
        raise identity_verifier.VerificationError(
            "Saml2Int encryption certificate was not valid DER base64."
        ) from error
    if (
        hashlib.sha256(certificate_der).hexdigest().upper()
        != client_profile.get("serviceProviderCertificateSha256")
    ):
        raise identity_verifier.VerificationError(
            "Saml2Int did not install the selected public certificate."
        )
    expected_attributes = {
        "saml.encryption.algorithm": AES_256_GCM,
        "saml.encryption.keyAlgorithm": RSA_OAEP_11,
        "saml.encryption.digestMethod": SHA_256,
        "saml.encryption.maskGenerationFunction": MGF1_SHA_256,
    }
    if any(attributes.get(key) != value for key, value in expected_attributes.items()):
        raise identity_verifier.VerificationError(
            "Saml2Int encryption algorithms drifted from the EEM-supported profile."
        )
    if "PRIVATE KEY" in json.dumps(client).upper():
        raise identity_verifier.VerificationError(
            "Saml2Int client data unexpectedly contained private-key material."
        )
    print(
        "[OK] Saml2Int installed only the selected public RSA certificate with explicit "
        "AES-256-GCM, RSA-OAEP-11, SHA-256, and MGF1-SHA256 settings."
    )


def _require_one(
    parent: Any,
    path: str,
    description: str,
) -> Any:
    nodes = parent.findall(path, namespaces=NAMESPACES)
    if len(nodes) != 1:
        raise identity_verifier.VerificationError(
            f"Encrypted Saml2Int response did not contain one {description}."
        )
    return nodes[0]


def _verify_saml2int_encrypted_response(
    profile: dict[str, Any],
    context: ssl.SSLContext,
) -> None:
    metadata = identity_verifier._fetch_saml_metadata(profile, context)
    client = profile["clients"]["saml2Int"]
    assertion_consumer_service_url = client["defaultAssertionConsumerServiceUrl"]
    opener, login_document = identity_verifier._open_login(
        context,
        client["idpInitiatedSsoUrl"],
        assertion_consumer_service_url,
    )
    status, location, body = identity_verifier._submit_login(
        opener,
        login_document,
        profile["testUsers"]["active"]["username"],
        profile["testUsers"]["password"],
        assertion_consumer_service_url,
    )
    if status != 200 or location:
        raise identity_verifier.VerificationError(
            "Saml2Int IdP-initiated login did not return an HTTP-POST form."
        )
    response_document = identity_verifier._saml_callback_form(
        body,
        assertion_consumer_service_url,
        client["idpInitiatedRelayState"],
    )
    raw_response = identity_verifier._parse_saml_xml(
        response_document,
        "Saml2Int response",
    )
    response_tag = etree.QName(identity_verifier.SAML_PROTOCOL_NAMESPACE, "Response")
    response = identity_verifier._verify_saml_xml_signature(
        response_document,
        metadata,
        location="./",
        expected_tag=response_tag,
    )
    if response.get("Destination") != assertion_consumer_service_url:
        raise identity_verifier.VerificationError(
            "Saml2Int response Destination did not match the exact ACS URL."
        )
    if response.get("InResponseTo"):
        raise identity_verifier.VerificationError(
            "Saml2Int IdP-initiated response unexpectedly included InResponseTo."
        )
    plain_assertions = raw_response.findall("./saml:Assertion", namespaces=NAMESPACES)
    encrypted_assertions = raw_response.findall(
        "./saml:EncryptedAssertion",
        namespaces=NAMESPACES,
    )
    if plain_assertions or len(encrypted_assertions) != 1:
        raise identity_verifier.VerificationError(
            "Saml2Int response did not contain exactly one encrypted assertion."
        )
    encrypted_assertion = encrypted_assertions[0]
    data_method = _require_one(
        encrypted_assertion,
        "./xenc:EncryptedData/xenc:EncryptionMethod",
        "data EncryptionMethod",
    )
    key_method = _require_one(
        encrypted_assertion,
        ".//xenc:EncryptedKey/xenc:EncryptionMethod",
        "key EncryptionMethod",
    )
    digest_method = _require_one(
        key_method,
        "./ds:DigestMethod",
        "RSA-OAEP DigestMethod",
    )
    mask_generation = _require_one(
        key_method,
        "./xenc11:MGF",
        "RSA-OAEP mask-generation function",
    )
    if (
        data_method.get("Algorithm") != AES_256_GCM
        or key_method.get("Algorithm") != RSA_OAEP_11
        or digest_method.get("Algorithm") != SHA_256
        or mask_generation.get("Algorithm") != MGF1_SHA_256
    ):
        raise identity_verifier.VerificationError(
            "Saml2Int response encryption algorithms did not match EEM's accepted profile."
        )
    if response.find("./saml:Issuer", namespaces=NAMESPACES).text != metadata.entity_id:
        raise identity_verifier.VerificationError(
            "Saml2Int response issuer did not match IdP metadata."
        )
    print(
        "[OK] Saml2Int IdP-initiated POST response is directly signed and contains one "
        "AES-256-GCM assertion encrypted with RSA-OAEP-11/SHA-256/MGF1-SHA256."
    )


def verify(connection_path: Path, ca_path: Path) -> None:
    profile = json.loads(connection_path.read_text(encoding="utf-8"))
    context = ssl.create_default_context(cafile=str(ca_path))
    if "saml" not in profile["clients"] and "saml2Int" not in profile["clients"]:
        raise identity_verifier.VerificationError("Both bounded SAML profiles are disabled.")
    identity_verifier._verify_admin(profile, context)
    if "saml" in profile["clients"]:
        identity_verifier._verify_saml(profile, context)
    else:
        print("[OK] Standard SAML is disabled by the bounded profile.")
    if "saml2Int" in profile["clients"]:
        _verify_saml2int_admin_certificate(profile, context)
        _verify_unsigned_saml2int_request_rejected(profile, context)
        _verify_saml2int_encrypted_response(profile, context)
        print(
            "[GAP] Northlake cannot prove EEM's signed AuthnRequest or private-key decryption "
            "without running the installed EnergyHippo path; no private key was requested or stored."
        )
    else:
        print("[OK] Saml2Int is disabled; no public SP certificate is required.")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify the configured Northlake SAML provider profiles."
    )
    parser.add_argument("--connection", required=True, type=Path)
    parser.add_argument("--ca-file", required=True, type=Path)
    parser.add_argument("--resolve-host")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        _install_host_override(args.resolve_host)
        verify(args.connection.resolve(), args.ca_file.resolve())
    except (
        OSError,
        HTTPError,
        URLError,
        identity_verifier.VerificationError,
        KeyError,
        AttributeError,
        json.JSONDecodeError,
    ) as error:
        print(f"[ERROR] {error}", file=sys.stderr)
        return 1
    print("[OK] Northlake focused SAML provider verification completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
