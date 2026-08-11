"use strict";

const workspace = document.querySelector("#workspace");
const loadError = document.querySelector("#load-error");
const form = document.querySelector("#scim-form");
const formError = document.querySelector("#form-error");
const selectedConnection = document.querySelector("#selectedConnectionKey");
const credential = document.querySelector("#credential");
const credentialHelp = document.querySelector("#credential-help");
const connectionsJson = document.querySelector("#connectionsJson");
const syntheticUser = document.querySelector("#syntheticUserId");
const groupBinding = document.querySelector("#groupBindingKey");
const saveButton = document.querySelector("#save-button");
const formatButton = document.querySelector("#format-button");
const verifyButton = document.querySelector("#verify-button");
const lifecycleButton = document.querySelector("#lifecycle-button");
const deactivateButton = document.querySelector("#deactivate-button");
const reactivateButton = document.querySelector("#reactivate-button");
const copyButton = document.querySelector("#copy-button");
const statusBadge = document.querySelector("#status-badge");
const operationStatus = document.querySelector("#operation-status");
const verificationTime = document.querySelector("#verification-time");
const verificationOutput = document.querySelector("#verification-output");
const lifecycleTime = document.querySelector("#lifecycle-time");
const lifecycleOutput = document.querySelector("#lifecycle-output");
const jsonPreview = document.querySelector("#json-preview");

let credentialStatus = {};
let fixtureUsers = [];
let fixtureBindings = [];

function clearErrors() {
  formError.hidden = true;
  formError.textContent = "";
  for (const name of ["selectedConnectionKey", "credential", "connections", "syntheticUserId", "groupBindingKey"]) {
    const error = document.querySelector(`#error-${name}`);
    if (error) {
      error.hidden = true;
      error.textContent = "";
    }
  }
}

function showErrors(errors) {
  clearErrors();
  for (const [name, message] of Object.entries(errors || {})) {
    if (name === "_form" || name.startsWith("connections[")) {
      formError.textContent = message;
      formError.hidden = false;
      continue;
    }
    const normalized = name === "connections.groupBindings" ? "connections" : name;
    const error = document.querySelector(`#error-${normalized}`);
    if (error) {
      error.textContent = message;
      error.hidden = false;
    } else {
      formError.textContent = message;
      formError.hidden = false;
    }
  }
}

function parseConnections() {
  let parsed;
  try {
    parsed = JSON.parse(connectionsJson.value);
  } catch (failure) {
    throw new Error(`Connections JSON is invalid: ${failure.message}`);
  }
  if (!Array.isArray(parsed)) {
    throw new Error("Connections JSON must be an array.");
  }
  return parsed;
}

function updateConnectionOptions(connections, selectedKey) {
  selectedConnection.replaceChildren();
  for (const connection of connections) {
    if (!connection || typeof connection.connectionKey !== "string") {
      continue;
    }
    const option = document.createElement("option");
    option.value = connection.connectionKey;
    option.textContent = `${connection.displayName || connection.connectionKey} · ${connection.connectionKey}`;
    selectedConnection.append(option);
  }
  if (selectedKey && [...selectedConnection.options].some((option) => option.value === selectedKey)) {
    selectedConnection.value = selectedKey;
  }
  updateSelectedConnection();
}

