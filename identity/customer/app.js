"use strict";

const stateUrl = "/customer/api/state";
const evidenceUrl = "/customer/api/evidence";
let silentTimer = null;

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function query(values) {
  const parameters = new URLSearchParams();
  for (const [key, value] of Object.entries(values)) {
    if (value !== null && value !== undefined && value !== "") {
      parameters.set(key, value);
    }
  }
  return parameters.toString();
}

function returnPath() {
  const parameters = new URLSearchParams(window.location.search);
  parameters.delete("oidcOutcome");
  parameters.delete("realm");
  const suffix = parameters.toString();
  return `${window.location.pathname}${suffix ? `?${suffix}` : ""}`;
}

function authorizationHref(route, slot, realm, extra = {}) {
  return `${route}?${query({
    slot,
    returnTo: returnPath(),
    login_hint: realm.loginHint,
    cookieMode: extra.cookieMode ?? "Lax",
    prompt: extra.prompt,
    max_age: extra.maxAge,
    frame: extra.frame ? "true" : undefined,
  })}`;
}

function actionForm(action, label, className = "button secondary") {
  return `<form method="post" action="${action}"><button class="${className}" type="submit">${label}</button></form>`;
}

function renderSession(state) {
  const title = document.querySelector("#session-title");
  const detail = document.querySelector("#session-detail");
  const actions = document.querySelector("#session-actions");
  if (!state.session.authenticated) {
    title.textContent = "No customer session";
    detail.textContent = "The provider may still have an SSO session after local logout.";
    actions.innerHTML = "";
    return;
  }
  title.textContent = state.session.username;
  detail.textContent = `${state.session.realm} · ${state.session.cookieMode} cookie · clients: ${state.session.clients.join(", ")}`;
  if (state.session.providerTerminationRequested) {
    detail.textContent += " · provider session termination requested; local RP state intentionally remains";
  }
  actions.innerHTML = [
    actionForm("/customer/local-logout", "Local logout"),
    actionForm("/customer/rp-logout", "RP-initiated logout", "button primary"),
    actionForm("/customer/provider-terminate", "Provider terminates session", "button danger"),
  ].join("");
}

function realmCard(slot, realm, providerOrigin, activeCookieMode) {
  const laxLogin = authorizationHref("/customer/login", slot, realm, { cookieMode: "Lax" });
  const noneLogin = authorizationHref("/customer/login", slot, realm, { cookieMode: "None" });
  const silentTop = authorizationHref("/customer/probe", slot, realm, { prompt: "none", cookieMode: activeCookieMode });
  const consent = authorizationHref("/customer/consent", slot, realm, { prompt: "consent", cookieMode: activeCookieMode });
  const maxAge = authorizationHref("/customer/login", slot, realm, { prompt: "", maxAge: "0", cookieMode: activeCookieMode });
  const silentFrame = authorizationHref("/customer/probe", slot, realm, { prompt: "none", frame: true, cookieMode: activeCookieMode });
  const bootstrap = `${providerOrigin}/configure/browser-session/${slot}?cookieMode=Lax`;
  return `
    <article class="realm-card">
      <div class="realm-topline"><span>${escapeHtml(slot)}</span><span class="status-dot"></span></div>
      <h3>${escapeHtml(realm.realm)}</h3>
      <p class="issuer">${escapeHtml(realm.issuer)}</p>
      <dl>
        <div><dt>Primary</dt><dd>${escapeHtml(realm.primaryClientId)}</dd></div>
        <div><dt>Probe</dt><dd>${escapeHtml(realm.probeClientId)} · consent</dd></div>
      </dl>
      <div class="scenario-block">
        <p class="mini-label">ESTABLISH SESSION</p>
        <a class="button primary" href="${laxLogin}">Login · Lax cookie</a>
        <a class="button secondary" href="${noneLogin}">Login · SameSite=None</a>
        <a class="button secondary wide" href="${bootstrap}">Local admin bootstrap · no password exposure</a>
      </div>
      <div class="scenario-block">
        <p class="mini-label">REUSE AND POLICY</p>
        <a class="button secondary" href="${silentTop}">Top-level prompt=none</a>
        <a class="button secondary" href="${consent}">Grant probe consent</a>
        <a class="button secondary" href="${maxAge}">Require max_age=0</a>
        <button class="button secondary silent-button" data-frame-url="${silentFrame}" data-slot="${slot}" type="button">Iframe prompt=none</button>
      </div>
      <p class="hint">login_hint: ${escapeHtml(realm.loginHint)}</p>
    </article>`;
}

