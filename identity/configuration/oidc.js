const form = document.querySelector("#oidc-form");
const workspace = document.querySelector("#workspace");
const loadError = document.querySelector("#load-error");
const formError = document.querySelector("#form-error");
const jsonPreview = document.querySelector("#json-preview");
const operationStatus = document.querySelector("#operation-status");
const statusBadge = document.querySelector("#status-badge");
const verificationOutput = document.querySelector("#verification-output");
const verificationTime = document.querySelector("#verification-time");
const previewButton = document.querySelector("#preview-button");
const saveButton = document.querySelector("#save-button");
const applyButton = document.querySelector("#apply-button");
const verifyButton = document.querySelector("#verify-button");
const copyButton = document.querySelector("#copy-button");

const fieldNames = [
  "configurationMode",
  "parBehavior",
  "tokenEndpointAuthMethod",
  "accessTokenLifetimeSeconds",
  "modernClientId",
  "modernRedirectUris",
  "modernPostLogoutRedirectUris",
  "modernScopes",
  "modernConsentRequired",
  "legacyEnabled",
  "legacyClientId",
  "legacyRedirectUris",
  "legacyPostLogoutRedirectUris",
  "legacyScopes",
];

const listFields = new Set([
  "modernRedirectUris",
  "modernPostLogoutRedirectUris",
  "legacyRedirectUris",
  "legacyPostLogoutRedirectUris",
]);
const scopeFields = new Set(["modernScopes", "legacyScopes"]);
const checkboxFields = new Set(["modernConsentRequired", "legacyEnabled"]);

function setValues(values) {
  for (const name of fieldNames) {
    const control = document.querySelector(`#${name}`);
    const value = values[name];
    if (checkboxFields.has(name)) {
      control.checked = Boolean(value);
    } else if (listFields.has(name)) {
      control.value = Array.isArray(value) ? value.join("\n") : "";
    } else if (scopeFields.has(name)) {
      control.value = Array.isArray(value) ? value.join(" ") : value || "";
    } else {
      control.value = value ?? "";
    }
  }
}

function collectValues() {
  const values = {};
  for (const name of fieldNames) {
    const control = document.querySelector(`#${name}`);
    if (checkboxFields.has(name)) {
      values[name] = control.checked;
    } else if (listFields.has(name)) {
      values[name] = control.value
        .split(/\r?\n/)
        .map((value) => value.trim())
        .filter(Boolean);
    } else if (scopeFields.has(name)) {
      values[name] = control.value
        .split(/\s+/)
        .map((value) => value.trim())
        .filter(Boolean);
    } else if (name === "accessTokenLifetimeSeconds") {
      values[name] = Number(control.value);
    } else {
      values[name] = control.value;
    }
  }
  return values;
}

function clearErrors() {
  formError.hidden = true;
  formError.textContent = "";
  for (const name of fieldNames) {
    const control = document.querySelector(`#${name}`);
    const error = document.querySelector(`#error-${name}`);
    control.removeAttribute("aria-invalid");
    control.removeAttribute("aria-describedby");
    error.hidden = true;
    error.textContent = "";
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
    const control = document.querySelector(`#${name}`);
    const error = document.querySelector(`#error-${name}`);
    if (!control || !error) {
      continue;
    }
    control.setAttribute("aria-invalid", "true");
    control.setAttribute("aria-describedby", error.id);
    error.textContent = message;
    error.hidden = false;
  }
}

function renderPreview(preview) {
  jsonPreview.textContent = JSON.stringify(preview, null, 2);
  document.querySelector("#summary-mode").textContent = preview.configurationMode;
  document.querySelector("#summary-par").textContent = preview.parBehavior;
  document.querySelector("#summary-auth").textContent = preview.tokenEndpointAuthMethod;
  document.querySelector("#summary-legacy").textContent = preview.profiles.historicalLegacy
    ? "Historical enabled"
    : "Disabled";
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
  statusBadge.textContent = verification.passed ? "Verified" : "Break found";
  statusBadge.className = verification.passed ? "status-badge" : "status-badge error";
}

function setBusy(busy) {
  previewButton.disabled = busy;
  saveButton.disabled = busy;
  applyButton.disabled = busy;
  verifyButton.disabled = busy;
}

async function send(action) {
  clearErrors();
  setBusy(true);
  operationStatus.textContent = action === "apply"
    ? "Applying profiles and running the focused verifier…"
    : action === "verify"
      ? "Running the focused verifier against the current realm…"
      : action === "save"
        ? "Saving OIDC profiles…"
        : "Refreshing the ready-to-copy values…";
  try {
    const response = await fetch(`/configure/api/oidc/${action}`, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({values: collectValues()}),
    });
    const payload = await response.json();
    if (!response.ok) {
      showErrors(payload.errors || {_form: payload.message || "OIDC operation failed."});
      operationStatus.textContent = payload.applyError || payload.detail || payload.message;
      statusBadge.textContent = response.status === 400 ? "Check values" : "Apply error";
      statusBadge.className = "status-badge error";
      if (payload.preview) {
        renderPreview(payload.preview);
      }
      if (action === "apply") {
        renderVerification(null);
      }
      return;
    }
    if (payload.preview) {
      renderPreview(payload.preview);
    }
    if (payload.verification) {
      renderVerification(payload.verification);
    }
    operationStatus.textContent = payload.message || "OIDC operation completed.";
    if (action === "preview") {
      statusBadge.textContent = "Preview";
      statusBadge.className = "status-badge";
    } else if (action === "save") {
      renderVerification(null);
      statusBadge.textContent = "Saved";
      statusBadge.className = "status-badge";
    } else if (action === "apply" && !payload.verification?.passed) {
      statusBadge.textContent = "Break found";
      statusBadge.className = "status-badge error";
    }
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
form.addEventListener("submit", (event) => {
  event.preventDefault();
  send("apply");
});
copyButton.addEventListener("click", async () => {
  await navigator.clipboard.writeText(jsonPreview.textContent);
  copyButton.textContent = "Copied";
  window.setTimeout(() => { copyButton.textContent = "Copy"; }, 1400);
});

async function load() {
  try {
    const response = await fetch("/configure/api/oidc", {cache: "no-store"});
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || payload.message || "Unable to load OIDC state.");
    }
    setValues(payload.values);
    renderPreview(payload.preview);
    renderVerification(payload.lastVerification);
    workspace.hidden = false;
  } catch (failure) {
    loadError.textContent = `Unable to load OIDC configuration: ${failure.message}`;
    loadError.hidden = false;
  }
}

load();
