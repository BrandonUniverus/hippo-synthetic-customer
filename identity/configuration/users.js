const workspace = document.querySelector("#user-workspace");
const loadError = document.querySelector("#user-load-error");
const userList = document.querySelector("#user-list");
const userCounts = document.querySelector("#user-counts");
const form = document.querySelector("#user-form");
const formError = document.querySelector("#user-form-error");
const operationStatus = document.querySelector("#user-operation-status");
const editorKicker = document.querySelector("#editor-kicker");
const editorTitle = document.querySelector("#editor-title");
const sourceBadge = document.querySelector("#user-source-badge");
const syntheticUserId = document.querySelector("#synthetic-user-id");
const username = document.querySelector("#user-username");
const firstName = document.querySelector("#user-first-name");
const lastName = document.querySelector("#user-last-name");
const email = document.querySelector("#user-email");
const title = document.querySelector("#user-title");
const enabled = document.querySelector("#user-enabled");
const newUserButton = document.querySelector("#new-user-button");
const saveUserButton = document.querySelector("#save-user-button");
const resetPasswordButton = document.querySelector("#reset-password-button");
const passwordResult = document.querySelector("#password-result");
const generatedPassword = document.querySelector("#generated-password");
const copyPasswordButton = document.querySelector("#copy-password-button");

let users = [];
let selectedUserId = null;

function clearErrors() {
  formError.hidden = true;
  formError.textContent = "";
  for (const control of form.querySelectorAll("[aria-invalid='true']")) {
    control.removeAttribute("aria-invalid");
    control.removeAttribute("aria-describedby");
  }
  for (const error of form.querySelectorAll(".field-error")) {
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
    const control = form.elements.namedItem(key);
    const error = document.querySelector(`#user-error-${key}`);
    if (!control || !error) {
      continue;
    }
    control.setAttribute("aria-invalid", "true");
    control.setAttribute("aria-describedby", error.id);
    error.textContent = message;
    error.hidden = false;
  }
}

function collectValues() {
  return {
    username: username.value,
    firstName: firstName.value,
    lastName: lastName.value,
    email: email.value,
    title: title.value,
    enabled: enabled.checked,
  };
}

function showPassword(password) {
  if (!password) {
    passwordResult.hidden = true;
    generatedPassword.textContent = "";
    return;
  }
  generatedPassword.textContent = password;
  passwordResult.hidden = false;
  passwordResult.scrollIntoView({behavior: "smooth", block: "nearest"});
}

function setBusy(busy) {
  newUserButton.disabled = busy;
  saveUserButton.disabled = busy;
  resetPasswordButton.disabled = busy;
  for (const button of userList.querySelectorAll("button")) {
    button.disabled = busy;
  }
}

function renderDirectory(counts) {
  userCounts.textContent = `${counts.total} total · ${counts.enabled} enabled · ${counts.local} local additions`;
  userList.replaceChildren();
  for (const user of users) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "user-row";
    button.dataset.userId = user.syntheticUserId;
    button.setAttribute("aria-pressed", String(user.syntheticUserId === selectedUserId));

    const identity = document.createElement("span");
    identity.className = "user-row-identity";
    const displayName = document.createElement("strong");
    displayName.textContent = `${user.firstName} ${user.lastName}`;
    const login = document.createElement("small");
    login.textContent = user.username;
    identity.append(displayName, login);

    const metadata = document.createElement("span");
    metadata.className = "user-row-metadata";
    const source = document.createElement("span");
    source.className = "source-chip";
    source.textContent = user.source === "local" ? "Local" : "Base";
    const state = document.createElement("span");
    state.className = `state-chip ${user.enabled ? "enabled" : "disabled"}`;
    state.textContent = user.enabled ? "Enabled" : "Disabled";
    metadata.append(source, state);

    button.append(identity, metadata);
    button.addEventListener("click", () => selectUser(user.syntheticUserId));
    userList.append(button);
  }
}

function selectUser(userId) {
  const user = users.find((candidate) => candidate.syntheticUserId === userId);
  if (!user) {
    return;
  }
  clearErrors();
  showPassword(null);
  selectedUserId = user.syntheticUserId;
  syntheticUserId.value = user.syntheticUserId;
  username.value = user.username;
  firstName.value = user.firstName;
  lastName.value = user.lastName;
  email.value = user.email;
  title.value = user.attributes.title;
  enabled.checked = user.enabled;
  editorKicker.textContent = user.source === "local" ? "Ignored local addition" : "Checked-in base identity";
  editorTitle.textContent = `Edit ${user.firstName} ${user.lastName}`;
  sourceBadge.textContent = user.source;
  sourceBadge.className = "status-badge";
  resetPasswordButton.hidden = false;
  saveUserButton.textContent = "Save and reset realm";
  operationStatus.textContent = user.credentialSource === "generated"
    ? "This user has a generated local password override."
    : "This base user currently uses the shared generated synthetic password.";
  const counts = {
    total: users.length,
    enabled: users.filter((candidate) => candidate.enabled).length,
    local: users.filter((candidate) => candidate.source === "local").length,
  };
  renderDirectory(counts);
}

