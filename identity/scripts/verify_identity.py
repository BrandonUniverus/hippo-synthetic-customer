#!/usr/bin/env python3
"""End-to-end protocol and administration checks for Northlake Keycloak."""

from __future__ import annotations

import argparse
import base64
import hashlib
import html
import json
import secrets
import ssl
import sys
import time
import zlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, unquote_plus, urlencode, urljoin, urlparse
from urllib.request import (
    HTTPCookieProcessor,
    HTTPRedirectHandler,
    HTTPSHandler,
    Request,
    build_opener,
    urlopen,
)

from cryptography import x509
from cryptography.exceptions import InvalidSignature as InvalidJwtSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from lxml import etree
from signxml import DigestAlgorithm, SignatureConfiguration, SignatureMethod, XMLVerifier
from signxml.exceptions import InvalidSignature as InvalidXmlSignature


class VerificationError(AssertionError):
    """Raised when the live provider violates the synthetic identity contract."""


VERIFIER_USER_AGENT = "HippoSyntheticIdentityVerifier/1.0"
SAML_ASSERTION_NAMESPACE = "urn:oasis:names:tc:SAML:2.0:assertion"
SAML_METADATA_NAMESPACE = "urn:oasis:names:tc:SAML:2.0:metadata"
SAML_PROTOCOL_NAMESPACE = "urn:oasis:names:tc:SAML:2.0:protocol"
XML_SIGNATURE_NAMESPACE = "http://www.w3.org/2000/09/xmldsig#"
SAML_POST_BINDING = "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"
SAML_REDIRECT_BINDING = "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"
SAML_PERSISTENT_NAME_ID = "urn:oasis:names:tc:SAML:2.0:nameid-format:persistent"
SAML_BEARER_CONFIRMATION = "urn:oasis:names:tc:SAML:2.0:cm:bearer"
SAML_SUCCESS_STATUS = "urn:oasis:names:tc:SAML:2.0:status:Success"
SAML_NAMESPACES = {
    "saml": SAML_ASSERTION_NAMESPACE,
    "samlp": SAML_PROTOCOL_NAMESPACE,
    "md": SAML_METADATA_NAMESPACE,
    "ds": XML_SIGNATURE_NAMESPACE,
}


@dataclass
class ParsedForm:
    action: str
    method: str
    form_id: str
    inputs: dict[str, str] = field(default_factory=dict)


@dataclass
class SamlMetadata:
    entity_id: str
    signing_certificates: list[str]


@dataclass
class SamlLoginResult:
    response_id: str
    assertion_id: str
    name_id: str
    session_index: str
    attributes: dict[str, list[str]]


class FormParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.forms: list[ParsedForm] = []
        self._current: ParsedForm | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {key: value or "" for key, value in attrs}
        if tag == "form":
            self._current = ParsedForm(
                action=html.unescape(attributes.get("action", "")),
                method=attributes.get("method", "get").lower(),
                form_id=attributes.get("id", ""),
            )
            self.forms.append(self._current)
        elif tag == "input" and self._current is not None:
            name = attributes.get("name", "")
            if name:
                self._current.inputs[name] = attributes.get("value", "")

    def handle_endtag(self, tag: str) -> None:
        if tag == "form":
            self._current = None


class StopAtCallbackRedirect(HTTPRedirectHandler):
    def __init__(self, callback_prefix: str | tuple[str, ...]) -> None:
        super().__init__()
        self.callback_prefix = callback_prefix

    @property
    def callback_prefix(self) -> str | tuple[str, ...]:
        if len(self.callback_prefixes) == 1:
            return self.callback_prefixes[0]
        return self.callback_prefixes

    @callback_prefix.setter
    def callback_prefix(self, value: str | tuple[str, ...]) -> None:
        self.callback_prefixes = (value,) if isinstance(value, str) else value

    def redirect_request(
        self,
        req: Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> Request | None:
        if any(newurl.startswith(prefix) for prefix in self.callback_prefixes):
            return None
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _base64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _decode_base64url(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + ("=" * (-len(value) % 4)))


def _decode_jwt(token: str) -> tuple[dict[str, Any], dict[str, Any], bytes, bytes]:
    parts = token.split(".")
    if len(parts) != 3:
        raise VerificationError("Expected a compact JWT with three segments.")
    try:
        header = json.loads(_decode_base64url(parts[0]))
        claims = json.loads(_decode_base64url(parts[1]))
        signature = _decode_base64url(parts[2])
    except (ValueError, json.JSONDecodeError) as error:
        raise VerificationError(f"JWT encoding was invalid: {error}") from error
    return header, claims, signature, f"{parts[0]}.{parts[1]}".encode("ascii")


def _verify_id_token(
    token: str,
    jwks: dict[str, Any],
    *,
    issuer: str,
    client_id: str,
    nonce: str | None,
) -> dict[str, Any]:
    header, claims, signature, signed_data = _decode_jwt(token)
    if header.get("alg") != "RS256" or not header.get("kid"):
        raise VerificationError("ID token must use a keyed RS256 signature.")

    jwk = next(
        (
            candidate
            for candidate in jwks.get("keys", [])
            if candidate.get("kid") == header["kid"]
            and candidate.get("kty") == "RSA"
            and candidate.get("alg") == "RS256"
            and candidate.get("use") in {None, "sig"}
        ),
        None,
    )
    if jwk is None:
        raise VerificationError(f"JWKS did not contain ID-token key {header['kid']}.")

    try:
        public_key = rsa.RSAPublicNumbers(
            int.from_bytes(_decode_base64url(jwk["e"]), "big"),
            int.from_bytes(_decode_base64url(jwk["n"]), "big"),
        ).public_key()
        public_key.verify(signature, signed_data, padding.PKCS1v15(), hashes.SHA256())
    except (InvalidJwtSignature, KeyError, ValueError) as error:
        raise VerificationError("ID-token signature validation failed.") from error

    now = int(time.time())
    skew = 60
    if claims.get("iss") != issuer:
        raise VerificationError("ID token issuer did not match discovery.")
    audience = claims.get("aud", [])
    audience_values = [audience] if isinstance(audience, str) else audience
    if client_id not in audience_values:
        raise VerificationError("ID token audience did not include the requesting client.")
    if claims.get("azp") != client_id:
        raise VerificationError("ID token authorized party did not match the requesting client.")
    if nonce is not None and claims.get("nonce") != nonce:
        raise VerificationError("ID token nonce did not match the authorization request.")
    if not isinstance(claims.get("exp"), int) or claims["exp"] < now - skew:
        raise VerificationError("ID token was expired or omitted a numeric expiration.")
    if not isinstance(claims.get("iat"), int) or claims["iat"] > now + skew:
        raise VerificationError("ID token issuance time was invalid.")
    if isinstance(claims.get("nbf"), int) and claims["nbf"] > now + skew:
        raise VerificationError("ID token is not yet valid.")
    return claims


def _json_request(
    url: str,
    context: ssl.SSLContext,
    *,
    data: dict[str, str] | None = None,
    bearer: str | None = None,
) -> Any:
    body = urlencode(data).encode("utf-8") if data is not None else None
    headers = {
        "Accept": "application/json",
        "User-Agent": VERIFIER_USER_AGENT,
    }
    if body is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    request = Request(url, data=body, headers=headers)
    with urlopen(request, context=context, timeout=20) as response:
        return json.load(response)


def _forms(document: bytes) -> list[ParsedForm]:
    parser = FormParser()
    parser.feed(document.decode("utf-8", errors="replace"))
    return parser.forms


def _login_form(document: bytes) -> ParsedForm:
    for form in _forms(document):
        if "login-actions/authenticate" in form.action:
            return form
    raise VerificationError("Keycloak login form was not present.")


def _authorization_parameters(
    client: dict[str, Any],
    redirect_uri: str,
    *,
    response_type: str,
    state: str,
    nonce: str,
    code_challenge: str | None = None,
    response_mode: str | None = None,
    scope: str | None = None,
    prompt: str | None = None,
    max_age: int | None = None,
    acr_values: str | None = None,
) -> dict[str, str]:
    parameters = {
        "client_id": client["clientId"],
        "redirect_uri": redirect_uri,
        "response_type": response_type,
        "scope": scope or client["scope"],
        "state": state,
        "nonce": nonce,
    }
    if code_challenge:
        parameters["code_challenge"] = code_challenge
        parameters["code_challenge_method"] = "S256"
    if response_mode:
        parameters["response_mode"] = response_mode
    if prompt:
        parameters["prompt"] = prompt
    if max_age is not None:
        parameters["max_age"] = str(max_age)
    if acr_values:
        parameters["acr_values"] = acr_values
    return parameters


def _authorization_url(
    profile: dict[str, Any],
    client: dict[str, Any],
    redirect_uri: str,
    *,
    response_type: str,
    state: str,
    nonce: str,
    code_challenge: str | None = None,
    response_mode: str | None = None,
    scope: str | None = None,
    prompt: str | None = None,
    max_age: int | None = None,
    acr_values: str | None = None,
) -> str:
    parameters = _authorization_parameters(
        client,
        redirect_uri,
        response_type=response_type,
        state=state,
        nonce=nonce,
        code_challenge=code_challenge,
        response_mode=response_mode,
        scope=scope,
        prompt=prompt,
        max_age=max_age,
        acr_values=acr_values,
    )
    return f"{profile['authorizationEndpoint']}?{urlencode(parameters)}"


def _open_login(
    context: ssl.SSLContext,
    authorization_url: str,
    callback: str | tuple[str, ...],
) -> tuple[Any, bytes]:
    opener = build_opener(
        HTTPSHandler(context=context),
        HTTPCookieProcessor(CookieJar()),
        StopAtCallbackRedirect(callback),
    )
    request = Request(authorization_url, headers={"User-Agent": VERIFIER_USER_AGENT})
    with opener.open(request, timeout=20) as response:
        body = response.read()
    _login_form(body)
    return opener, body


def _submit_login(
    opener: Any,
    login_document: bytes,
    username: str,
    password: str,
    callback: str,
) -> tuple[int, str | None, bytes]:
    form = _login_form(login_document)
    values = dict(form.inputs)
    values["username"] = username
    values["password"] = password
    values["credentialId"] = values.get("credentialId", "")
    request = Request(
        form.action,
        data=urlencode(values).encode("utf-8"),
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": VERIFIER_USER_AGENT,
        },
    )
    try:
        with opener.open(request, timeout=20) as response:
            return response.status, response.headers.get("Location"), response.read()
    except HTTPError as error:
        location = error.headers.get("Location")
        if error.code in {301, 302, 303, 307, 308} and location and location.startswith(callback):
            return error.code, location, error.read()
        raise


