const form = document.querySelector("#scenario-form");
const workspace = document.querySelector("#workspace");
const loadError = document.querySelector("#load-error");
const formError = document.querySelector("#form-error");
const statusBadge = document.querySelector("#status-badge");
const operationStatus = document.querySelector("#operation-status");
const verificationTime = document.querySelector("#verification-time");
const verificationOutput = document.querySelector("#verification-output");
const diffOutput = document.querySelector("#diff-output");
const exportOutput = document.querySelector("#export-output");
const advancedJson = document.querySelector("#advanced-json");
const presetControl = document.querySelector("#preset");
const previewButton = document.querySelector("#preview-button");
const saveButton = document.querySelector("#save-button");
const applyButton = document.querySelector("#apply-button");
const verifyButton = document.querySelector("#verify-button");
const copyButton = document.querySelector("#copy-button");
const usePresetButton = document.querySelector("#use-preset-button");
const useJsonButton = document.querySelector("#use-json-button");

const slots = ["labA", "labB"];
const listFields = new Set([
  "oidcRedirectUris",
  "oidcPostLogoutRedirectUris",
  "samlAssertionConsumerServiceUrls",
  "samlLogoutServiceUrls",
]);
const realmFieldDefinitions = [
  ["realmKey", "Realm key", "text"],
  ["displayName", "Display name", "text"],
  ["claimShape", "Claim shape", "claimShape"],
  ["oidcProviderKey", "OIDC provider key", "text"],
  ["oidcClientId", "OIDC client ID", "text"],
  ["oidcConfigurationMode", "OIDC configuration mode", "configurationMode"],
  ["oidcParBehavior", "OIDC PAR behavior", "parBehavior"],
  ["oidcRedirectUris", "OIDC redirect URIs · one per line", "list"],
  ["oidcPostLogoutRedirectUris", "OIDC post-logout URIs · one per line", "list"],
  ["samlProviderKey", "SAML provider key", "text"],
  ["samlEntityId", "SAML SP entity ID", "text"],
  ["samlAssertionConsumerServiceUrls", "SAML ACS URLs · one per line", "list"],
  ["samlLogoutServiceUrls", "SAML logout URLs · one per line", "list"],
];
let presets = {};

function optionsFor(kind) {
  if (kind === "claimShape") return [["Full", "Full"], ["IdentityOnly", "Identity only"], ["Minimal", "Minimal"]];
  if (kind === "configurationMode") return [["Discovery", "Discovery"], ["Authority", "Authority"], ["Static", "Static endpoints"]];
  if (kind === "parBehavior") return [["Require", "Require PAR"], ["UseIfAvailable", "Use if available"], ["Disable", "Disable"]];
  return [];
}

function buildRealmEditors() {
  for (const slot of slots) {
    const container = document.querySelector(`[data-slot="${slot}"] .realm-fields`);
    for (const [key, label, kind] of realmFieldDefinitions) {
      const wrapper = document.createElement("div");
      wrapper.className = `field${kind === "list" ? " field-wide" : ""}`;
      const id = `${slot}-${key}`;
      const labelElement = document.createElement("label");
      labelElement.htmlFor = id;
      labelElement.textContent = label;
      let control;
      if (["claimShape", "configurationMode", "parBehavior"].includes(kind)) {
        control = document.createElement("select");
        for (const [value, text] of optionsFor(kind)) {
          const option = document.createElement("option");
          option.value = value;
          option.textContent = text;
          control.append(option);
        }
      } else if (kind === "list") {
        control = document.createElement("textarea");
      } else {
        control = document.createElement("input");
        control.spellcheck = false;
      }
      control.id = id;
      const error = document.createElement("p");
      error.className = "field-error";
      error.id = `error-realms.${slot}.${key}`;
      error.hidden = true;
      wrapper.append(labelElement, control, error);
      container.append(wrapper);
    }
  }
}

