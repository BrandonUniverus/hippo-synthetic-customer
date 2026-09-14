// Update the single customer workbook from northlake_packet.py's data.
// NORTHLAKE_ARTIFACT_RUNTIME locates the supported artifact-tool package;
// it is not an EEM instance setting.
import fs from "node:fs/promises";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath, pathToFileURL } from "node:url";

const artifactModule = process.env.NORTHLAKE_ARTIFACT_RUNTIME
  ? pathToFileURL(createRequire(path.join(process.env.NORTHLAKE_ARTIFACT_RUNTIME, "package.json")).resolve("@oai/artifact-tool")).href
  : "@oai/artifact-tool";
const { FileBlob, SpreadsheetFile } = await import(artifactModule);
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const packet = JSON.parse(await fs.readFile(path.join(root, "out/northlake-onboarding/packet.json"), "utf8"));
const filename = "data-collection-workbook.xlsx";
const target = path.join(root, "outputs/northlake-university", filename);
const definitions = packet.sheets;
const previewDir = process.env.NORTHLAKE_PREVIEW_DIR;
if (previewDir) await fs.mkdir(previewDir, { recursive: true });

async function sheetsOf(workbook) {
  const result = await workbook.inspect({ kind: "sheet", maxChars: 50000 });
  return result.ndjson.split("\n").filter(Boolean).map(JSON.parse).filter(item => item.kind === "sheet");
}

function columnName(index) {
  let text = "";
  for (let n = index + 1; n > 0; n = Math.floor((n - 1) / 26)) text = String.fromCharCode(65 + (n - 1) % 26) + text;
  return text;
}

function columnWidth(header) {
  if (/^Unit$|^Units$|Area Unit|Multiplier|^Rate$|Gross Area|Interval Minutes/.test(header)) return 100;
  if (/Notes|Requirement|Convention|Channel \/ Source|Occupancy|Boundary|What Northlake|Purpose/.test(header)) return 330;
  if (/Meter|Measurement|Source|Device \/ Station|Account \/ Agreement|Requested Total|Email/.test(header)) return 300;
  if (/Provider|Counterparty|Scope|Location|Property|Service Name|Organization/.test(header)) return 220;
  if (/Date|Effective/.test(header)) return 150;
  return 175;
}

function storedTableValues(definition) {
  return [definition.headers, ...definition.rows].map(row => row.map(value => {
    if (typeof value === "string" && /^\d{4}-\d{2}-\d{2}$/.test(value)) return (Date.parse(`${value}T00:00:00Z`) - Date.UTC(1899, 11, 30)) / 86400000;
    return value === "" || value == null ? null : value;
  }));
}