def _submit_consent(
    opener: Any,
    consent_form: ParsedForm,
    base_url: str,
    callback: str,
) -> tuple[int, str | None]:
    consent_values = dict(consent_form.inputs)
    consent_values.pop("cancel", None)
    consent_values["accept"] = consent_values.get("accept") or "Yes"
    consent_request = Request(
        urljoin(base_url, consent_form.action),
        data=urlencode(consent_values).encode("utf-8"),
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": VERIFIER_USER_AGENT,
        },
    )
    try:
        with opener.open(consent_request, timeout=20) as response:
            return response.status, response.headers.get("Location")
    except HTTPError as error:
        location = error.headers.get("Location")
        if error.code in {301, 302, 303, 307, 308} and location and location.startswith(callback):
            return error.code, location
        raise


def _parse_saml_xml(document: bytes, description: str) -> Any:
    parser = etree.XMLParser(
        resolve_entities=False,
        no_network=True,
        load_dtd=False,
        huge_tree=False,
        remove_comments=False,
    )
    try:
        root = etree.fromstring(document, parser=parser)
    except etree.XMLSyntaxError as error:
        raise VerificationError(f"{description} was not well-formed XML: {error}") from error
    if root.getroottree().docinfo.doctype:
        raise VerificationError(f"{description} unexpectedly contained a document type.")
    return root


def _saml_timestamp(value: str | None, description: str) -> datetime:
    if not value:
        raise VerificationError(f"{description} was missing.")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise VerificationError(f"{description} was not a valid timestamp.") from error
    if parsed.tzinfo is None:
        raise VerificationError(f"{description} did not include a timezone.")
    return parsed.astimezone(timezone.utc)


def _saml_authentication_url(
    profile: dict[str, Any],
    assertion_consumer_service_url: str,
    client_key: str = "saml",
) -> tuple[str, str, str]:
    client = profile["clients"][client_key]
    request_id = f"_{_base64url(secrets.token_bytes(18))}"
    relay_state = _base64url(secrets.token_bytes(18))
    issue_instant = (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )
    request = etree.Element(
        etree.QName(SAML_PROTOCOL_NAMESPACE, "AuthnRequest"),
        nsmap={"samlp": SAML_PROTOCOL_NAMESPACE, "saml": SAML_ASSERTION_NAMESPACE},
        ID=request_id,
        Version="2.0",
        IssueInstant=issue_instant,
        Destination=profile["samlSingleSignOnEndpoint"],
        AssertionConsumerServiceURL=assertion_consumer_service_url,
        ProtocolBinding=SAML_POST_BINDING,
        ForceAuthn="true",
    )
    etree.SubElement(
        request,
        etree.QName(SAML_ASSERTION_NAMESPACE, "Issuer"),
    ).text = client["entityId"]
    etree.SubElement(
        request,
        etree.QName(SAML_PROTOCOL_NAMESPACE, "NameIDPolicy"),
        Format=client["nameIdFormat"],
        AllowCreate="true",
    )
    request_xml = etree.tostring(request, encoding="utf-8", xml_declaration=False)
    compressor = zlib.compressobj(wbits=-15)
    compressed_request = compressor.compress(request_xml) + compressor.flush()
    parameters = {
        "SAMLRequest": base64.b64encode(compressed_request).decode("ascii"),
        "RelayState": relay_state,
    }
    return (
        request_id,
        relay_state,
        f"{profile['samlSingleSignOnEndpoint']}?{urlencode(parameters)}",
    )


def _fetch_saml_metadata(
    profile: dict[str, Any],
    context: ssl.SSLContext,
) -> SamlMetadata:
    request = Request(
        profile["samlMetadataEndpoint"],
        headers={
            "Accept": "application/samlmetadata+xml, application/xml",
            "User-Agent": VERIFIER_USER_AGENT,
        },
    )
    with urlopen(request, context=context, timeout=20) as response:
        if response.status != 200:
            raise VerificationError(
                f"SAML metadata returned HTTP {response.status}; expected 200."
            )
        metadata_document = response.read()

    root = _parse_saml_xml(metadata_document, "SAML metadata")
    if root.tag != etree.QName(SAML_METADATA_NAMESPACE, "EntityDescriptor"):
        raise VerificationError("SAML metadata root was not an EntityDescriptor.")
    if root.get("entityID") != profile["issuer"]:
        raise VerificationError("SAML metadata entityID did not match the realm issuer.")

    idp_descriptors = root.findall("./md:IDPSSODescriptor", namespaces=SAML_NAMESPACES)
    if len(idp_descriptors) != 1:
        raise VerificationError("SAML metadata did not contain one IDPSSODescriptor.")
    descriptor = idp_descriptors[0]

    sso_services = {
        (service.get("Binding"), service.get("Location"))
        for service in descriptor.findall("./md:SingleSignOnService", namespaces=SAML_NAMESPACES)
    }
    for binding in (SAML_POST_BINDING, SAML_REDIRECT_BINDING):
        if (binding, profile["samlSingleSignOnEndpoint"]) not in sso_services:
            raise VerificationError(
                f"SAML metadata omitted the {binding.rsplit(':', 1)[-1]} SSO binding."
            )

    logout_services = {
        (service.get("Binding"), service.get("Location"))
        for service in descriptor.findall("./md:SingleLogoutService", namespaces=SAML_NAMESPACES)
    }
    for binding in (SAML_POST_BINDING, SAML_REDIRECT_BINDING):
        if (binding, profile["samlSingleLogoutEndpoint"]) not in logout_services:
            raise VerificationError(
                f"SAML metadata omitted the {binding.rsplit(':', 1)[-1]} logout binding."
            )

    signing_certificates: list[str] = []
    for key_descriptor in descriptor.findall("./md:KeyDescriptor", namespaces=SAML_NAMESPACES):
        if key_descriptor.get("use") not in {None, "signing"}:
            continue
        for certificate in key_descriptor.findall(
            ".//ds:X509Certificate",
            namespaces=SAML_NAMESPACES,
        ):
            encoded = "".join((certificate.text or "").split())
            if not encoded:
                continue
            try:
                base64.b64decode(encoded, validate=True)
            except ValueError as error:
                raise VerificationError(
                    "SAML metadata contained an invalid signing certificate."
                ) from error
            pem = (
                "-----BEGIN CERTIFICATE-----\n"
                + "\n".join(
                    encoded[index : index + 64]
                    for index in range(0, len(encoded), 64)
                )
                + "\n-----END CERTIFICATE-----\n"
            )
            if pem not in signing_certificates:
                signing_certificates.append(pem)
    if not signing_certificates:
        raise VerificationError("SAML metadata did not publish a signing certificate.")

    return SamlMetadata(
        entity_id=root.get("entityID"),
        signing_certificates=signing_certificates,
    )


def _verify_saml_xml_signature(
    document: bytes,
    metadata: SamlMetadata,
    *,
    location: str,
    expected_tag: etree.QName,
) -> Any:
    configuration = SignatureConfiguration(
        require_x509=False,
        location=location,
        expect_references=1,
        signature_methods=frozenset({SignatureMethod.RSA_SHA256}),
        digest_algorithms=frozenset({DigestAlgorithm.SHA256}),
    )
    last_error: Exception | None = None
    for certificate in metadata.signing_certificates:
        try:
            result = XMLVerifier().verify(
                document,
                x509_cert=certificate,
                expect_config=configuration,
                id_attribute="ID",
            )
        except (InvalidXmlSignature, ValueError, etree.XMLSyntaxError) as error:
            last_error = error
            continue
        if isinstance(result, list):
            raise VerificationError("SAML signature unexpectedly covered multiple references.")
        if result.signed_xml.tag != expected_tag:
            raise VerificationError("SAML signature covered an unexpected XML element.")
        return result.signed_xml
    raise VerificationError("SAML XML signature validation failed.") from last_error