function updateSelectedConnection() {
  const key = selectedConnection.value;
  const configured = Boolean(credentialStatus[key]);
  document.querySelector("#summary-connection").textContent = key || "—";
  document.querySelector("#summary-credential").textContent = configured ? "Stored locally" : "Not configured";
  credentialHelp.textContent = configured
    ? "A credential is stored for this connection. Leave blank to retain it."
    : "No credential is stored for this connection. Paste the one-time value before testing.";
  const applicable = fixtureBindings.filter((binding) => binding.connectionKey === key);
  const previous = groupBinding.value;
  groupBinding.replaceChildren();
  const none = document.createElement("option");
  none.value = "";
  none.textContent = "User only · no Group operations";
  groupBinding.append(none);
  for (const binding of applicable) {
    const option = document.createElement("option");
    option.value = binding.bindingKey;
    option.textContent = `${binding.displayName} · ${binding.bindingKey}${binding.syntheticGroupAvailable ? "" : " · missing fixture group"}`;
    option.disabled = !binding.syntheticGroupAvailable;
    groupBinding.append(option);
  }
  if (previous && [...groupBinding.options].some((option) => option.value === previous && !option.disabled)) {
    groupBinding.value = previous;
  } else if (applicable.some((binding) => binding.syntheticGroupAvailable)) {
    groupBinding.value = applicable.find((binding) => binding.syntheticGroupAvailable).bindingKey;
  }
}

function collectSettings() {
  return {
    selectedConnectionKey: selectedConnection.value,
    connections: parseConnections(),
    credential: credential.value,
  };
}

function renderPreview(preview) {
  jsonPreview.textContent = JSON.stringify(preview, null, 2);
}

function renderVerification(result) {
  if (!result) {
    verificationTime.textContent = "Not run.";
    verificationOutput.textContent = "No discovery evidence.";
    return;
  }
  verificationTime.textContent = result.checkedAtUtc
    ? `Checked ${new Date(result.checkedAtUtc).toLocaleString()} · ${result.classification}`
    : result.classification;
  verificationOutput.textContent = JSON.stringify(result, null, 2);
}

function renderLifecycle(result) {
  if (!result) {
    lifecycleTime.textContent = "Not run.";
    lifecycleOutput.textContent = "No lifecycle evidence.";
    deactivateButton.disabled = true;
    reactivateButton.disabled = true;
    return;
  }
  lifecycleTime.textContent = result.checkedAtUtc
    ? `Checked ${new Date(result.checkedAtUtc).toLocaleString()} · ${result.classification}`
    : result.classification;
  lifecycleOutput.textContent = JSON.stringify(result, null, 2);
  const hasResource = Boolean(result.userResourceId);
  deactivateButton.disabled = !hasResource || result.active === false;
  reactivateButton.disabled = !hasResource || result.active === true || result.finalState?.userActive === true;
}

function populateFixtures(users) {
  fixtureUsers = users;
  syntheticUser.replaceChildren();
  for (const user of users) {
    const option = document.createElement("option");
    option.value = user.syntheticUserId;
    option.textContent = `${user.displayName} · ${user.username}${user.enabled ? "" : " · disabled"}`;
    option.disabled = !user.enabled;
    syntheticUser.append(option);
  }
  const preferred = users.find((user) => user.syntheticUserId === "samantha.ireland" && user.enabled)
    || users.find((user) => user.enabled);
  if (preferred) {
    syntheticUser.value = preferred.syntheticUserId;
  }
}

function setBusy(busy) {
  saveButton.disabled = busy;
  formatButton.disabled = busy;
  verifyButton.disabled = busy;
  lifecycleButton.disabled = busy;
  if (busy) {
    deactivateButton.disabled = true;
    reactivateButton.disabled = true;
  }
}

