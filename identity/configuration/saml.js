const form = document.querySelector("#saml-form");
const workspace = document.querySelector("#workspace");
const loadError = document.querySelector("#load-error");
const formError = document.querySelector("#form-error");
const jsonPreview = document.querySelector("#json-preview");
const operationStatus = document.querySelector("#operation-status");
const statusBadge = document.querySelector("#status-badge");
const verificationOutput = document.querySelector("#verification-output");
const verificationTime = document.querySelector("#verification-time");
const certificateInput = document.querySelector("#saml2IntCertificate");
const previewButton = document.querySelector("#preview-button");
const saveButton = document.querySelector("#save-button");
const applyButton = document.querySelector("#apply-button");
const verifyButton = document.querySelector("#verify-button");
const copyButton = document.querySelector("#copy-button");

const profilePrefixes = ["standard", "saml2Int"];
const suffixes = [
  "Enabled",
  "ProviderKey",
  "EntityId",
  "AssertionConsumerServiceUrls",
  "LogoutServiceUrls",
  "SubjectBindingKind",
  "SubjectAttribute",
  "AllowedClaims",
  "AllowedAuthenticationContextClassReferences",
  "AllowUnsolicitedResponses",
  "EnableSingleLogout",
];
const fieldNames = profilePrefixes.flatMap((prefix) => suffixes.map((suffix) => `${prefix}${suffix}`));
const checkboxSuffixes = new Set(["Enabled", "AllowUnsolicitedResponses", "EnableSingleLogout"]);
const listSuffixes = new Set([
  "AssertionConsumerServiceUrls",
  "LogoutServiceUrls",
  "AllowedClaims",
  "AllowedAuthenticationContextClassReferences",
]);

function suffixFor(name) {
  return suffixes.find((suffix) => name.endsWith(suffix));
}

function setValues(values) {
  for (const name of fieldNames) {
    const control = document.querySelector(`#${name}`);
    const suffix = suffixFor(name);
    const value = values[name];
    if (checkboxSuffixes.has(suffix)) {
      control.checked = Boolean(value);
    } else if (listSuffixes.has(suffix)) {
      control.value = Array.isArray(value) ? value.join("\n") : "";
    } else {
      control.value = value ?? "";
    }
  }
}

async function collectValues(includeCertificate = true) {
  const values = {};
  for (const name of fieldNames) {
    const control = document.querySelector(`#${name}`);
    const suffix = suffixFor(name);
    if (checkboxSuffixes.has(suffix)) {
      values[name] = control.checked;
    } else if (listSuffixes.has(suffix)) {
      values[name] = control.value.split(/\r?\n/).map((value) => value.trim()).filter(Boolean);
    } else {
      values[name] = control.value;
    }
  }
  const file = includeCertificate ? certificateInput.files[0] : null;
  if (file) {
    const bytes = new Uint8Array(await file.arrayBuffer());
    let binary = "";
    for (let offset = 0; offset < bytes.length; offset += 8192) {
      binary += String.fromCharCode(...bytes.subarray(offset, offset + 8192));
    }
    values.saml2IntCertificateBase64 = btoa(binary);
    values.saml2IntCertificateName = file.name;
  }
  return values;
}

function clearErrors() {
  formError.hidden = true;
  formError.textContent = "";
  for (const name of [...fieldNames, "saml2IntCertificateBase64"]) {
    const control = document.querySelector(name === "saml2IntCertificateBase64" ? "#saml2IntCertificate" : `#${name}`);
    const error = document.querySelector(`#error-${name}`);
    control?.removeAttribute("aria-invalid");
    control?.removeAttribute("aria-describedby");
    if (error) {
      error.hidden = true;
      error.textContent = "";
    }
  }
}

function showErrors(errors) {
  clearErrors();
  for (const [name, message] of Object.entries(errors || {})) {
    if (name === "_form") {
      formError.textContent = message;
      formError.hidden = false;
      continue;
    }
    const control = document.querySelector(name === "saml2IntCertificateBase64" ? "#saml2IntCertificate" : `#${name}`);
    const error = document.querySelector(`#error-${name}`);
    if (!control || !error) continue;
    control.setAttribute("aria-invalid", "true");
    control.setAttribute("aria-describedby", error.id);
    error.textContent = message;
    error.hidden = false;
  }
}