def _saml_attribute_values(assertion: Any) -> dict[str, list[str]]:
    attributes: dict[str, list[str]] = {}
    for attribute in assertion.findall(
        "./saml:AttributeStatement/saml:Attribute",
        namespaces=SAML_NAMESPACES,
    ):
        name = attribute.get("Name", "")
        if not name:
            raise VerificationError("SAML assertion contained an unnamed attribute.")
        values = [
            "".join(value.itertext())
            for value in attribute.findall("./saml:AttributeValue", namespaces=SAML_NAMESPACES)
        ]
        attributes.setdefault(name, []).extend(values)
    return attributes


def _validate_saml_response(
    document: bytes,
    profile: dict[str, Any],
    metadata: SamlMetadata,
    *,
    assertion_consumer_service_url: str,
    request_id: str | None,
    expected_user: dict[str, Any],
) -> SamlLoginResult:
    raw_response = _parse_saml_xml(document, "SAML response")
    response_tag = etree.QName(SAML_PROTOCOL_NAMESPACE, "Response")
    assertion_tag = etree.QName(SAML_ASSERTION_NAMESPACE, "Assertion")
    if raw_response.tag != response_tag:
        raise VerificationError("SAML callback did not contain a protocol Response.")

    response = _verify_saml_xml_signature(
        document,
        metadata,
        location="./",
        expected_tag=response_tag,
    )
    assertion = _verify_saml_xml_signature(
        document,
        metadata,
        location=f"./{{{SAML_ASSERTION_NAMESPACE}}}Assertion/",
        expected_tag=assertion_tag,
    )

    response_assertions = response.findall("./saml:Assertion", namespaces=SAML_NAMESPACES)
    if len(response_assertions) != 1:
        raise VerificationError("Signed SAML response did not contain exactly one assertion.")
    if response_assertions[0].get("ID") != assertion.get("ID"):
        raise VerificationError("Signed response and signed assertion identities did not match.")

    response_id = response.get("ID", "")
    assertion_id = assertion.get("ID", "")
    if not response_id or not assertion_id or response_id == assertion_id:
        raise VerificationError("SAML response or assertion omitted a generated identifier.")
    if response.get("Version") != "2.0" or assertion.get("Version") != "2.0":
        raise VerificationError("SAML response or assertion did not declare version 2.0.")
    if response.get("Destination") != assertion_consumer_service_url:
        raise VerificationError("SAML response Destination did not match the exact ACS URL.")
    if request_id is None:
        if response.get("InResponseTo"):
            raise VerificationError("IdP-initiated SAML response unexpectedly had InResponseTo.")
    elif response.get("InResponseTo") != request_id:
        raise VerificationError("SAML response InResponseTo did not match the AuthnRequest.")

    now = datetime.now(timezone.utc)
    skew = timedelta(seconds=60)
    issue_instant = _saml_timestamp(response.get("IssueInstant"), "SAML response IssueInstant")
    if issue_instant > now + skew or issue_instant < now - timedelta(minutes=10):
        raise VerificationError("SAML response IssueInstant was outside the current login window.")

    response_issuers = response.findall("./saml:Issuer", namespaces=SAML_NAMESPACES)
    assertion_issuers = assertion.findall("./saml:Issuer", namespaces=SAML_NAMESPACES)
    if (
        len(response_issuers) != 1
        or len(assertion_issuers) != 1
        or response_issuers[0].text != metadata.entity_id
        or assertion_issuers[0].text != metadata.entity_id
    ):
        raise VerificationError("SAML response or assertion issuer did not match metadata.")

    status_codes = response.findall(
        "./samlp:Status/samlp:StatusCode",
        namespaces=SAML_NAMESPACES,
    )
    if len(status_codes) != 1 or status_codes[0].get("Value") != SAML_SUCCESS_STATUS:
        raise VerificationError("SAML response did not contain a Success status.")

    subjects = assertion.findall("./saml:Subject", namespaces=SAML_NAMESPACES)
    if len(subjects) != 1:
        raise VerificationError("SAML assertion did not contain exactly one Subject.")
    name_ids = subjects[0].findall("./saml:NameID", namespaces=SAML_NAMESPACES)
    if (
        len(name_ids) != 1
        or name_ids[0].get("Format") != SAML_PERSISTENT_NAME_ID
        or name_ids[0].text != expected_user["samlNameId"]
    ):
        raise VerificationError("SAML persistent NameID was missing or changed.")

    confirmations = subjects[0].findall(
        "./saml:SubjectConfirmation",
        namespaces=SAML_NAMESPACES,
    )
    if len(confirmations) != 1 or confirmations[0].get("Method") != SAML_BEARER_CONFIRMATION:
        raise VerificationError("SAML assertion did not use one bearer SubjectConfirmation.")
    confirmation_data = confirmations[0].findall(
        "./saml:SubjectConfirmationData",
        namespaces=SAML_NAMESPACES,
    )
    if len(confirmation_data) != 1:
        raise VerificationError("SAML assertion omitted SubjectConfirmationData.")
    if confirmation_data[0].get("Recipient") != assertion_consumer_service_url:
        raise VerificationError("SAML SubjectConfirmation recipient did not match the ACS URL.")
    if request_id is None:
        if confirmation_data[0].get("InResponseTo"):
            raise VerificationError(
                "IdP-initiated SubjectConfirmation unexpectedly had InResponseTo."
            )
    elif confirmation_data[0].get("InResponseTo") != request_id:
        raise VerificationError("SAML SubjectConfirmation did not bind to the AuthnRequest.")
    confirmation_expiration = _saml_timestamp(
        confirmation_data[0].get("NotOnOrAfter"),
        "SAML SubjectConfirmation expiration",
    )
    if confirmation_expiration <= now - skew:
        raise VerificationError("SAML SubjectConfirmation was already expired.")

    conditions = assertion.findall("./saml:Conditions", namespaces=SAML_NAMESPACES)
    if len(conditions) != 1:
        raise VerificationError("SAML assertion did not contain exactly one Conditions element.")
    not_before = _saml_timestamp(conditions[0].get("NotBefore"), "SAML NotBefore")
    not_on_or_after = _saml_timestamp(
        conditions[0].get("NotOnOrAfter"),
        "SAML NotOnOrAfter",
    )
    if not_before > now + skew or not_on_or_after <= now - skew:
        raise VerificationError("SAML assertion conditions were not currently valid.")
    if not_on_or_after - not_before > timedelta(minutes=6):
        raise VerificationError("SAML assertion lifetime exceeded the five-minute profile.")
    if len(conditions[0].findall("./saml:OneTimeUse", namespaces=SAML_NAMESPACES)) != 1:
        raise VerificationError("SAML assertion omitted the OneTimeUse condition.")
    audiences = [
        audience.text
        for audience in conditions[0].findall(
            "./saml:AudienceRestriction/saml:Audience",
            namespaces=SAML_NAMESPACES,
        )
    ]
    if audiences != [profile["clients"]["saml"]["entityId"]]:
        raise VerificationError("SAML assertion audience did not exactly match the SP entity ID.")

    authn_statements = assertion.findall(
        "./saml:AuthnStatement",
        namespaces=SAML_NAMESPACES,
    )
    if len(authn_statements) != 1 or not authn_statements[0].get("SessionIndex"):
        raise VerificationError("SAML assertion omitted its AuthnStatement or SessionIndex.")
    authn_instant = _saml_timestamp(
        authn_statements[0].get("AuthnInstant"),
        "SAML AuthnInstant",
    )
    if authn_instant > now + skew or authn_instant < now - timedelta(minutes=10):
        raise VerificationError("SAML AuthnInstant was outside the current login window.")
    authentication_contexts = authn_statements[0].findall(
        "./saml:AuthnContext/saml:AuthnContextClassRef",
        namespaces=SAML_NAMESPACES,
    )
    if len(authentication_contexts) != 1 or not authentication_contexts[0].text:
        raise VerificationError("SAML assertion omitted one authentication context.")
    allowed_authentication_contexts = profile["clients"]["saml"].get(
        "allowedAuthenticationContextClassReferences",
        [],
    )
    if (
        allowed_authentication_contexts
        and authentication_contexts[0].text not in allowed_authentication_contexts
    ):
        raise VerificationError(
            "SAML authentication context "
            f"{authentication_contexts[0].text!r} was outside the configured allowlist."
        )

    attributes = _saml_attribute_values(assertion)
    client = profile["clients"]["saml"]
    allowed_claims = client.get(
        "allowedClaims",
        list(expected_user["expectedAttributes"]) + ["realm_roles"],
    )
    unexpected_claims = sorted(set(attributes) - set(allowed_claims))
    if unexpected_claims:
        raise VerificationError(
            f"SAML assertion emitted a claim outside the allowlist: {unexpected_claims[0]}."
        )
    for attribute_name in allowed_claims:
        if attribute_name == "realm_roles":
            continue
        if attribute_name not in expected_user["expectedAttributes"]:
            raise VerificationError(
                f"SAML verifier has no expected value for allowlisted claim {attribute_name}."
            )
        expected_value = expected_user["expectedAttributes"][attribute_name]
        actual_values = attributes.get(attribute_name)
        expected_values = (
            [str(value) for value in expected_value]
            if isinstance(expected_value, list)
            else [str(expected_value)]
        )
        values_match = (
            actual_values is None or actual_values == []
            if not expected_values
            else actual_values is not None and set(actual_values) == set(expected_values)
        )
        if not values_match:
            raise VerificationError(
                f"SAML attribute {attribute_name} did not match the generated user profile."
            )
    expected_roles = set(expected_user["expectedAttributes"]["eem_permission_profiles"])
    if "realm_roles" in allowed_claims and not expected_roles.issubset(
        attributes.get("realm_roles", [])
    ):
        raise VerificationError("SAML realm_roles omitted expected permission-profile roles.")
    subject_attribute = client.get("subjectAttribute")
    if client.get("subjectBindingKind") == "Attribute" and not attributes.get(
        subject_attribute or ""
    ):
        raise VerificationError("SAML attribute-bound subject was not emitted.")
    if any(name.startswith("saml.persistent.name.id.for.") for name in attributes):
        raise VerificationError("Internal persistent-NameID state leaked into SAML attributes.")

    return SamlLoginResult(
        response_id=response_id,
        assertion_id=assertion_id,
        name_id=name_ids[0].text,
        session_index=authn_statements[0].get("SessionIndex"),
        attributes=attributes,
    )