function setValues(values, updateJson = true) {
  document.querySelector("#scenarioName").value = values.scenarioName ?? "";
  presetControl.value = values.preset ?? "SharedSubject";
  document.querySelector("#publicBaseUrl").value = values.publicBaseUrl ?? "";
  document.querySelector("#applicationHomeUrl").value = values.applicationHomeUrl ?? "";
  document.querySelector("#sharedExternalSubject").checked = Boolean(values.sharedExternalSubject);
  for (const slot of slots) {
    for (const [key] of realmFieldDefinitions) {
      const control = document.querySelector(`#${slot}-${key}`);
      const value = values.realms?.[slot]?.[key];
      control.value = listFields.has(key) && Array.isArray(value) ? value.join("\n") : value ?? "";
    }
    document.querySelector(`[data-slot="${slot}"] h2`).textContent = values.realms?.[slot]?.realmKey || slot;
  }
  if (updateJson) advancedJson.value = JSON.stringify(values, null, 2);
}

function collectValues() {
  const values = {
    scenarioName: document.querySelector("#scenarioName").value,
    preset: presetControl.value,
    publicBaseUrl: document.querySelector("#publicBaseUrl").value,
    applicationHomeUrl: document.querySelector("#applicationHomeUrl").value,
    sharedExternalSubject: document.querySelector("#sharedExternalSubject").checked,
    realms: {},
  };
  for (const slot of slots) {
    const realm = {};
    for (const [key] of realmFieldDefinitions) {
      const value = document.querySelector(`#${slot}-${key}`).value;
      realm[key] = listFields.has(key)
        ? value.split(/\r?\n/).map((item) => item.trim()).filter(Boolean)
        : value;
    }
    values.realms[slot] = realm;
  }
  return values;
}

function controlForError(path) {
  if (path.startsWith("realms.")) {
    const [, slot, key] = path.split(".");
    return document.querySelector(`#${slot}-${key}`);
  }
  return document.querySelector(`#${path}`);
}

function clearErrors() {
  formError.hidden = true;
  formError.textContent = "";
  document.querySelectorAll(".field-error").forEach((error) => { error.hidden = true; error.textContent = ""; });
  document.querySelectorAll("[aria-invalid='true']").forEach((control) => {
    control.removeAttribute("aria-invalid");
    control.removeAttribute("aria-describedby");
  });
}

function showErrors(errors) {
  clearErrors();
  for (const [path, message] of Object.entries(errors || {})) {
    if (path === "_form" || path === "realms") {
      formError.textContent = message;
      formError.hidden = false;
      continue;
    }
    const control = controlForError(path);
    const error = document.getElementById(`error-${path}`);
    if (!control || !error) {
      formError.textContent = message;
      formError.hidden = false;
      continue;
    }
    control.setAttribute("aria-invalid", "true");
    control.setAttribute("aria-describedby", error.id);
    error.textContent = message;
    error.hidden = false;
  }
}

