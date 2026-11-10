"use strict";
// Every URL is relative: the tool runs at its own root (port 18082) and inside
// the Northlake site at /meter-reading/.
const $ = id => document.getElementById(id);
let status, imported, round, dirty = false;
const text = (id, value) => { $(id).textContent = value; };
async function api(path, body) {
  const response = await fetch(path, body === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const value = await response.json();
  if (!response.ok) throw new Error(value.error || `Request failed (${response.status})`);
  return value;
}
async function work(action) {
  $("error").hidden = true;
  const controls = [...document.querySelectorAll("button")];
  const disabled = controls.map(control => control.disabled);
  controls.forEach(control => { control.disabled = true; });
  try { await action(); } catch (error) { text("error", error.message); $("error").hidden = false; }
  finally { controls.forEach((control, i) => { control.disabled = disabled[i]; }); if (round) setAvailability(); }
}
function setAvailability() {
  const final = Boolean(round.artifact);
  $("visit-fields").disabled = final;
  $("save").hidden = final;
  $("finalize").hidden = final;
  $("finalize").disabled = !round.observation || dirty;
  $("download").hidden = $("manifest").hidden = $("finalized").hidden = !final;
  $("follow-up").hidden = round.observation?.action !== "skip";
  const enabled = HandheldModel.canDeliver(round, status.targets);
  $("deliver").disabled = $("replay").disabled = !enabled;
  $("replay").hidden = round.status !== "delivered";
  text("delivery-help", enabled ? `Explicit destination: ${round.channel.delivery_target}. Receipts prevent automatic redelivery after a file is claimed.` : "Delivery is off. Configure and enable the binding’s target on the host, or download the return.");
}
async function list() {
  const rounds = await api("api/rounds");
  $("round-list").replaceChildren();
  for (const item of rounds) {
    const box = document.createElement("div"); box.className = "hh-saved";
    const button = document.createElement("button"); button.type = "button"; button.className = "button button-quiet";
    button.textContent = `${item.channel.route} · ${item.status}`;
    button.addEventListener("click", () => work(() => open(item.id)));
    const info = document.createElement("p"); info.textContent = `${item.created_at.slice(0, 10)} · ${item.id.slice(0, 8)}${item.fixture_only ? " · Demonstration" : ""}`;
    box.append(button, info); $("round-list").append(box);
  }
}
async function open(id) {
  round = await api(`api/rounds/${id}`);
  localStorage.setItem("northlake-handheld-round", id);
  render();
}
function render() {
  dirty = false;
  const c = round.channel, o = round.observation;
  $("round").hidden = false;
  text("round-title", `${c.route} · ${c.meter_description}`); text("status", round.status);
  text("round-context", `${round.environment_id} / ${round.database} · ${c.return_format.toUpperCase()} · revision ${round.revision}`);
  $("fixture-warning").hidden = !round.fixture_only;
  $("binding-details").replaceChildren();
  for (const [label, value] of [["Meter", `${c.meter_number} (${c.meter_id})`], ["Prompt / points", `${c.text_prompt} · register ${c.reading_pt_id} / usage ${c.usage_pt_id}`], ["Known opening", `${c.opening.value} ${c.display_unit} at ${c.opening.observed_at}`], ["Exported previous", c.export_previous]]) {
    const dt = document.createElement("dt"), dd = document.createElement("dd"); dt.textContent = label; dd.textContent = value; $("binding-details").append(dt, dd);
  }
  text("opening-reason", `Controlled opening: ${c.opening.reason}`);
  $("reader").value = o?.reader || "NLR001";
  $("visit-action").value = o?.action || "read";
  $("observed-at").value = o?.observed_at || new Date(Date.parse(round.after || c.opening.observed_at) + 14 * 86400000).toISOString().replace(".000Z", "Z");
  $("value").value = o && o.action === "read" ? o.value : "";
  $("read-code").value = o?.read_code || "N";
  $("audit-code").value = o?.audit_code || "0";
  $("skip-code").value = o?.skip_code || "01";
  $("note").value = o?.note || "";
  $("note").maxLength = c.return_format === "mvrs" ? 40 : 128;
  text("note-help", c.return_format === "mvrs" ? "Up to 40 ASCII characters. Returned as an MTM visit log after the reading." : "Up to 128 ASCII characters. Preserved in the return and evidence; Neptune does not publish this note to the HMR log.");
  text("value-label", `Whole-unit register (${c.display_unit})`);
  $("review").hidden = !o;
  if (o) {
    const codes = [o.read_code && o.read_code !== "N" ? `read code ${o.read_code}` : "", o.audit_code && o.audit_code !== "0" ? `audit code ${o.audit_code}` : "", o.skip_code ? `skip code ${o.skip_code}` : ""].filter(Boolean);
    text("review-summary", `${o.reader} · ${o.observed_at} · ${o.action === "skip" ? "Skipped; no accepted reading" : `Register ${o.value} ${c.display_unit}; usage ${o.usage} ${c.usage_unit}`} · ${o.note || "No note"}${codes.length ? ` · ${codes.join(", ")}` : ""}`);
  }
  if (round.artifact) {
    $("download").href = `download/${round.id}`;
    $("manifest").href = `releases/handheld-${round.id}/manifest.json`;
    text("artifact-hash", `SHA-256 ${round.artifact.sha256} · ${round.artifact.size} bytes`);
  }
  text("provenance", JSON.stringify({ id: round.id, source: round.source, export_sha256: round.export_sha256, binding_sha256: round.binding_sha256, parent: round.parent, events: round.events }, null, 2));
  $("finalize").disabled = !o;
  changeAction(); setAvailability();
}
function changeAction() {
  const skip = $("visit-action").value === "skip";
  $("value").disabled = skip;
  $("value").required = !$("value").disabled;
  // MVRS codes: a read carries a read and an audit code, a skip its skip code. Neptune returns carry none.
  const mvrs = round?.channel.return_format === "mvrs";
  $("read-code-field").hidden = $("audit-code-field").hidden = !mvrs || skip;
  $("skip-code-field").hidden = !mvrs || !skip;
  $("code-help").hidden = !mvrs;
}
function visitCodes() {
  if (round.channel.return_format !== "mvrs") return {};
  return $("visit-action").value === "skip" ? { skip_code: $("skip-code").value } : { read_code: $("read-code").value, audit_code: $("audit-code").value };
}
async function preflight(files) {
  imported = undefined; $("preflight").hidden = true;
  const result = await api("api/preflight", files);
  imported = files;
  $("route").replaceChildren(...result.channels.map(c => new Option(`${c.route} · ${c.meter_description} · ${c.return_format.toUpperCase()}`, c.route)));
  text("preflight-summary", `${result.channels.length} checked master route(s) · ${result.environment_id} / ${result.database}`);
  $("preflight").hidden = false;
}
function readFile(file) {
  if (!file || file.size > 2000000) throw new Error("Select both files; each must be no larger than 2 MB.");
  return new Promise((resolve, reject) => { const reader = new FileReader(); reader.onload = () => resolve(reader.result.split(",")[1]); reader.onerror = reject; reader.readAsDataURL(file); });
}
$("check-files").addEventListener("click", () => work(async () => preflight({ export_base64: await readFile($("export-file").files[0]), binding_base64: await readFile($("binding-file").files[0]) })));
$("demo").addEventListener("click", () => work(async () => preflight(await api("api/demo"))));
$("create").addEventListener("click", () => work(async () => { const created = await api("api/rounds", { ...imported, route: $("route").value }); await open(created.id); await list(); $("round").scrollIntoView({ block: "start" }); }));
$("visit-action").addEventListener("change", changeAction);
$("visit-form").addEventListener("input", () => { dirty = true; $("finalize").disabled = true; });
$("visit-form").addEventListener("submit", event => { event.preventDefault(); work(async () => {
  const observation = HandheldModel.observation({ reader: $("reader").value, action: $("visit-action").value, value: $("value").value, observed_at: $("observed-at").value, note: $("note").value, ...visitCodes() });
  await api(`api/rounds/${round.id}/save`, { revision: round.revision, observation }); await open(round.id); await list();
}); });
$("reload").addEventListener("click", () => work(() => open(round.id)));
$("finalize").addEventListener("click", () => work(async () => { await api(`api/rounds/${round.id}/finalize`, { revision: round.revision }); await open(round.id); await list(); }));
for (const [id, action] of [["correct", "correction"], ["follow-up", "follow-up"]]) $(id).addEventListener("click", () => work(async () => { const created = await api(`api/rounds/${round.id}/${action}`, { revision: round.revision }); await open(created.id); await list(); }));
for (const [id, replay] of [["deliver", false], ["replay", true]]) $(id).addEventListener("click", () => work(async () => {
  await api(`api/rounds/${round.id}/deliver`, { target: round.channel.delivery_target, replay }); await open(round.id); await list();
}));
$("refresh").addEventListener("click", () => work(async () => { status = await api("api/status"); await list(); if (round) await open(round.id); }));
work(async () => {
  status = await api("api/status");
  $("reader").replaceChildren(...Object.entries(status.readers).map(([id, name]) => new Option(`${name} (${id})`, id)));
  text("message", `Source ready · ${status.source.release_id}. Retained history and installed import verification remain separate.`);
  await list(); const selected = localStorage.getItem("northlake-handheld-round"); if (selected) await open(selected);
});