def _saml_callback_form(
    body: bytes,
    assertion_consumer_service_url: str,
    relay_state: str,
) -> bytes:
    callback_forms = [
        form
        for form in _forms(body)
        if form.action == assertion_consumer_service_url
        and form.method == "post"
        and "SAMLResponse" in form.inputs
    ]
    if len(callback_forms) != 1:
        raise VerificationError("SAML login did not produce one HTTP-POST ACS callback.")
    callback_form = callback_forms[0]
    if callback_form.inputs.get("RelayState") != relay_state:
        raise VerificationError("SAML callback did not preserve RelayState.")
    try:
        return base64.b64decode(callback_form.inputs["SAMLResponse"], validate=True)
    except ValueError as error:
        raise VerificationError("SAMLResponse was not valid base64.") from error


def _saml_logout_url(
    profile: dict[str, Any],
    login_result: SamlLoginResult,
) -> tuple[str, str, str]:
    client = profile["clients"]["saml"]
    request_id = f"_{_base64url(secrets.token_bytes(18))}"
    relay_state = _base64url(secrets.token_bytes(18))
    issue_instant = (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )
    request = etree.Element(
        etree.QName(SAML_PROTOCOL_NAMESPACE, "LogoutRequest"),
        nsmap={"samlp": SAML_PROTOCOL_NAMESPACE, "saml": SAML_ASSERTION_NAMESPACE},
        ID=request_id,
        Version="2.0",
        IssueInstant=issue_instant,
        Destination=profile["samlSingleLogoutEndpoint"],
    )
    etree.SubElement(
        request,
        etree.QName(SAML_ASSERTION_NAMESPACE, "Issuer"),
    ).text = client["entityId"]
    etree.SubElement(
        request,
        etree.QName(SAML_ASSERTION_NAMESPACE, "NameID"),
        Format=client["nameIdFormat"],
    ).text = login_result.name_id
    etree.SubElement(
        request,
        etree.QName(SAML_PROTOCOL_NAMESPACE, "SessionIndex"),
    ).text = login_result.session_index
    request_xml = etree.tostring(request, encoding="utf-8", xml_declaration=False)
    compressor = zlib.compressobj(wbits=-15)
    compressed_request = compressor.compress(request_xml) + compressor.flush()
    parameters = {
        "SAMLRequest": base64.b64encode(compressed_request).decode("ascii"),
        "RelayState": relay_state,
    }
    return (
        request_id,
        relay_state,
        f"{profile['samlSingleLogoutEndpoint']}?{urlencode(parameters)}",
    )


def _saml_redirect_response(
    location: str,
    relay_state: str,
    metadata: SamlMetadata,
) -> bytes:
    parsed = urlparse(location)
    raw_parameters: dict[str, str] = {}
    for part in parsed.query.split("&"):
        name, separator, value = part.partition("=")
        if not separator or name in raw_parameters:
            raise VerificationError("SAML Redirect response query was malformed.")
        raw_parameters[name] = value
    required = {"SAMLResponse", "RelayState", "SigAlg", "Signature"}
    if not required.issubset(raw_parameters):
        raise VerificationError("SAML Redirect response omitted signature parameters.")

    parameters = parse_qs(parsed.query, keep_blank_values=True)
    if parameters.get("RelayState") != [relay_state]:
        raise VerificationError("SAML logout Redirect response changed RelayState.")
    rsa_sha256 = "http://www.w3.org/2001/04/xmldsig-more#rsa-sha256"
    if parameters.get("SigAlg") != [rsa_sha256]:
        raise VerificationError("SAML logout Redirect response did not use RSA-SHA256.")

    signed_query = (
        f"SAMLResponse={raw_parameters['SAMLResponse']}"
        f"&RelayState={raw_parameters['RelayState']}"
        f"&SigAlg={raw_parameters['SigAlg']}"
    ).encode("ascii")
    try:
        signature = base64.b64decode(
            unquote_plus(raw_parameters["Signature"]),
            validate=True,
        )
    except ValueError as error:
        raise VerificationError("SAML Redirect signature was not valid base64.") from error

    signature_valid = False
    for certificate in metadata.signing_certificates:
        public_key = x509.load_pem_x509_certificate(
            certificate.encode("ascii")
        ).public_key()
        if not isinstance(public_key, rsa.RSAPublicKey):
            continue
        try:
            public_key.verify(
                signature,
                signed_query,
                padding.PKCS1v15(),
                hashes.SHA256(),
            )
        except InvalidJwtSignature:
            continue
        signature_valid = True
        break
    if not signature_valid:
        raise VerificationError("SAML Redirect binding signature validation failed.")

    try:
        compressed_response = base64.b64decode(
            parameters["SAMLResponse"][0],
            validate=True,
        )
        return zlib.decompress(compressed_response, wbits=-15)
    except (ValueError, zlib.error) as error:
        raise VerificationError("SAML Redirect response encoding was invalid.") from error


def _validate_saml_logout_response(
    document: bytes,
    profile: dict[str, Any],
    metadata: SamlMetadata,
    *,
    request_id: str,
    signed_xml: bool,
) -> None:
    logout_response_tag = etree.QName(SAML_PROTOCOL_NAMESPACE, "LogoutResponse")
    if signed_xml:
        response = _verify_saml_xml_signature(
            document,
            metadata,
            location="./",
            expected_tag=logout_response_tag,
        )
    else:
        response = _parse_saml_xml(document, "SAML LogoutResponse")
        if response.tag != logout_response_tag:
            raise VerificationError("SAML logout callback was not a LogoutResponse.")

    client = profile["clients"]["saml"]
    if (
        not response.get("ID")
        or response.get("Version") != "2.0"
        or response.get("InResponseTo") != request_id
        or response.get("Destination") != client["defaultSingleLogoutServiceUrl"]
    ):
        raise VerificationError("SAML LogoutResponse did not bind to the request and SP URL.")
    issue_instant = _saml_timestamp(
        response.get("IssueInstant"),
        "SAML LogoutResponse IssueInstant",
    )
    now = datetime.now(timezone.utc)
    if (
        issue_instant > now + timedelta(seconds=60)
        or issue_instant < now - timedelta(minutes=10)
    ):
        raise VerificationError("SAML LogoutResponse IssueInstant was outside the current window.")
    issuers = response.findall("./saml:Issuer", namespaces=SAML_NAMESPACES)
    status_codes = response.findall(
        "./samlp:Status/samlp:StatusCode",
        namespaces=SAML_NAMESPACES,
    )
    if (
        len(issuers) != 1
        or issuers[0].text != metadata.entity_id
        or len(status_codes) != 1
        or status_codes[0].get("Value") != SAML_SUCCESS_STATUS
    ):
        raise VerificationError("SAML LogoutResponse issuer or status was invalid.")