function renderVerification(verification) {
  if (!verification) {
    verificationTime.textContent = "Not run for these realms yet.";
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

function renderDiff(differences) {
  diffOutput.replaceChildren();
  if (!differences?.length) {
    diffOutput.textContent = "No unsaved differences.";
    return;
  }
  const list = document.createElement("ul");
  for (const difference of differences) {
    const item = document.createElement("li");
    const path = document.createElement("code");
    path.textContent = difference.path;
    const detail = document.createElement("span");
    detail.textContent = ` ${JSON.stringify(difference.before)} → ${JSON.stringify(difference.after)}`;
    item.append(path, detail);
    list.append(item);
  }
  diffOutput.append(list);
}

function render(payload, updateForm = true) {
  if (updateForm && payload.values) setValues(payload.values);
  if (payload.preview) {
    document.querySelector("#summary-labA").textContent = payload.preview.realms.labA.issuer;
    document.querySelector("#summary-labB").textContent = payload.preview.realms.labB.issuer;
    document.querySelector("#summary-subject").textContent = payload.preview.expectedSubjectRelationship;
  }
  if (payload.export) exportOutput.textContent = JSON.stringify(payload.export, null, 2);
  renderDiff(payload.diff || []);
  if (Object.hasOwn(payload, "verification")) renderVerification(payload.verification);
}

function setBusy(busy) {
  for (const button of document.querySelectorAll("button")) button.disabled = busy;
}

async function send(path, values = collectValues()) {
  clearErrors();
  setBusy(true);
  operationStatus.textContent = path.includes("apply") || path.includes("reset")
    ? "Replacing disposable lab realms and running isolation checks…"
    : path.includes("verify") ? "Running the two-realm verifier…" : "Validating the bounded scenario…";
  try {
    const response = await fetch(`/configure/api/scenarios/${path}`, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({values}),
    });
    const payload = await response.json();
    if (!response.ok) {
      showErrors(payload.errors || {_form: payload.message || "Scenario operation failed."});
      operationStatus.textContent = payload.applyError || payload.detail || payload.message;
      statusBadge.textContent = response.status === 400 ? "Check values" : "Apply error";
      statusBadge.className = "status-badge error";
      return null;
    }
    render(payload, Boolean(payload.values));
    if (payload.verification) renderVerification(payload.verification);
    operationStatus.textContent = payload.message || "Scenario operation completed.";
    if (path === "preview") statusBadge.textContent = "Preview";
    if (path === "save") { statusBadge.textContent = "Saved"; renderVerification(null); }
    return payload;
  } catch (failure) {
    formError.textContent = `Configuration service is unavailable: ${failure.message}`;
    formError.hidden = false;
    statusBadge.textContent = "Unavailable";
    statusBadge.className = "status-badge error";
    operationStatus.textContent = "The request did not reach the local configuration service.";
    return null;
  } finally {
    setBusy(false);
  }
}

previewButton.addEventListener("click", () => send("preview"));
saveButton.addEventListener("click", () => send("save"));
verifyButton.addEventListener("click", () => send("verify"));
form.addEventListener("submit", (event) => { event.preventDefault(); send("apply"); });
usePresetButton.addEventListener("click", () => {
  const selected = presets[presetControl.value];
  if (selected) { setValues(selected); operationStatus.textContent = "Preset loaded into the form; preview or apply when ready."; }
});
useJsonButton.addEventListener("click", () => {
  clearErrors();
  try {
    const values = JSON.parse(advancedJson.value);
    setValues(values, false);
    send("preview", values);
  } catch (failure) {
    const error = document.querySelector("#error-advanced-json");
    error.textContent = `JSON could not be parsed: ${failure.message}`;
    error.hidden = false;
    advancedJson.setAttribute("aria-invalid", "true");
    advancedJson.setAttribute("aria-describedby", error.id);
  }
});
for (const button of document.querySelectorAll(".clone-button")) {
  button.addEventListener("click", () => send(`clone/${button.dataset.source}/${button.dataset.target}`));
}
for (const button of document.querySelectorAll(".reset-button")) {
  button.addEventListener("click", () => send(`reset/${button.dataset.slot}`));
}
copyButton.addEventListener("click", async () => {
  await navigator.clipboard.writeText(exportOutput.textContent);
  copyButton.textContent = "Copied";
  window.setTimeout(() => { copyButton.textContent = "Copy"; }, 1400);
});

async function load() {
  try {
    const response = await fetch("/configure/api/scenarios", {cache: "no-store"});
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || payload.message || "Unable to load scenarios.");
    presets = payload.presets;
    render(payload);
    renderVerification(payload.lastVerification);
    workspace.hidden = false;
  } catch (failure) {
    loadError.textContent = `Unable to load concurrent scenarios: ${failure.message}`;
    loadError.hidden = false;
  }
}

buildRealmEditors();
load();
