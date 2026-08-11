const workspace = document.querySelector("#group-workspace");
const loadError = document.querySelector("#group-load-error");
const groupList = document.querySelector("#group-list");
const groupCounts = document.querySelector("#group-counts");
const groupForm = document.querySelector("#group-form");
const groupFormError = document.querySelector("#group-form-error");
const operationStatus = document.querySelector("#group-operation-status");
const editorKicker = document.querySelector("#group-editor-kicker");
const editorTitle = document.querySelector("#group-editor-title");
const sourceBadge = document.querySelector("#group-source-badge");
const selectedGroupId = document.querySelector("#selected-group-id");
const groupId = document.querySelector("#group-id");
const groupDisplayName = document.querySelector("#group-display-name");
const newGroupButton = document.querySelector("#new-group-button");
const saveGroupButton = document.querySelector("#save-group-button");
const deleteGroupButton = document.querySelector("#delete-group-button");
const membershipEditor = document.querySelector("#membership-editor");
const memberList = document.querySelector("#member-list");
const memberCountBadge = document.querySelector("#member-count-badge");
const saveMembersButton = document.querySelector("#save-members-button");
const claimPreview = document.querySelector("#claim-preview");
const claimUser = document.querySelector("#claim-user");
const selectedGroupClaims = document.querySelector("#selected-group-claims");
const selectedUserClaims = document.querySelector("#selected-user-claims");

let groups = [];
let users = [];
let selectedId = null;

function clearErrors() {
  groupFormError.hidden = true;
  groupFormError.textContent = "";
  for (const control of groupForm.querySelectorAll("[aria-invalid='true']")) {
    control.removeAttribute("aria-invalid");
    control.removeAttribute("aria-describedby");
  }
  for (const error of groupForm.querySelectorAll(".field-error")) {
    error.hidden = true;
    error.textContent = "";
  }
}

function showErrors(errors) {
  clearErrors();
  for (const [key, message] of Object.entries(errors || {})) {
    if (key === "_form" || key === "members") {
      groupFormError.textContent = message;
      groupFormError.hidden = false;
      continue;
    }
    const control = groupForm.elements.namedItem(key);
    const error = document.querySelector(`#group-error-${key}`);
    if (!control || !error) {
      continue;
    }
    control.setAttribute("aria-invalid", "true");
    control.setAttribute("aria-describedby", error.id);
    error.textContent = message;
    error.hidden = false;
  }
}

function groupValues() {
  return {
    groupId: groupId.value,
    displayName: groupDisplayName.value,
  };
}

function setBusy(busy) {
  newGroupButton.disabled = busy;
  saveGroupButton.disabled = busy;
  deleteGroupButton.disabled = busy;
  saveMembersButton.disabled = busy;
  for (const button of groupList.querySelectorAll("button")) {
    button.disabled = busy;
  }
}

function currentCounts() {
  return {
    total: groups.length,
    base: groups.filter((group) => group.source === "base").length,
    local: groups.filter((group) => group.source === "local").length,
  };
}

function renderDirectory(counts = currentCounts()) {
  groupCounts.textContent = `${counts.total} total · ${counts.base} checked in · ${counts.local} local additions`;
  groupList.replaceChildren();
  for (const group of groups) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "group-row";
    button.setAttribute("aria-pressed", String(group.groupId === selectedId));
    const identity = document.createElement("span");
    identity.className = "user-row-identity";
    const name = document.createElement("strong");
    name.textContent = group.displayName;
    const id = document.createElement("small");
    id.textContent = group.groupId;
    identity.append(name, id);
    const metadata = document.createElement("span");
    metadata.className = "user-row-metadata";
    const source = document.createElement("span");
    source.className = "source-chip";
    source.textContent = group.source === "local" ? "Local" : "Base";
    const members = document.createElement("span");
    members.className = "state-chip enabled";
    members.textContent = `${group.memberIds.length} member${group.memberIds.length === 1 ? "" : "s"}`;
    metadata.append(source, members);
    button.append(identity, metadata);
    button.addEventListener("click", () => selectGroup(group.groupId));
    groupList.append(button);
  }
}