def _verify_saml_logout(
    opener: Any,
    profile: dict[str, Any],
    metadata: SamlMetadata,
    login_result: SamlLoginResult,
) -> None:
    client = profile["clients"]["saml"]
    logout_service_url = client["defaultSingleLogoutServiceUrl"]
    request_id, relay_state, logout_url = _saml_logout_url(profile, login_result)
    redirect_handler = next(
        (
            handler
            for handler in opener.handlers
            if isinstance(handler, StopAtCallbackRedirect)
        ),
        None,
    )
    if redirect_handler is None:
        raise VerificationError("SAML browser did not expose its redirect guard.")
    previous_callback = redirect_handler.callback_prefix
    redirect_handler.callback_prefix = logout_service_url
    try:
        try:
            with opener.open(
                Request(logout_url, headers={"User-Agent": VERIFIER_USER_AGENT}),
                timeout=20,
            ) as response:
                status = response.status
                location = response.headers.get("Location")
                body = response.read()
        except HTTPError as error:
            location = error.headers.get("Location")
            if (
                error.code not in {301, 302, 303, 307, 308}
                or not location
                or not location.startswith(logout_service_url)
            ):
                raise
            status = error.code
            body = error.read()
    finally:
        redirect_handler.callback_prefix = previous_callback

    if location:
        response_document = _saml_redirect_response(
            location,
            relay_state,
            metadata,
        )
        signed_xml = False
    else:
        if status != 200:
            raise VerificationError("SAML logout did not return a callback response.")
        response_document = _saml_callback_form(
            body,
            logout_service_url,
            relay_state,
        )
        signed_xml = True
    _validate_saml_logout_response(
        response_document,
        profile,
        metadata,
        request_id=request_id,
        signed_xml=signed_xml,
    )

    with opener.open(
        Request(client["idpInitiatedSsoUrl"], headers={"User-Agent": VERIFIER_USER_AGENT}),
        timeout=20,
    ) as response:
        post_logout_document = response.read()
    _login_form(post_logout_document)


def _verify_saml(
    profile: dict[str, Any],
    context: ssl.SSLContext,
) -> None:
    metadata = _fetch_saml_metadata(profile, context)
    client = profile["clients"]["saml"]
    assertion_consumer_service_url = client["defaultAssertionConsumerServiceUrl"]

    invalid_acs = "https://attacker.example/saml/acs"
    _, _, invalid_url = _saml_authentication_url(profile, invalid_acs)
    try:
        with urlopen(
            Request(invalid_url, headers={"User-Agent": VERIFIER_USER_AGENT}),
            context=context,
            timeout=20,
        ) as response:
            response.read()
        raise VerificationError("Unregistered SAML Assertion Consumer Service URL was accepted.")
    except HTTPError as error:
        if error.headers.get("Location", "").startswith(invalid_acs):
            raise VerificationError("SAML error was redirected to an unregistered ACS URL.")
        if error.code != 400:
            raise VerificationError(
                f"Invalid SAML ACS returned HTTP {error.code}; expected 400."
            ) from error

    request_id, relay_state, authentication_url = _saml_authentication_url(
        profile,
        assertion_consumer_service_url,
    )
    opener, login_document = _open_login(
        context,
        authentication_url,
        assertion_consumer_service_url,
    )
    status, location, body = _submit_login(
        opener,
        login_document,
        profile["testUsers"]["active"]["username"],
        profile["testUsers"]["password"],
        assertion_consumer_service_url,
    )
    if status != 200 or location:
        raise VerificationError("SP-initiated SAML login did not return an HTTP-POST form.")
    response_document = _saml_callback_form(
        body,
        assertion_consumer_service_url,
        relay_state,
    )
    sp_initiated = _validate_saml_response(
        response_document,
        profile,
        metadata,
        assertion_consumer_service_url=assertion_consumer_service_url,
        request_id=request_id,
        expected_user=profile["testUsers"]["active"],
    )
    if client.get("enableSingleLogout", True):
        _verify_saml_logout(opener, profile, metadata, sp_initiated)

    idp_opener, idp_login_document = _open_login(
        context,
        client["idpInitiatedSsoUrl"],
        assertion_consumer_service_url,
    )
    idp_status, idp_location, idp_body = _submit_login(
        idp_opener,
        idp_login_document,
        profile["testUsers"]["active"]["username"],
        profile["testUsers"]["password"],
        assertion_consumer_service_url,
    )
    if idp_status != 200 or idp_location:
        raise VerificationError("IdP-initiated SAML login did not return an HTTP-POST form.")
    idp_response_document = _saml_callback_form(
        idp_body,
        assertion_consumer_service_url,
        client["idpInitiatedRelayState"],
    )
    idp_initiated = _validate_saml_response(
        idp_response_document,
        profile,
        metadata,
        assertion_consumer_service_url=assertion_consumer_service_url,
        request_id=None,
        expected_user=profile["testUsers"]["active"],
    )
    if (
        sp_initiated.response_id == idp_initiated.response_id
        or sp_initiated.assertion_id == idp_initiated.assertion_id
    ):
        raise VerificationError("SAML logins reused a response or assertion identifier.")

    _, _, disabled_url = _saml_authentication_url(
        profile,
        assertion_consumer_service_url,
    )
    disabled_opener, disabled_login_document = _open_login(
        context,
        disabled_url,
        assertion_consumer_service_url,
    )
    disabled_status, disabled_location, disabled_body = _submit_login(
        disabled_opener,
        disabled_login_document,
        profile["testUsers"]["disabled"]["username"],
        profile["testUsers"]["password"],
        assertion_consumer_service_url,
    )
    if disabled_location and disabled_location.startswith(assertion_consumer_service_url):
        raise VerificationError("Disabled user received a SAML authorization response.")
    if any("SAMLResponse" in form.inputs for form in _forms(disabled_body)):
        raise VerificationError("Disabled user received a SAMLResponse form.")
    disabled_document = disabled_body.decode("utf-8", errors="replace")
    if disabled_status != 200 or (
        "alert-error" not in disabled_document
        and "invalid" not in disabled_document.lower()
    ):
        raise VerificationError("Disabled SAML user did not remain on a controlled login error.")
    logout_result = (
        "signed single logout"
        if client.get("enableSingleLogout", True)
        else "configured local-only logout policy"
    )
    print(
        "[OK] Standard SAML: metadata and signing keys, exact ACS rejection, signed "
        "response and assertion, configured subject binding, audience/time/request "
        f"binding, allowlisted Northlake attributes, SP/IdP-initiated POST login, {logout_result}, "
        "unique IDs, and disabled-user denial."
    )