function selectNewUser() {
  clearErrors();
  showPassword(null);
  selectedUserId = null;
  syntheticUserId.value = "";
  form.reset();
  enabled.checked = true;
  editorKicker.textContent = "Local addition";
  editorTitle.textContent = "Create a fictional user";
  sourceBadge.textContent = "New";
  sourceBadge.className = "status-badge";
  resetPasswordButton.hidden = true;
  saveUserButton.textContent = "Create and reset realm";
  operationStatus.textContent = "Passwords are generated by Northlake; this form never accepts one.";
  const counts = {
    total: users.length,
    enabled: users.filter((candidate) => candidate.enabled).length,
    local: users.filter((candidate) => candidate.source === "local").length,
  };
  renderDirectory(counts);
  username.focus();
}

async function loadUsers(preferredUserId = selectedUserId) {
  const response = await fetch("/configure/api/users", {cache: "no-store"});
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  const payload = await response.json();
  users = payload.users;
  selectedUserId = preferredUserId;
  renderDirectory(payload.counts);
  workspace.hidden = false;
  if (preferredUserId && users.some((user) => user.syntheticUserId === preferredUserId)) {
    selectUser(preferredUserId);
  } else if (selectedUserId === null) {
    selectNewUser();
  }
}

async function saveUser(event) {
  event.preventDefault();
  clearErrors();
  showPassword(null);
  setBusy(true);
  operationStatus.textContent = selectedUserId
    ? "Saving the overlay and regenerating the disposable realm…"
    : "Creating the overlay and regenerating the disposable realm…";
  const path = selectedUserId
    ? `/configure/api/users/${encodeURIComponent(selectedUserId)}/update`
    : "/configure/api/users/create";
  try {
    const response = await fetch(path, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({values: collectValues()}),
    });
    const payload = await response.json();
    if (!response.ok) {
      showErrors(payload.errors || {_form: payload.message || "Synthetic user could not be saved."});
      operationStatus.textContent = payload.applyError || payload.message || "Synthetic user could not be saved.";
      sourceBadge.textContent = response.status === 400 ? "Check values" : "Apply error";
      sourceBadge.className = "status-badge error";
      return;
    }
    selectedUserId = payload.user.syntheticUserId;
    await loadUsers(selectedUserId);
    operationStatus.textContent = payload.message;
    sourceBadge.textContent = "Applied";
    sourceBadge.className = "status-badge";
    showPassword(payload.generatedPassword);
  } catch (failure) {
    formError.textContent = `Synthetic-user service is unavailable: ${failure.message}`;
    formError.hidden = false;
    sourceBadge.textContent = "Unavailable";
    sourceBadge.className = "status-badge error";
    operationStatus.textContent = "The request did not reach the local configuration service.";
  } finally {
    setBusy(false);
  }
}

async function resetPassword() {
  if (!selectedUserId) {
    return;
  }
  if (!window.confirm("Generate a new development password and reset the disposable realm?")) {
    return;
  }
  clearErrors();
  showPassword(null);
  setBusy(true);
  operationStatus.textContent = "Generating a password and regenerating the disposable realm…";
  try {
    const response = await fetch(
      `/configure/api/users/${encodeURIComponent(selectedUserId)}/reset-password`,
      {method: "POST"},
    );
    const payload = await response.json();
    if (!response.ok) {
      showErrors(payload.errors || {_form: payload.message || "Password could not be reset."});
      operationStatus.textContent = payload.applyError || payload.message || "Password could not be reset.";
      sourceBadge.textContent = "Apply error";
      sourceBadge.className = "status-badge error";
      return;
    }
    await loadUsers(selectedUserId);
    operationStatus.textContent = payload.message;
    sourceBadge.textContent = "Applied";
    sourceBadge.className = "status-badge";
    showPassword(payload.generatedPassword);
  } catch (failure) {
    formError.textContent = `Synthetic-user service is unavailable: ${failure.message}`;
    formError.hidden = false;
    sourceBadge.textContent = "Unavailable";
    sourceBadge.className = "status-badge error";
  } finally {
    setBusy(false);
  }
}

newUserButton.addEventListener("click", selectNewUser);
form.addEventListener("submit", saveUser);
resetPasswordButton.addEventListener("click", resetPassword);
copyPasswordButton.addEventListener("click", async () => {
  await navigator.clipboard.writeText(generatedPassword.textContent);
  copyPasswordButton.textContent = "Copied";
  window.setTimeout(() => {
    copyPasswordButton.textContent = "Copy password";
  }, 1200);
});

loadUsers().catch((failure) => {
  loadError.textContent = `Unable to load synthetic users: ${failure.message}`;
  loadError.hidden = false;
});