function renderMembers(group) {
  memberList.replaceChildren();
  for (const user of users) {
    const label = document.createElement("label");
    label.className = "member-option";
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.name = "member";
    checkbox.value = user.syntheticUserId;
    checkbox.checked = group.memberIds.includes(user.syntheticUserId);
    checkbox.addEventListener("change", updateMemberCount);
    const identity = document.createElement("span");
    const displayName = document.createElement("strong");
    displayName.textContent = user.displayName;
    const login = document.createElement("small");
    login.textContent = `${user.username} · ${user.enabled ? "enabled" : "disabled"}`;
    identity.append(displayName, login);
    label.append(checkbox, identity);
    memberList.append(label);
  }
  updateMemberCount();
}

function selectedMembers() {
  return Array.from(memberList.querySelectorAll("input[name='member']:checked")).map(
    (checkbox) => checkbox.value,
  );
}

function updateMemberCount() {
  const count = selectedMembers().length;
  memberCountBadge.textContent = `${count} member${count === 1 ? "" : "s"}`;
}

function renderClaimUserOptions(preferredUserId) {
  claimUser.replaceChildren();
  for (const user of users) {
    const option = document.createElement("option");
    option.value = user.syntheticUserId;
    option.textContent = `${user.displayName} (${user.username})`;
    claimUser.append(option);
  }
  if (preferredUserId && users.some((user) => user.syntheticUserId === preferredUserId)) {
    claimUser.value = preferredUserId;
  }
}

async function renderUserClaims() {
  if (!claimUser.value) {
    selectedUserClaims.textContent = "{}";
    return;
  }
  const response = await fetch(
    `/configure/api/groups/claims?userId=${encodeURIComponent(claimUser.value)}`,
    {cache: "no-store"},
  );
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  const payload = await response.json();
  selectedUserClaims.textContent = JSON.stringify(
    {oidc: payload.oidc, saml: payload.saml},
    null,
    2,
  );
}

function selectGroup(id) {
  const group = groups.find((candidate) => candidate.groupId === id);
  if (!group) {
    return;
  }
  clearErrors();
  selectedId = group.groupId;
  selectedGroupId.value = group.groupId;
  groupId.value = group.groupId;
  groupDisplayName.value = group.displayName;
  groupId.disabled = group.source === "base";
  groupDisplayName.disabled = group.source === "base";
  editorKicker.textContent = group.source === "local"
    ? "Ignored local addition"
    : "Checked-in base group";
  editorTitle.textContent = group.displayName;
  sourceBadge.textContent = group.source;
  sourceBadge.className = "status-badge";
  deleteGroupButton.hidden = group.source !== "local";
  saveGroupButton.hidden = group.source !== "local";
  saveGroupButton.textContent = "Rename and reset realm";
  operationStatus.textContent = group.source === "local"
    ? "This local group can be renamed or removed."
    : "The checked-in group definition is preserved; only its synthetic memberships can change.";
  membershipEditor.hidden = false;
  claimPreview.hidden = false;
  renderMembers(group);
  renderClaimUserOptions(group.memberIds[0] || claimUser.value || users[0]?.syntheticUserId);
  selectedGroupClaims.textContent = JSON.stringify(group.claimPreview, null, 2);
  renderUserClaims().catch((failure) => {
    selectedUserClaims.textContent = `Unable to preview claims: ${failure.message}`;
  });
  renderDirectory();
}

function selectNewGroup() {
  clearErrors();
  selectedId = null;
  selectedGroupId.value = "";
  groupForm.reset();
  groupId.disabled = false;
  groupDisplayName.disabled = false;
  editorKicker.textContent = "Local addition";
  editorTitle.textContent = "Create a synthetic group";
  sourceBadge.textContent = "New";
  sourceBadge.className = "status-badge";
  operationStatus.textContent = "New groups carry no company or permission meaning.";
  deleteGroupButton.hidden = true;
  saveGroupButton.hidden = false;
  saveGroupButton.textContent = "Create and reset realm";
  membershipEditor.hidden = true;
  claimPreview.hidden = true;
  renderDirectory();
  groupId.focus();
}

async function loadGroups(preferredGroupId = selectedId) {
  const response = await fetch("/configure/api/groups", {cache: "no-store"});
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  const payload = await response.json();
  groups = payload.groups;
  users = payload.users;
  selectedId = preferredGroupId;
  renderDirectory(payload.counts);
  workspace.hidden = false;
  if (preferredGroupId && groups.some((group) => group.groupId === preferredGroupId)) {
    selectGroup(preferredGroupId);
  } else {
    selectNewGroup();
  }
}