def _verify_admin(
    profile: dict[str, Any],
    context: ssl.SSLContext,
) -> None:
    admin_token = _json_request(
        f"{profile['baseUrl']}/realms/master/protocol/openid-connect/token",
        context,
        data={
            "grant_type": "password",
            "client_id": "admin-cli",
            "username": profile["admin"]["username"],
            "password": profile["admin"]["password"],
        },
    )["access_token"]

    users = _json_request(
        f"{profile['baseUrl']}/admin/realms/{profile['realm']}/users?max=100",
        context,
        bearer=admin_token,
    )
    groups = _json_request(
        f"{profile['baseUrl']}/admin/realms/{profile['realm']}/groups?max=100&briefRepresentation=false",
        context,
        bearer=admin_token,
    )
    clients = _json_request(
        f"{profile['baseUrl']}/admin/realms/{profile['realm']}/clients",
        context,
        bearer=admin_token,
    )

    expected_user_inventory = profile.get(
        "userInventory",
        {"total": 19, "enabled": 18, "local": 0},
    )
    if len(users) != expected_user_inventory["total"]:
        raise VerificationError(
            f"Admin API returned {len(users)} users; expected "
            f"{expected_user_inventory['total']}."
        )
    enabled_user_count = sum(bool(user["enabled"]) for user in users)
    if enabled_user_count != expected_user_inventory["enabled"]:
        raise VerificationError(
            f"Admin API returned {enabled_user_count} enabled users; expected "
            f"{expected_user_inventory['enabled']}."
        )
    expected_group_inventory = profile.get(
        "groupInventory",
        {"total": 27, "local": 0},
    )
    if len(groups) != expected_group_inventory["total"]:
        raise VerificationError(
            f"Admin API returned {len(groups)} groups; expected "
            f"{expected_group_inventory['total']}."
        )
    active_user = next(
        user
        for user in users
        if user["username"] == profile["testUsers"]["active"]["username"]
    )
    effective_realm_roles = _json_request(
        f"{profile['baseUrl']}/admin/realms/{profile['realm']}/users/"
        f"{active_user['id']}/role-mappings/realm/composite",
        context,
        bearer=admin_token,
    )
    if "offline_access" not in {role["name"] for role in effective_realm_roles}:
        raise VerificationError("Active synthetic user is not allowed to request offline access.")

    by_client_id = {client["clientId"]: client for client in clients}
    for client in profile["clients"].values():
        if client["clientId"] not in by_client_id:
            raise VerificationError(f"Admin API did not return client {client['clientId']}.")
        actual_redirects = by_client_id[client["clientId"]]["redirectUris"]
        if (
            len(actual_redirects) != len(client["redirectUris"])
            or set(actual_redirects) != set(client["redirectUris"])
        ):
            raise VerificationError(f"Redirect URI drift detected for {client['clientId']}.")

    modern_profile = profile["clients"].get("modern")
    legacy_profile = profile["clients"].get("legacy")
    if (modern_profile is None) != (legacy_profile is None):
        raise VerificationError("OIDC modern and legacy clients must be enabled together.")
    if modern_profile is not None and legacy_profile is not None:
        modern = by_client_id[modern_profile["clientId"]]
        if (
            modern.get("implicitFlowEnabled")
            or not modern.get("standardFlowEnabled")
            or not modern.get("consentRequired")
            or modern.get("attributes", {}).get("pkce.code.challenge.method") != "S256"
            or "offline_access" not in modern.get("optionalClientScopes", [])
        ):
            raise VerificationError(
                "Modern client drifted from code + PKCE, consent, or offline-access settings."
            )
        legacy = by_client_id[legacy_profile["clientId"]]
        if not legacy.get("implicitFlowEnabled") or legacy.get("consentRequired"):
            raise VerificationError(
                "Legacy client drifted from its explicit compatibility settings."
            )

    saml_profile = profile["clients"].get("saml")
    if saml_profile is not None:
        saml = by_client_id[saml_profile["clientId"]]
        saml_attributes = saml.get("attributes", {})
        if (
            saml.get("protocol") != "saml"
            or saml_attributes.get("saml.server.signature") != "true"
            or saml_attributes.get("saml.assertion.signature") != "true"
            or saml_attributes.get("saml.signature.algorithm") != "RSA_SHA256"
            or saml_attributes.get("saml.force.post.binding") != "true"
            or saml_attributes.get("saml.client.signature") != "false"
            or saml_attributes.get("saml.encrypt") != "false"
            or saml_attributes.get("saml.onetimeuse.condition") != "true"
            or saml_attributes.get("saml_name_id_format") != "persistent"
        ):
            raise VerificationError("SAML client drifted from its signed baseline profile.")
        expected_saml_mappers = set(saml_profile.get("allowedClaims", []))
        actual_saml_mappers = {
            mapper["name"] for mapper in saml.get("protocolMappers", [])
        }
        if actual_saml_mappers != expected_saml_mappers:
            raise VerificationError("SAML client protocol-mapper set drifted.")

    saml2int_profile = profile["clients"].get("saml2Int")
    if saml2int_profile is not None:
        saml2int = by_client_id[saml2int_profile["clientId"]]
        saml2int_attributes = saml2int.get("attributes", {})
        if (
            saml2int.get("protocol") != "saml"
            or saml2int_profile.get("validationProfile") != "Saml2Int"
            or saml2int_attributes.get("saml.server.signature") != "true"
            or saml2int_attributes.get("saml.assertion.signature") != "false"
            or saml2int_attributes.get("saml.signature.algorithm") != "RSA_SHA256"
            or saml2int_attributes.get("saml.force.post.binding") != "true"
            or saml2int_attributes.get("saml.client.signature") != "true"
            or saml2int_attributes.get("saml.encrypt") != "true"
            or not saml2int_attributes.get("saml.signing.certificate")
            or not saml2int_attributes.get("saml.encryption.certificate")
            or saml2int_attributes.get("saml.signing.certificate")
            != saml2int_attributes.get("saml.encryption.certificate")
        ):
            raise VerificationError(
                "SAML2Int client drifted from signed-request and encrypted-assertion settings."
            )
        actual_saml2int_mappers = {
            mapper["name"] for mapper in saml2int.get("protocolMappers", [])
        }
        if actual_saml2int_mappers != set(saml2int_profile.get("allowedClaims", [])):
            raise VerificationError("SAML2Int client protocol-mapper set drifted.")
        print(
            "[OK] Admin API: SAML2Int requires signed requests and encrypted assertions "
            "with the configured EEM public certificate."
        )

    disabled_username = profile["testUsers"]["disabled"]["username"]
    disabled = next((user for user in users if user["username"] == disabled_username), None)
    if disabled is None or disabled["enabled"]:
        raise VerificationError("Disabled-user regression identity was not disabled.")
    print(
        f"[OK] Admin API: {len(users)} users, {enabled_user_count} enabled, "
        f"{len(groups)} groups, "
        f"and {len(profile['clients'])} "
        "exact EEMSuite OIDC/SAML clients."
    )