function renderRealms(state) {
  const grid = document.querySelector("#realm-grid");
  grid.innerHTML = Object.entries(state.realms)
    .map(([slot, realm]) => realmCard(
      slot,
      realm,
      state.providerOrigin,
      state.session.authenticated && state.session.realm === realm.realm
        ? state.session.cookieMode
        : "Lax",
    ))
    .join("");
  for (const button of document.querySelectorAll(".silent-button")) {
    button.addEventListener("click", () => {
      const frame = document.querySelector("#silent-frame");
      const result = document.querySelector("#silent-result");
      result.textContent = "Running prompt=none inside a cross-site iframe…";
      frame.src = button.dataset.frameUrl;
      frame.hidden = false;
      window.clearTimeout(silentTimer);
      silentTimer = window.setTimeout(async () => {
        result.textContent = "Iframe unavailable as expected: provider frame policy or browser third-party state prevented a callback.";
        frame.hidden = true;
        frame.src = "about:blank";
        await fetch("/customer/browser-observation", {
          method: "POST",
          headers: { "Content-Type": "application/x-www-form-urlencoded" },
          body: new URLSearchParams({
            slot: button.dataset.slot,
            outcome: "provider-frame-unavailable",
          }),
        });
        const evidenceResponse = await fetch(evidenceUrl);
        renderEvidence(await evidenceResponse.json());
      }, 4000);
    });
  }
}

function renderEvidence(payload) {
  const container = document.querySelector("#evidence");
  const events = [...payload.events].reverse().slice(0, 24);
  container.innerHTML = events.length
    ? events.map((event) => `
        <article class="event">
          <time>${escapeHtml(event.atUtc)}</time>
          <strong>${escapeHtml(event.event)}</strong>
          <span>${escapeHtml(event.realm ?? "n/a")}</span>
          <code>${escapeHtml(event.outcome)}</code>
        </article>`).join("")
    : '<p class="empty">No browser evidence recorded yet.</p>';
}

async function refresh() {
  const [stateResponse, evidenceResponse] = await Promise.all([fetch(stateUrl), fetch(evidenceUrl)]);
  const state = await stateResponse.json();
  const evidence = await evidenceResponse.json();
  const banner = document.querySelector("#banner");
  const outcome = new URLSearchParams(window.location.search).get("oidcOutcome");
  banner.textContent = state.ready
    ? `${state.crossSite ? "Cross-site boundary active" : "Same-site boundary"}: ${state.customerOrigin} → ${state.providerOrigin}${outcome ? ` · ${outcome}` : ""}`
    : "Apply both lab realms from the provider configuration page before running browser scenarios.";
  banner.classList.toggle("ready", state.ready);
  renderSession(state);
  renderRealms(state);
  renderEvidence(evidence);
}

window.addEventListener("message", async (event) => {
  if (event.origin !== window.location.origin || event.data?.type !== "northlake-silent-result") {
    return;
  }
  window.clearTimeout(silentTimer);
  document.querySelector("#silent-result").textContent = `Iframe result: ${event.data.outcome}`;
  document.querySelector("#silent-frame").hidden = true;
  await refresh();
});

refresh().catch((failure) => {
  document.querySelector("#banner").textContent = `Unable to load lab state: ${failure.message}`;
});
