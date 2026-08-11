const form = document.querySelector("#configuration-form");
const workspace = document.querySelector("#workspace");
const loadError = document.querySelector("#load-error");
const formError = document.querySelector("#form-error");
const groupsRoot = document.querySelector("#field-groups");
const jsonPreview = document.querySelector("#json-preview");
const endpointLinks = document.querySelector("#endpoint-links");
const operationStatus = document.querySelector("#operation-status");
const statusBadge = document.querySelector("#status-badge");
const appliedRealm = document.querySelector("#applied-realm");
const pendingApply = document.querySelector("#pending-apply");
const previewButton = document.querySelector("#preview-button");
const saveButton = document.querySelector("#save-button");
const applyButton = document.querySelector("#apply-button");
const copyButton = document.querySelector("#copy-button");

let fieldCatalog = [];

function fieldId(key) {
  return `field-${key}`;
}

function createField(field, value) {
  const container = document.createElement("div");
  container.className = "field";
  if (field.kind === "uri-list") {
    container.classList.add("field-wide");
  }
  if (field.kind === "checkbox") {
    container.classList.add("field-checkbox");
  }

  const controlId = fieldId(field.key);
  let control;
  if (field.kind === "checkbox") {
    const label = document.createElement("label");
    label.className = "checkbox-label";
    control = document.createElement("input");
    control.type = "checkbox";
    control.checked = Boolean(value);
    label.append(control, document.createTextNode(field.label));
    container.append(label);
  } else {
    const label = document.createElement("label");
    label.htmlFor = controlId;
    label.textContent = field.label;
    container.append(label);
    if (field.kind === "uri-list") {
      control = document.createElement("textarea");
      control.value = Array.isArray(value) ? value.join("\n") : "";
      control.spellcheck = false;
    } else if (field.kind === "select") {
      control = document.createElement("select");
      for (const choice of field.choices || []) {
        const option = document.createElement("option");
        option.value = choice.value;
        option.textContent = choice.label;
        option.selected = choice.value === value;
        control.append(option);
      }
    } else {
      control = document.createElement("input");
      control.type = field.kind;
      control.value = value ?? "";
      if (field.kind === "number") {
        control.min = "1";
        control.max = "65535";
      }
    }
    container.append(control);
  }
  control.id = controlId;
  control.name = field.key;
  control.dataset.kind = field.kind;
  if (field.required) {
    control.required = true;
  }

  const help = document.createElement("p");
  help.className = "field-help";
  help.textContent = field.help || "";
  container.append(help);

  const fieldError = document.createElement("p");
  fieldError.className = "field-error";
  fieldError.id = `error-${field.key}`;
  fieldError.hidden = true;
  container.append(fieldError);
  return container;
}

function renderForm(schema, values) {
  fieldCatalog = schema.groups.flatMap((group) => group.fields);
  groupsRoot.replaceChildren();
  for (const group of schema.groups) {
    const section = document.createElement("section");
    section.className = "field-group";

    const header = document.createElement("div");
    header.className = "field-group-header";
    const title = document.createElement("h2");
    title.textContent = group.title;
    const description = document.createElement("p");
    description.textContent = group.description;
    header.append(title, description);

    const grid = document.createElement("div");
    grid.className = "field-grid";
    for (const field of group.fields) {
      grid.append(createField(field, values[field.key]));
    }
    section.append(header, grid);
    groupsRoot.append(section);
  }
}

function collectValues() {
  const values = {};
  for (const field of fieldCatalog) {
    const control = document.querySelector(`#${fieldId(field.key)}`);
    if (field.kind === "checkbox") {
      values[field.key] = control.checked;
    } else if (field.kind === "number") {
      values[field.key] = Number(control.value);
    } else if (field.kind === "uri-list") {
      values[field.key] = control.value
        .split(/\r?\n/)
        .map((value) => value.trim())
        .filter(Boolean);
    } else {
      values[field.key] = control.value;
    }
  }
  return values;
}

function clearErrors() {
  formError.hidden = true;
  formError.textContent = "";
  for (const field of fieldCatalog) {
    const control = document.querySelector(`#${fieldId(field.key)}`);
    const error = document.querySelector(`#error-${field.key}`);
    control.removeAttribute("aria-invalid");
    control.removeAttribute("aria-describedby");
    error.hidden = true;
    error.textContent = "";
  }
}