def _verify_modern_code_flow(
    profile: dict[str, Any],
    context: ssl.SSLContext,
    discovery: dict[str, Any],
    jwks: dict[str, Any],
) -> None:
    client = profile["clients"]["modern"]
    redirect_uri = client["redirectUris"][0]
    verifier = _base64url(secrets.token_bytes(48))
    challenge = _base64url(hashlib.sha256(verifier.encode("ascii")).digest())
    state = _base64url(secrets.token_bytes(18))
    nonce = _base64url(secrets.token_bytes(18))
    authorization_parameters = _authorization_parameters(
        client,
        redirect_uri,
        response_type="code",
        state=state,
        nonce=nonce,
        code_challenge=challenge,
        prompt="login consent",
        acr_values="1",
    )
    pushed_request = _json_request(
        discovery["pushed_authorization_request_endpoint"],
        context,
        data={
            **authorization_parameters,
            "client_secret": client["clientSecret"],
        },
    )
    if not pushed_request.get("request_uri") or pushed_request.get("expires_in", 0) <= 0:
        raise VerificationError("PAR did not return a usable request URI and lifetime.")
    authorization_url = (
        f"{profile['authorizationEndpoint']}?"
        + urlencode(
            {
                "client_id": client["clientId"],
                "request_uri": pushed_request["request_uri"],
            }
        )
    )

    opener, login_document = _open_login(context, authorization_url, redirect_uri)
    status, location, response_body = _submit_login(
        opener,
        login_document,
        profile["testUsers"]["active"]["username"],
        f"{profile['testUsers']['password']}-invalid",
        redirect_uri,
    )
    invalid_document = response_body.decode("utf-8", errors="replace")
    if (
        status != 200
        or location
        or "invalid" not in invalid_document.lower()
        or not any(
            "login-actions/authenticate" in form.action
            for form in _forms(response_body)
        )
    ):
        raise VerificationError(
            "Modern client did not allow retry after invalid credentials."
        )

    status, location, response_body = _submit_login(
        opener,
        response_body,
        profile["testUsers"]["active"]["username"],
        profile["testUsers"]["password"],
        redirect_uri,
    )
    if location:
        raise VerificationError("Modern client did not stop for the required consent grant.")
    consent_form = next(
        (
            form
            for form in _forms(response_body)
            if "login-actions/consent" in form.action
        ),
        None,
    )
    if status != 200 or consent_form is None:
        raise VerificationError("Modern login did not present the Keycloak consent page.")

    status, location = _submit_consent(
        opener,
        consent_form,
        profile["baseUrl"],
        redirect_uri,
    )
    if status not in {301, 302, 303, 307, 308} or not location:
        raise VerificationError("Modern login did not redirect with an authorization code.")

    callback = urlparse(location)
    parameters = parse_qs(callback.query)
    if parameters.get("state") != [state] or "code" not in parameters:
        raise VerificationError("Modern callback did not preserve state and authorization code.")
    if parameters.get("iss") != [profile["issuer"]]:
        raise VerificationError("Modern callback omitted or changed the authorization issuer.")

    tokens = _json_request(
        profile["tokenEndpoint"],
        context,
        data={
            "grant_type": "authorization_code",
            "client_id": client["clientId"],
            "client_secret": client["clientSecret"],
            "code": parameters["code"][0],
            "redirect_uri": redirect_uri,
            "code_verifier": verifier,
        },
    )
    if not {"access_token", "id_token", "refresh_token"}.issubset(tokens):
        raise VerificationError("Modern token response did not include access, ID, and refresh tokens.")
    if "offline_access" in set(tokens.get("scope", "").split()):
        raise VerificationError("Online SSO setup unexpectedly granted offline access.")

    claims = _verify_id_token(
        tokens["id_token"],
        jwks,
        issuer=profile["issuer"],
        client_id=client["clientId"],
        nonce=nonce,
    )
    if claims.get("sub") != profile["testUsers"]["active"]["subject"]:
        raise VerificationError("Stable synthetic subject changed.")
    now = int(time.time())
    if (
        not isinstance(claims.get("auth_time"), int)
        or claims["auth_time"] > now + 60
        or claims["auth_time"] < now - 300
    ):
        raise VerificationError(
            "ID token auth_time was missing or outside the current login window "
            f"(auth_time={claims.get('auth_time')!r}, now={now})."
        )
    if claims.get("acr") != "1":
        raise VerificationError("ID token did not return the selected ACR value.")

    userinfo = _json_request(
        profile["userinfoEndpoint"],
        context,
        bearer=tokens["access_token"],
    )
    for required_claim in (
        "sub",
        "preferred_username",
        "email",
        "groups",
        "primary_company_id",
        "eem_permission_profiles",
    ):
        if required_claim not in userinfo:
            raise VerificationError(f"UserInfo omitted required claim {required_claim}.")

    session_client = profile["clients"]["legacy"]
    if session_client["redirectUris"][0] != redirect_uri:
        raise VerificationError("Session prompt test requires a shared registered callback URI.")
    silent_state = _base64url(secrets.token_bytes(12))
    silent_url = _authorization_url(
        profile,
        session_client,
        redirect_uri,
        response_type="code",
        state=silent_state,
        nonce=_base64url(secrets.token_bytes(12)),
        prompt="none",
    )
    try:
        opener.open(
            Request(silent_url, headers={"User-Agent": VERIFIER_USER_AGENT}),
            timeout=20,
        )
        raise VerificationError("prompt=none did not return an authorization response.")
    except HTTPError as error:
        silent_location = error.headers.get("Location", "")
        if error.code not in {301, 302, 303, 307, 308} or not silent_location.startswith(
            redirect_uri
        ):
            raise
        silent_parameters = parse_qs(urlparse(silent_location).query)
        if (
            silent_parameters.get("state") != [silent_state]
            or "code" not in silent_parameters
            or "error" in silent_parameters
        ):
            raise VerificationError(
                "prompt=none did not reuse the active provider session "
                f"(callback={silent_parameters!r})."
            )

    time.sleep(1.1)
    stale_state = _base64url(secrets.token_bytes(12))
    stale_url = _authorization_url(
        profile,
        session_client,
        redirect_uri,
        response_type="code",
        state=stale_state,
        nonce=_base64url(secrets.token_bytes(12)),
        prompt="none",
        max_age=0,
    )
    try:
        opener.open(
            Request(stale_url, headers={"User-Agent": VERIFIER_USER_AGENT}),
            timeout=20,
        )
        raise VerificationError("max_age=0 with prompt=none did not require authentication.")
    except HTTPError as error:
        stale_location = error.headers.get("Location", "")
        if error.code not in {301, 302, 303, 307, 308} or not stale_location.startswith(
            redirect_uri
        ):
            raise
        stale_parameters = parse_qs(urlparse(stale_location).query)
        if (
            stale_parameters.get("state") != [stale_state]
            or stale_parameters.get("error") != ["login_required"]
        ):
            raise VerificationError("max_age=0 did not produce the expected login_required error.")

    offline_verifier = _base64url(secrets.token_bytes(48))
    offline_challenge = _base64url(
        hashlib.sha256(offline_verifier.encode("ascii")).digest()
    )
    offline_state = _base64url(secrets.token_bytes(18))
    offline_nonce = _base64url(secrets.token_bytes(18))
    offline_parameters = _authorization_parameters(
        client,
        redirect_uri,
        response_type="code",
        state=offline_state,
        nonce=offline_nonce,
        code_challenge=offline_challenge,
        prompt="consent",
        acr_values="1",
        scope=f"{client['scope']} offline_access",
    )
    offline_pushed_request = _json_request(
        discovery["pushed_authorization_request_endpoint"],
        context,
        data={
            **offline_parameters,
            "client_secret": client["clientSecret"],
        },
    )
    if (
        not offline_pushed_request.get("request_uri")
        or offline_pushed_request.get("expires_in", 0) <= 0
    ):
        raise VerificationError("Offline PAR did not return a usable request URI and lifetime.")
    offline_authorization_url = (
        f"{profile['authorizationEndpoint']}?"
        + urlencode(
            {
                "client_id": client["clientId"],
                "request_uri": offline_pushed_request["request_uri"],
            }
        )
    )
    offline_request = Request(
        offline_authorization_url,
        headers={"User-Agent": VERIFIER_USER_AGENT},
    )
    try:
        with opener.open(offline_request, timeout=20) as response:
            status = response.status
            location = response.headers.get("Location")
            response_body = response.read()
    except HTTPError as error:
        location = error.headers.get("Location")
        if (
            error.code not in {301, 302, 303, 307, 308}
            or not location
            or not location.startswith(redirect_uri)
        ):
            raise
        status = error.code
        response_body = error.read()
    offline_forms = _forms(response_body)
    offline_consent_form = next(
        (
            form
            for form in offline_forms
            if "login-actions/consent" in form.action
        ),
        None,
    )
    if status != 200 or location or offline_consent_form is None:
        raise VerificationError(
            "Offline-access authorization did not reuse SSO and present consent without a "
            f"password (status={status}, location={location!r}, "
            f"forms={[form.action for form in offline_forms]!r})."
        )
    status, location = _submit_consent(
        opener,
        offline_consent_form,
        profile["baseUrl"],
        redirect_uri,
    )
    if status not in {301, 302, 303, 307, 308} or not location:
        raise VerificationError(
            "Offline-access consent did not redirect with an authorization code."
        )
    offline_parameters = parse_qs(urlparse(location).query)
    if (
        offline_parameters.get("state") != [offline_state]
        or "code" not in offline_parameters
    ):
        raise VerificationError(
            "Offline-access callback did not preserve state and authorization code."
        )
    if offline_parameters.get("iss") != [profile["issuer"]]:
        raise VerificationError(
            "Offline-access callback omitted or changed the authorization issuer."
        )
    offline_tokens = _json_request(
        profile["tokenEndpoint"],
        context,
        data={
            "grant_type": "authorization_code",
            "client_id": client["clientId"],
            "client_secret": client["clientSecret"],
            "code": offline_parameters["code"][0],
            "redirect_uri": redirect_uri,
            "code_verifier": offline_verifier,
        },
    )
    if not {"access_token", "id_token", "refresh_token"}.issubset(offline_tokens):
        raise VerificationError(
            "Offline token response did not include access, ID, and refresh tokens."
        )
    if "offline_access" not in set(offline_tokens.get("scope", "").split()):
        raise VerificationError("Offline token response did not grant offline access.")
    offline_claims = _verify_id_token(
        offline_tokens["id_token"],
        jwks,
        issuer=profile["issuer"],
        client_id=client["clientId"],
        nonce=offline_nonce,
    )
    if offline_claims.get("sub") != profile["testUsers"]["active"]["subject"]:
        raise VerificationError("Offline ID token changed the stable synthetic subject.")

    converted_state = _base64url(secrets.token_bytes(12))
    converted_url = _authorization_url(
        profile,
        session_client,
        redirect_uri,
        response_type="code",
        state=converted_state,
        nonce=_base64url(secrets.token_bytes(12)),
        prompt="none",
    )
    try:
        opener.open(
            Request(converted_url, headers={"User-Agent": VERIFIER_USER_AGENT}),
            timeout=20,
        )
        raise VerificationError(
            "Offline token exchange did not return an authorization response."
        )
    except HTTPError as error:
        converted_location = error.headers.get("Location", "")
        if error.code not in {301, 302, 303, 307, 308} or not converted_location.startswith(
            redirect_uri
        ):
            raise
        converted_parameters = parse_qs(urlparse(converted_location).query)
        if (
            converted_parameters.get("state") != [converted_state]
            or converted_parameters.get("error") != ["login_required"]
        ):
            raise VerificationError(
                "Offline token exchange did not remove the online provider session "
                f"(callback={converted_parameters!r})."
            )

    rotated_tokens = _json_request(
        profile["tokenEndpoint"],
        context,
        data={
            "grant_type": "refresh_token",
            "client_id": client["clientId"],
            "client_secret": client["clientSecret"],
            "refresh_token": offline_tokens["refresh_token"],
        },
    )
    if not {"access_token", "id_token", "refresh_token"}.issubset(rotated_tokens):
        raise VerificationError("Refresh did not return rotated access, ID, and refresh tokens.")
    if rotated_tokens["refresh_token"] == offline_tokens["refresh_token"]:
        raise VerificationError("Refresh token was not rotated.")
    refreshed_claims = _verify_id_token(
        rotated_tokens["id_token"],
        jwks,
        issuer=profile["issuer"],
        client_id=client["clientId"],
        nonce=None,
    )
    if refreshed_claims.get("sub") != profile["testUsers"]["active"]["subject"]:
        raise VerificationError("Refreshed ID token changed the stable synthetic subject.")

    revocation_request = Request(
        discovery["revocation_endpoint"],
        data=urlencode(
            {
                "client_id": client["clientId"],
                "client_secret": client["clientSecret"],
                "token": rotated_tokens["refresh_token"],
                "token_type_hint": "refresh_token",
            }
        ).encode("utf-8"),
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": VERIFIER_USER_AGENT,
        },
    )
    with urlopen(revocation_request, context=context, timeout=20) as response:
        if response.status != 200:
            raise VerificationError(
                f"Refresh-token revocation returned HTTP {response.status}; expected 200."
            )
    try:
        _json_request(
            profile["tokenEndpoint"],
            context,
            data={
                "grant_type": "refresh_token",
                "client_id": client["clientId"],
                "client_secret": client["clientSecret"],
                "refresh_token": rotated_tokens["refresh_token"],
            },
        )
        raise VerificationError("Revoked refresh token was accepted.")
    except HTTPError as error:
        error_body = json.loads(error.read() or b"{}")
        if error.code != 400 or error_body.get("error") != "invalid_grant":
            raise VerificationError("Revoked refresh token did not return invalid_grant.") from error

    logout_state = _base64url(secrets.token_bytes(12))
    logout_url = (
        f"{profile['logoutEndpoint']}?"
        + urlencode(
            {
                "client_id": client["clientId"],
                "id_token_hint": rotated_tokens["id_token"],
                "post_logout_redirect_uri": redirect_uri,
                "state": logout_state,
            }
        )
    )
    try:
        opener.open(
            Request(logout_url, headers={"User-Agent": VERIFIER_USER_AGENT}),
            timeout=20,
        )
        raise VerificationError("RP-initiated logout did not redirect to the registered URI.")
    except HTTPError as error:
        location = error.headers.get("Location", "")
        if error.code not in {301, 302, 303, 307, 308} or not location.startswith(redirect_uri):
            raise
        if parse_qs(urlparse(location).query).get("state") != [logout_state]:
            raise VerificationError("RP-initiated logout did not preserve state.")

    print(
        "[OK] Modern client: PAR, invalid-credential retry, login + consent, code + "
        "PKCE S256, signed ID token, UserInfo, prompt/max_age online-session checks, "
        "passwordless offline-access grant + session conversion, refresh "
        "rotation/revocation, and RP logout."
    )