async function saveGroup(event) {
  event.preventDefault();
  clearErrors();
  setBusy(true);
  operationStatus.textContent = selectedId
    ? "Renaming the local group and regenerating the disposable realm…"
    : "Creating the local group and regenerating the disposable realm…";
  const path = selectedId
    ? `/configure/api/groups/${encodeURIComponent(selectedId)}/update`
    : "/configure/api/groups/create";
  try {
    const response = await fetch(path, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({values: groupValues()}),
    });
    const payload = await response.json();
    if (!response.ok) {
      showErrors(payload.errors || {_form: payload.message || "Synthetic group could not be saved."});
      operationStatus.textContent = payload.applyError || payload.message || "Synthetic group could not be saved.";
      sourceBadge.textContent = response.status === 400 ? "Check values" : "Apply error";
      sourceBadge.className = "status-badge error";
      return;
    }
    selectedId = payload.group.groupId;
    await loadGroups(selectedId);
    operationStatus.textContent = payload.message;
    sourceBadge.textContent = "Applied";
    sourceBadge.className = "status-badge";
  } catch (failure) {
    groupFormError.textContent = `Synthetic-group service is unavailable: ${failure.message}`;
    groupFormError.hidden = false;
    sourceBadge.textContent = "Unavailable";
    sourceBadge.className = "status-badge error";
  } finally {
    setBusy(false);
  }
}

async function saveMembers() {
  if (!selectedId) {
    return;
  }
  clearErrors();
  setBusy(true);
  operationStatus.textContent = "Saving memberships and regenerating the disposable realm…";
  try {
    const response = await fetch(
      `/configure/api/groups/${encodeURIComponent(selectedId)}/members`,
      {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({values: {members: selectedMembers()}}),
      },
    );
    const payload = await response.json();
    if (!response.ok) {
      showErrors(payload.errors || {_form: payload.message || "Memberships could not be saved."});
      operationStatus.textContent = payload.applyError || payload.message || "Memberships could not be saved.";
      sourceBadge.textContent = "Apply error";
      sourceBadge.className = "status-badge error";
      return;
    }
    await loadGroups(selectedId);
    operationStatus.textContent = payload.message;
    sourceBadge.textContent = "Applied";
    sourceBadge.className = "status-badge";
  } catch (failure) {
    groupFormError.textContent = `Synthetic-group service is unavailable: ${failure.message}`;
    groupFormError.hidden = false;
    sourceBadge.textContent = "Unavailable";
    sourceBadge.className = "status-badge error";
  } finally {
    setBusy(false);
  }
}

async function deleteGroup() {
  if (!selectedId || !window.confirm("Remove this local group and reset the disposable realm?")) {
    return;
  }
  clearErrors();
  setBusy(true);
  operationStatus.textContent = "Removing the local group and regenerating the disposable realm…";
  try {
    const response = await fetch(
      `/configure/api/groups/${encodeURIComponent(selectedId)}/delete`,
      {method: "POST"},
    );
    const payload = await response.json();
    if (!response.ok) {
      showErrors(payload.errors || {_form: payload.message || "Local group could not be removed."});
      operationStatus.textContent = payload.applyError || payload.message || "Local group could not be removed.";
      return;
    }
    selectedId = null;
    await loadGroups();
    operationStatus.textContent = payload.message;
  } catch (failure) {
    groupFormError.textContent = `Synthetic-group service is unavailable: ${failure.message}`;
    groupFormError.hidden = false;
  } finally {
    setBusy(false);
  }
}

newGroupButton.addEventListener("click", selectNewGroup);
groupForm.addEventListener("submit", saveGroup);
saveMembersButton.addEventListener("click", saveMembers);
deleteGroupButton.addEventListener("click", deleteGroup);
claimUser.addEventListener("change", () => {
  renderUserClaims().catch((failure) => {
    selectedUserClaims.textContent = `Unable to preview claims: ${failure.message}`;
  });
});

loadGroups().catch((failure) => {
  loadError.textContent = `Unable to load synthetic groups: ${failure.message}`;
  loadError.hidden = false;
});