function showErrors(errors) {
  clearErrors();
  for (const [key, message] of Object.entries(errors || {})) {
    if (key === "_form") {
      formError.textContent = message;
      formError.hidden = false;
      continue;
    }
    const control = document.querySelector(`#${fieldId(key)}`);
    const fieldError = document.querySelector(`#error-${key}`);
    if (!control || !fieldError) {
      continue;
    }
    control.setAttribute("aria-invalid", "true");
    control.setAttribute("aria-describedby", fieldError.id);
    fieldError.textContent = message;
    fieldError.hidden = false;
  }
}

function renderPreview(preview) {
  jsonPreview.textContent = JSON.stringify(preview, null, 2);
  const endpoints = [
    ["Issuer", preview.issuer],
    ["Account", preview.account],
    ["Realm admin", preview.adminConsole],
    ["OIDC discovery", preview.oidc.discovery],
    ["SAML metadata", preview.saml.metadata],
  ];
  endpointLinks.replaceChildren();
  for (const [label, href] of endpoints) {
    const link = document.createElement("a");
    link.className = "endpoint-link";
    link.href = href;
    link.target = "_blank";
    link.rel = "noopener";
    const name = document.createElement("span");
    name.textContent = label;
    const address = document.createElement("small");
    address.textContent = href;
    link.append(name, address);
    endpointLinks.append(link);
  }
}

function renderStatus(status) {
  appliedRealm.textContent = status.appliedRealmKey || "—";
  pendingApply.textContent = status.pendingApply ? "Yes" : "No";
  if (status.lastApplyError) {
    statusBadge.textContent = "Apply error";
    statusBadge.className = "status-badge error";
    operationStatus.textContent = status.lastApplyError;
  } else if (status.pendingApply) {
    statusBadge.textContent = "Pending";
    statusBadge.className = "status-badge pending";
    operationStatus.textContent = "The saved configuration will be retried after the stack starts.";
  }
}

function setBusy(busy) {
  previewButton.disabled = busy;
  saveButton.disabled = busy;
  applyButton.disabled = busy;
}

async function send(action) {
  clearErrors();
  setBusy(true);
  operationStatus.textContent = `${action === "apply" ? "Applying" : action === "save" ? "Saving" : "Refreshing"} configuration…`;
  try {
    const response = await fetch(`/configure/api/${action}`, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({values: collectValues()}),
    });
    const payload = await response.json();
    if (!response.ok) {
      showErrors(payload.errors || {_form: payload.message || "Configuration failed."});
      operationStatus.textContent = payload.applyError || payload.message || "Configuration failed.";
      statusBadge.textContent = response.status === 400 ? "Check values" : "Apply error";
      statusBadge.className = "status-badge error";
      if (payload.preview) {
        renderPreview(payload.preview);
      }
      return;
    }
    renderPreview(payload.preview);
    operationStatus.textContent = payload.message || "Preview refreshed.";
    if (action === "apply" && payload.restartRequired) {
      statusBadge.textContent = "Restart needed";
      statusBadge.className = "status-badge pending";
      pendingApply.textContent = "Yes";
    } else if (action === "apply") {
      statusBadge.textContent = "Applied";
      statusBadge.className = "status-badge";
      appliedRealm.textContent = payload.values.realmKey;
      pendingApply.textContent = "No";
    } else if (action === "save") {
      statusBadge.textContent = "Saved";
      statusBadge.className = "status-badge";
    } else {
      statusBadge.textContent = "Preview";
      statusBadge.className = "status-badge";
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
form.addEventListener("submit", (event) => {
  event.preventDefault();
  if (window.confirm("Apply this configuration and reset the disposable Keycloak realm?")) {
    send("apply");
  }
});
copyButton.addEventListener("click", async () => {
  await navigator.clipboard.writeText(jsonPreview.textContent);
  copyButton.textContent = "Copied";
  window.setTimeout(() => {
    copyButton.textContent = "Copy";
  }, 1200);
});

async function initialize() {
  try {
    const response = await fetch("/configure/api/state", {cache: "no-store"});
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const state = await response.json();
    renderForm(state.schema, state.values);
    renderPreview(state.preview);
    renderStatus(state.status);
    workspace.hidden = false;
  } catch (failure) {
    loadError.textContent = `Unable to load the local provider configuration: ${failure.message}`;
    loadError.hidden = false;
  }
}

initialize();