def _verify_disabled_user(
    profile: dict[str, Any],
    context: ssl.SSLContext,
) -> None:
    client = profile["clients"]["modern"]
    redirect_uri = client["redirectUris"][0]
    verifier = _base64url(secrets.token_bytes(48))
    challenge = _base64url(hashlib.sha256(verifier.encode("ascii")).digest())
    authorization_url = _authorization_url(
        profile,
        client,
        redirect_uri,
        response_type="code",
        state=_base64url(secrets.token_bytes(12)),
        nonce=_base64url(secrets.token_bytes(12)),
        code_challenge=challenge,
    )
    opener, login_document = _open_login(context, authorization_url, redirect_uri)
    status, location, body = _submit_login(
        opener,
        login_document,
        profile["testUsers"]["disabled"]["username"],
        profile["testUsers"]["password"],
        redirect_uri,
    )
    if location and location.startswith(redirect_uri):
        raise VerificationError("Disabled user received an authorization response.")
    document = body.decode("utf-8", errors="replace")
    if status != 200 or ("alert-error" not in document and "invalid" not in document.lower()):
        raise VerificationError("Disabled user did not remain on a controlled login error.")
    print("[OK] Disabled user: authentication denied without an authorization response.")


def _verify_legacy_implicit_flow(
    profile: dict[str, Any],
    context: ssl.SSLContext,
) -> None:
    client = profile["clients"]["legacy"]
    redirect_uri = client["redirectUris"][0]
    state = _base64url(secrets.token_bytes(12))
    authorization_url = _authorization_url(
        profile,
        client,
        redirect_uri,
        response_type="id_token token",
        response_mode="form_post",
        state=state,
        nonce=_base64url(secrets.token_bytes(12)),
    )
    opener, login_document = _open_login(context, authorization_url, redirect_uri)
    status, location, body = _submit_login(
        opener,
        login_document,
        profile["testUsers"]["active"]["username"],
        profile["testUsers"]["password"],
        redirect_uri,
    )
    if location:
        raise VerificationError("Legacy form_post flow unexpectedly used a redirect response.")
    callback_form = next(
        (form for form in _forms(body) if form.action.startswith(redirect_uri)),
        None,
    )
    if status != 200 or callback_form is None:
        raise VerificationError("Legacy flow did not produce an HTML form_post callback.")
    if not {"id_token", "access_token", "state"}.issubset(callback_form.inputs):
        raise VerificationError("Legacy form_post callback omitted expected tokens or state.")
    if callback_form.inputs["state"] != state:
        raise VerificationError("Legacy form_post callback did not preserve state.")

    logout_state = _base64url(secrets.token_bytes(12))
    logout_url = (
        f"{profile['logoutEndpoint']}?"
        + urlencode(
            {
                "client_id": client["clientId"],
                "id_token_hint": callback_form.inputs["id_token"],
                "post_logout_redirect_uri": redirect_uri,
                "state": logout_state,
            }
        )
    )
    try:
        opener.open(
            Request(logout_url, headers={"User-Agent": VERIFIER_USER_AGENT}),
            timeout=20,
        )
        raise VerificationError("Legacy RP-initiated logout did not redirect.")
    except HTTPError as error:
        logout_location = error.headers.get("Location", "")
        if error.code not in {301, 302, 303, 307, 308} or not logout_location.startswith(
            redirect_uri
        ):
            raise
        if parse_qs(urlparse(logout_location).query).get("state") != [logout_state]:
            raise VerificationError("Legacy RP-initiated logout did not preserve state.")
    print("[OK] Legacy client: current id_token token + form_post login and logout work.")


def _verify_negative_protocol_cases(
    profile: dict[str, Any],
    context: ssl.SSLContext,
) -> None:
    modern = profile["clients"]["modern"]
    invalid_redirect = "https://attacker.example/callback"
    invalid_url = _authorization_url(
        profile,
        modern,
        invalid_redirect,
        response_type="code",
        state="invalid-redirect",
        nonce="invalid-redirect",
        code_challenge=_base64url(hashlib.sha256(b"verifier").digest()),
    )
    try:
        urlopen(invalid_url, context=context, timeout=20)
        raise VerificationError("Unregistered redirect URI was accepted.")
    except HTTPError as error:
        if error.headers.get("Location", "").startswith(invalid_redirect):
            raise VerificationError("Provider redirected an error to an unregistered URI.")
        if error.code != 400:
            raise VerificationError(f"Invalid redirect returned HTTP {error.code}, expected 400.")

    implicit_url = _authorization_url(
        profile,
        modern,
        modern["redirectUris"][0],
        response_type="id_token token",
        response_mode="form_post",
        state="modern-implicit",
        nonce="modern-implicit",
    )
    try:
        response = urlopen(implicit_url, context=context, timeout=20)
        document = response.read().decode("utf-8", errors="replace")
        if "login-actions/authenticate" in document:
            raise VerificationError("Modern client accepted an implicit authorization request.")
    except HTTPError as error:
        if error.code not in {400, 403}:
            raise
    print("[OK] Negative protocol: unregistered redirects and modern implicit flow are rejected.")


def verify(connection_path: Path, ca_path: Path, suite: str = "all") -> None:
    profile = json.loads(connection_path.read_text(encoding="utf-8"))
    context = ssl.create_default_context(cafile=str(ca_path))

    if suite == "saml":
        if "saml" not in profile["clients"]:
            raise VerificationError("The Standard SAML profile is disabled.")
        _verify_saml(profile, context)
        return

    discovery = _json_request(profile["discoveryEndpoint"], context)
    if discovery.get("issuer") != profile["issuer"]:
        raise VerificationError("Discovery issuer did not match the connection profile.")
    for endpoint in (
        "authorization_endpoint",
        "token_endpoint",
        "userinfo_endpoint",
        "jwks_uri",
        "end_session_endpoint",
        "revocation_endpoint",
        "pushed_authorization_request_endpoint",
    ):
        if not discovery.get(endpoint):
            raise VerificationError(f"Discovery omitted {endpoint}.")
    expected_scopes = {"openid", "profile", "email", "offline_access", "northlake"}
    if not expected_scopes.issubset(discovery.get("scopes_supported", [])):
        raise VerificationError("Discovery omitted a required realistic-profile scope.")
    if not {"none", "login", "consent"}.issubset(
        discovery.get("prompt_values_supported", [])
    ):
        raise VerificationError("Discovery omitted required OIDC prompt values.")
    if "S256" not in discovery.get("code_challenge_methods_supported", []):
        raise VerificationError("Discovery did not advertise PKCE S256.")
    if "refresh_token" not in discovery.get("grant_types_supported", []):
        raise VerificationError("Discovery did not advertise the refresh-token grant.")
    if "1" not in discovery.get("acr_values_supported", []):
        raise VerificationError("Discovery did not advertise the selected ACR value.")
    if discovery.get("authorization_response_iss_parameter_supported") is not True:
        raise VerificationError("Discovery did not advertise authorization-response issuer binding.")
    jwks = _json_request(discovery["jwks_uri"], context)
    if not jwks.get("keys"):
        raise VerificationError("JWKS did not contain signing keys.")
    print(
        "[OK] HTTPS discovery, stable issuer, JWKS, UserInfo, scopes, prompts, "
        "refresh/revocation, logout, and PAR metadata."
    )

    _verify_admin(profile, context)
    if "modern" in profile["clients"]:
        _verify_negative_protocol_cases(profile, context)
        _verify_modern_code_flow(profile, context, discovery, jwks)
        _verify_disabled_user(profile, context)
        _verify_legacy_implicit_flow(profile, context)
    else:
        print("[OK] OIDC client flows are disabled by the local provider configuration.")
    if "saml" in profile["clients"]:
        _verify_saml(profile, context)
    else:
        print("[OK] Standard SAML client flow is disabled by the local provider configuration.")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify the live Northlake identity provider.")
    parser.add_argument("--connection", required=True, type=Path)
    parser.add_argument("--ca-file", required=True, type=Path)
    parser.add_argument(
        "--suite",
        choices=("all", "saml"),
        default="all",
        help="Run the complete provider verifier or only the focused SAML suite.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        verify(args.connection.resolve(), args.ca_file.resolve(), args.suite)
    except (OSError, HTTPError, URLError, VerificationError, KeyError, json.JSONDecodeError) as error:
        print(f"[ERROR] {error}", file=sys.stderr)
        return 1
    print(f"[OK] Northlake synthetic identity {args.suite} verification completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