const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(target));
const existing = await sheetsOf(workbook);
const before = new Map();
for (const info of existing) {
  const range = workbook.resolve(info.id).getRange(info.range);
  before.set(info.name, { range: info.range, values: JSON.stringify(range.values), formulas: JSON.stringify(range.formulas) });
}
const changed = new Set();
for (const [name, definition] of Object.entries(definitions)) {
  const info = existing.find(item => item.name === name);
  const sheet = info ? workbook.resolve(info.id) : workbook.worksheets.add(name);
  const endColumn = columnName(definition.headers.length - 1);
  const lastRow = definition.rows.length + 4;
  const tableRange = `A4:${endColumn}${lastRow}`;
  if (info?.range === `A1:${endColumn}${lastRow}` && sheet.getRange("A1").values[0][0] === name && sheet.getRange("A2").values[0][0] === definition.description && JSON.stringify(sheet.getRange(tableRange).values) === JSON.stringify(storedTableValues(definition))) continue;
  changed.add(name);
  const oldStyle = sheet.tables.items[0]?.style;
  for (const oldTable of [...sheet.tables.items]) oldTable.delete();
  if (info) sheet.getRange(info.range).clear({ applyTo: "contents" });
  const rows = definition.rows.map(row => row.map(value => {
    if (typeof value === "string" && /^\d{4}-\d{2}-\d{2}$/.test(value)) return new Date(`${value}T00:00:00Z`);
    return value;
  }));
  sheet.unmergeCells(`A1:${endColumn}1`);
  sheet.unmergeCells(`A2:${endColumn}2`);
  sheet.mergeCells(`A1:${endColumn}1`);
  sheet.mergeCells(`A2:${endColumn}2`);
  sheet.getRange("A1").values = [[name]];
  sheet.getRange("A2").values = [[definition.description]];
  sheet.getRange(tableRange).values = [definition.headers, ...rows];
  const nativeTable = sheet.tables.add(tableRange, true, name.replace(/[^A-Za-z0-9]/g, "") + "Table");
  nativeTable.style = oldStyle || "TableStyleMedium4";
  nativeTable.showFilterButton = true;

  // Extend the reference's green title/header treatment only where data changes.
  const used = sheet.getRange(`A1:${endColumn}${lastRow}`);
  if (rows.length > 8) {
    sheet.freezePanes.freezeRows(4);
    sheet.freezePanes.freezeColumns(1);
  }
  used.format.font = { name: "Arial", size: 10, color: "#203A31" };
  used.format.verticalAlignment = "center";
  used.format.wrapText = true;
  sheet.getRange(`A1:${endColumn}1`).format = { fill: "#244539", font: { name: "Arial", size: 12, bold: true, color: "#FFFFFF" } };
  sheet.getRange(`A1:${endColumn}1`).format.rowHeightPx = 32;
  sheet.getRange(`A2:${endColumn}2`).format.fill = "#EAF1ED";
  sheet.getRange(`A2:${endColumn}2`).format.rowHeightPx = 44;
  sheet.getRange(`A4:${endColumn}4`).format = { fill: "#3C6B5C", font: { name: "Arial", size: 10, bold: true, color: "#FFFFFF" }, wrapText: true };
  sheet.getRange(`A4:${endColumn}4`).format.rowHeightPx = 44;
  const widths = definition.headers.map(columnWidth);
  for (let column = 0; column < definition.headers.length; column++) {
    const col = columnName(column);
    sheet.getRange(`${col}1:${col}${lastRow}`).format.columnWidthPx = widths[column];
    const body = sheet.getRange(`${col}5:${col}${lastRow}`);
    if (/Date/.test(definition.headers[column])) body.setNumberFormat("mm/dd/yyyy");
    else if (/^Rate$/.test(definition.headers[column])) body.setNumberFormat("0.000");
    else if (/Gross Area|Multiplier|Interval Minutes/.test(definition.headers[column])) body.setNumberFormat(rows.every(row => Number.isInteger(row[column])) ? "#,##0" : "#,##0.00");
    // Keep the template's validation range so its earlier status choices are replaced.
    if (/Review Status|^Status$/.test(definition.headers[column])) sheet.getRange(`${col}5:${col}${Math.max(100, lastRow)}`).dataValidation = { rule: { type: "list", values: ["Documented", "Pending", "Planned", "Sample supplied", "Confirmed", "UI acceptance pending", "Ongoing"] } };
  }
  for (let index = 0; index < rows.length; index++) {
    const height = Math.max(36, ...rows[index].map((value, column) => {
      const text = value instanceof Date ? "09/14/2026" : String(value ?? "");
      return Math.ceil(text.length / Math.max(10, (widths[column] - 20) / 7)) * 16 + 14;
    }));
    const range = sheet.getRange(`A${index + 5}:${endColumn}${index + 5}`);
    range.format.rowHeightPx = height;
    range.format.fill = index % 2 ? "#FFFFFF" : "#EEF6F0";
  }
}

if (changed.size === 0) {
  console.log(`${filename}: all generated tables are current; no file changes.`);
  process.exit(0);
}
workbook.recalculate();
const errors = await workbook.inspect({ kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!", options: { useRegex: true, maxResults: 50 }, maxChars: 3000 });
console.log(filename, "formula error scan:", errors.ndjson);
if (previewDir) {
  for (const name of changed) {
    const definition = definitions[name];
    const image = await workbook.render({ sheetName: name, range: `A1:${columnName(definition.headers.length - 1)}${definition.rows.length + 4}`, scale: 1, format: "png" });
    await fs.writeFile(path.join(previewDir, `${name.replace(/[^A-Za-z0-9]/g, "-")}.png`), new Uint8Array(await image.arrayBuffer()));
  }
}
const result = await SpreadsheetFile.exportXlsx(workbook);
await result.save(target);
await fs.rm(`${target}.inspect.ndjson`, { force: true });
const saved = await SpreadsheetFile.importXlsx(await FileBlob.load(target));
const savedSheets = await sheetsOf(saved);
for (const [name, original] of before) {
  if (changed.has(name)) continue;
  const sheet = saved.resolve(savedSheets.find(item => item.name === name).id);
  const range = sheet.getRange(original.range);
  if (JSON.stringify(range.values) !== original.values || JSON.stringify(range.formulas) !== original.formulas) throw new Error(`Unrelated sheet changed: ${filename} / ${name}`);
}
for (const [name, definition] of Object.entries(definitions)) {
  const sheet = saved.resolve(savedSheets.find(item => item.name === name).id);
  const values = sheet.getRange(`A4:${columnName(definition.headers.length - 1)}${definition.rows.length + 4}`).values;
  if (JSON.stringify(values) !== JSON.stringify(storedTableValues(definition))) throw new Error(`Saved table values differ: ${filename} / ${name}`);
}
console.log(`${filename}: updated ${changed.size} sheets; preserved ${existing.length - changed.size} other sheets; reopened successfully.`);