async function post(action, values) {
  clearErrors();
  setBusy(true);
  operationStatus.textContent = action === "save"
    ? "Saving the ignored local SCIM configuration…"
    : action === "verify"
      ? "Reading authenticated SCIM discovery endpoints…"
      : action === "lifecycle"
        ? "Running the bounded User and Group lifecycle…"
        : action === "deactivate"
          ? "Deactivating the provisioned User for the denial checkpoint…"
          : "Reactivating the provisioned User…";
  try {
    const response = await fetch(`/configure/api/scim/${action}`, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({values}),
    });
    const payload = await response.json();
    if (!response.ok) {
      showErrors(payload.errors || {_form: payload.message || "SCIM operation failed."});
      operationStatus.textContent = payload.detail || payload.message || "SCIM operation failed.";
      statusBadge.textContent = response.status === 400 ? "Check values" : "Unavailable";
      statusBadge.className = "status-badge error";
      return;
    }
    if (payload.values) {
      connectionsJson.value = JSON.stringify(payload.values.connections, null, 2);
      credentialStatus = payload.credentialStatus || credentialStatus;
      updateConnectionOptions(payload.values.connections, payload.values.selectedConnectionKey);
      credential.value = "";
    }
    if (payload.preview) {
      renderPreview(payload.preview);
    }
    if (payload.verification) {
      renderVerification(payload.verification);
      statusBadge.textContent = payload.verification.passed ? "Discovered" : "Break found";
      statusBadge.className = payload.verification.passed ? "status-badge" : "status-badge error";
    } else if (payload.lifecycle) {
      renderLifecycle(payload.lifecycle);
      statusBadge.textContent = payload.lifecycle.passed ? "Lifecycle ready" : "Break found";
      statusBadge.className = payload.lifecycle.passed ? "status-badge" : "status-badge error";
    } else {
      renderVerification(null);
      renderLifecycle(null);
      statusBadge.textContent = "Saved";
      statusBadge.className = "status-badge";
    }
    operationStatus.textContent = payload.message || "SCIM operation completed.";
  } catch (failure) {
    formError.textContent = `Configuration service is unavailable: ${failure.message}`;
    formError.hidden = false;
    operationStatus.textContent = "The request did not reach the local configuration service.";
    statusBadge.textContent = "Unavailable";
    statusBadge.className = "status-badge error";
  } finally {
    setBusy(false);
    const lastLifecycle = lifecycleOutput.textContent.startsWith("{")
      ? JSON.parse(lifecycleOutput.textContent)
      : null;
    if (lastLifecycle) {
      renderLifecycle(lastLifecycle);
    }
  }
}

selectedConnection.addEventListener("change", updateSelectedConnection);
form.addEventListener("submit", (event) => {
  event.preventDefault();
  try {
    post("save", collectSettings());
  } catch (failure) {
    showErrors({connections: failure.message});
  }
});
formatButton.addEventListener("click", () => {
  try {
    const connections = parseConnections();
    connectionsJson.value = JSON.stringify(connections, null, 2);
    updateConnectionOptions(connections, selectedConnection.value);
    clearErrors();
  } catch (failure) {
    showErrors({connections: failure.message});
  }
});
verifyButton.addEventListener("click", () => post("verify", {connectionKey: selectedConnection.value}));
lifecycleButton.addEventListener("click", () => post("lifecycle", {
  connectionKey: selectedConnection.value,
  syntheticUserId: syntheticUser.value,
  groupBindingKey: groupBinding.value,
}));
deactivateButton.addEventListener("click", () => post("deactivate", {connectionKey: selectedConnection.value}));
reactivateButton.addEventListener("click", () => post("reactivate", {connectionKey: selectedConnection.value}));
copyButton.addEventListener("click", async () => {
  await navigator.clipboard.writeText(jsonPreview.textContent);
  copyButton.textContent = "Copied";
  window.setTimeout(() => { copyButton.textContent = "Copy"; }, 1400);
});

async function load() {
  try {
    const response = await fetch("/configure/api/scim", {cache: "no-store"});
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || payload.message || "Unable to load SCIM state.");
    }
    connectionsJson.value = JSON.stringify(payload.values.connections, null, 2);
    credentialStatus = payload.credentialStatus || {};
    fixtureBindings = payload.fixtures?.groupBindings || [];
    populateFixtures(payload.fixtures?.users || []);
    updateConnectionOptions(payload.values.connections, payload.values.selectedConnectionKey);
    renderPreview(payload.preview);
    renderVerification(payload.lastVerification);
    renderLifecycle(payload.lastLifecycle);
    workspace.hidden = false;
  } catch (failure) {
    loadError.textContent = `Unable to load SCIM configuration: ${failure.message}`;
    loadError.hidden = false;
  }
}

load();