function renderPreview(preview, certificate) {
  jsonPreview.textContent = JSON.stringify(preview, null, 2);
  document.querySelector("#summary-standard").textContent = preview.profiles.standard ? "Enabled" : "Disabled";
  document.querySelector("#summary-saml2int").textContent = preview.profiles.saml2Int ? "Enabled" : "Disabled";
  document.querySelector("#summary-certificate").textContent = certificate?.configured
    ? `${certificate.keyType} ${certificate.keySize} · ${certificate.sha256Thumbprint.slice(0, 12)}…`
    : "Not configured";
}

function renderVerification(verification) {
  if (!verification) {
    verificationTime.textContent = "Not run from this configuration yet.";
    verificationOutput.textContent = "No verification result.";
    return;
  }
  verificationTime.textContent = verification.checkedAtUtc
    ? `Checked ${new Date(verification.checkedAtUtc).toLocaleString()} · ${verification.classification}`
    : verification.classification;
  verificationOutput.textContent = verification.output || "Verifier returned no output.";
  statusBadge.textContent = verification.passed ? "Provider ready" : "Break found";
  statusBadge.className = verification.passed ? "status-badge" : "status-badge error";
}

function setBusy(busy) {
  for (const button of [previewButton, saveButton, applyButton, verifyButton]) button.disabled = busy;
}

async function send(action) {
  clearErrors();
  setBusy(true);
  operationStatus.textContent = action === "apply"
    ? "Applying profiles and running provider-side SAML checks…"
    : action === "verify"
      ? "Running the focused verifier against the current realm…"
      : action === "save"
        ? "Saving SAML profiles…"
        : "Refreshing the ready-to-copy values…";
  try {
    const response = await fetch(`/configure/api/saml/${action}`, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({values: await collectValues(action !== "verify")}),
    });
    const payload = await response.json();
    if (!response.ok) {
      showErrors(payload.errors || {_form: payload.message || "SAML operation failed."});
      operationStatus.textContent = payload.applyError || payload.detail || payload.message;
      statusBadge.textContent = response.status === 400 ? "Check values" : "Apply error";
      statusBadge.className = "status-badge error";
      return;
    }
    if (payload.preview) renderPreview(payload.preview, payload.certificate);
    if (payload.verification) renderVerification(payload.verification);
    operationStatus.textContent = payload.message || "SAML operation completed.";
    if (action === "preview") statusBadge.textContent = "Preview";
    if (action === "save") {
      renderVerification(null);
      statusBadge.textContent = "Saved";
      certificateInput.value = "";
    }
    if (action === "apply") certificateInput.value = "";
  } catch (failure) {
    formError.textContent = `Configuration service is unavailable: ${failure.message}`;
    formError.hidden = false;
    statusBadge.textContent = "Unavailable";
    statusBadge.className = "status-badge error";
    operationStatus.textContent = "The request did not reach the local configuration service.";
  } finally {
    setBusy(false);
  }
}

previewButton.addEventListener("click", () => send("preview"));
saveButton.addEventListener("click", () => send("save"));
verifyButton.addEventListener("click", () => send("verify"));
form.addEventListener("submit", (event) => { event.preventDefault(); send("apply"); });
copyButton.addEventListener("click", async () => {
  await navigator.clipboard.writeText(jsonPreview.textContent);
  copyButton.textContent = "Copied";
  window.setTimeout(() => { copyButton.textContent = "Copy"; }, 1400);
});

async function load() {
  try {
    const response = await fetch("/configure/api/saml", {cache: "no-store"});
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || payload.message || "Unable to load SAML state.");
    setValues(payload.values);
    renderPreview(payload.preview, payload.certificate);
    renderVerification(payload.lastVerification);
    workspace.hidden = false;
  } catch (failure) {
    loadError.textContent = `Unable to load SAML configuration: ${failure.message}`;
    loadError.hidden = false;
  }
}

load();
