import type ExcelJS from "exceljs";
import { api } from "../api/client";
import type { SystemObject } from "../api/types";

// exceljs + file-saver are only pulled into a JS chunk when this function
// actually runs (dynamic import below), same pattern as excelExport.ts.

const HEADER_FILL: ExcelJS.Fill = { type: "pattern", pattern: "solid", fgColor: { argb: "FF1F2C3A" } };
const HEADER_FONT: Partial<ExcelJS.Font> = { color: { argb: "FFFFFFFF" }, bold: true };

// Excel's hard per-cell character limit is 32,767 -- a real config diff or
// raw stanza dump can exceed that on a device with a large config, so every
// long-text cell is capped here rather than letting exceljs silently
// truncate (or error) deep inside the write.
const CELL_TEXT_LIMIT = 30000;
function clip(text: string): string {
  return text.length > CELL_TEXT_LIMIT ? `${text.slice(0, CELL_TEXT_LIMIT)}\n...[truncated for Excel's cell size limit]` : text;
}

function styleHeaderRow(row: ExcelJS.Row) {
  row.eachCell((cell) => {
    cell.fill = HEADER_FILL;
    cell.font = HEADER_FONT;
    cell.alignment = { vertical: "middle" };
  });
}

function entries(json: string): Record<string, unknown> {
  try {
    const parsed = JSON.parse(json);
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

function text(v: unknown): string {
  if (v === null || v === undefined) return "";
  if (typeof v === "string") return v;
  if (Array.isArray(v)) return v.join(", ");
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

function addSystemObjectSheet(wb: ExcelJS.Workbook, title: string, objects: SystemObject[]) {
  if (objects.length === 0) return;
  const sheet = wb.addWorksheet(title.slice(0, 31));
  const keySet = new Set<string>();
  const parsedEntries = objects.map((o) => entries(o.entries_json));
  for (const e of parsedEntries) for (const k of Object.keys(e)) keySet.add(k);
  const keys = Array.from(keySet);
  sheet.columns = [
    { header: "Object Type", key: "object_type", width: 26 },
    { header: "Name", key: "name", width: 34 },
    ...keys.map((k) => ({ header: k, key: k, width: 28 })),
  ];
  styleHeaderRow(sheet.getRow(1));
  objects.forEach((o, i) => {
    const row: Record<string, string> = { object_type: o.object_type, name: o.name };
    for (const k of keys) row[k] = clip(text(parsedEntries[i][k]));
    sheet.addRow(row);
  });
}

export async function exportFullSessionToExcel(params: { sessionId: string; sessionName: string }) {
  const { sessionId, sessionName } = params;
  const [{ default: ExcelJSRuntime }, { saveAs }] = await Promise.all([import("exceljs"), import("file-saver")]);

  const [vips, pools, nodes, vlans, monitors, systemObjects, commandHistory, configRevisions, healthCheck] = await Promise.all([
    api.listVips(sessionId),
    api.listPools(sessionId),
    api.listNodes(sessionId),
    api.listVlans(sessionId),
    api.listMonitors(sessionId),
    api.listSystemObjects(sessionId),
    api.listCommandHistory(sessionId, { mutatingOnly: false }).catch(() => ({ items: [], total: 0, total_all: 0 })),
    api.listConfigRevisions(sessionId).catch(() => ({ items: [], total: 0, total_all: 0, config_files: [] })),
    api.runHealthCheck(sessionId).catch(() => null),
  ]);

  const wb = new ExcelJSRuntime.Workbook();
  wb.creator = "Config Intelligence";
  wb.created = new Date();

  // --- Summary ---
  const summary = wb.addWorksheet("Summary");
  summary.columns = [
    { header: "Field", key: "field", width: 30 },
    { header: "Value", key: "value", width: 60 },
  ];
  styleHeaderRow(summary.getRow(1));
  summary.addRows([
    { field: "Session", value: sessionName },
    { field: "Exported at", value: new Date().toLocaleString() },
    { field: "Virtual Servers", value: vips.total },
    { field: "Pools", value: pools.total },
    { field: "Nodes", value: nodes.total },
    { field: "VLANs", value: vlans.total },
    { field: "Monitors", value: monitors.total },
    { field: "System objects (self IPs, certs, license, HA, ...)", value: systemObjects.total },
    { field: "Command history entries (all, incl. read-only)", value: commandHistory.total_all },
    { field: "Config revisions (per-save diffs)", value: configRevisions.total_all },
    { field: "Health check result", value: healthCheck ? healthCheck.overall : "not available" },
  ]);
  summary.addRow({});
  summary.addRow({ field: "Note", value: "Command history and config diffs below have passwords/secrets redacted -- this export never contains plaintext credentials, private keys, or shadow/passwd data, matching what the app itself will and won't show." });

  // --- Virtual Servers ---
  const vipSheet = wb.addWorksheet("Virtual Servers");
  vipSheet.columns = [
    { header: "Name", key: "name", width: 40 },
    { header: "Partition", key: "partition", width: 12 },
    { header: "Destination", key: "dest", width: 20 },
    { header: "Port", key: "port", width: 8 },
    { header: "Address Family", key: "af", width: 12 },
    { header: "Route Domain", key: "rd", width: 12 },
    { header: "Protocol", key: "proto", width: 10 },
    { header: "Pool", key: "pool", width: 40 },
    { header: "VLANs", key: "vlans", width: 30 },
    { header: "VLANs Enabled", key: "vlans_enabled", width: 12 },
    { header: "Profiles", key: "profiles", width: 40 },
    { header: "Persistence", key: "persist", width: 24 },
    { header: "SNAT", key: "snat", width: 14 },
    { header: "iRules", key: "irules", width: 30 },
    { header: "Mask", key: "mask", width: 16 },
    { header: "Monitors", key: "monitors", width: 30 },
  ];
  styleHeaderRow(vipSheet.getRow(1));
  for (const v of vips.items) {
    vipSheet.addRow({
      name: v.name,
      partition: v.partition,
      dest: v.destination_address,
      port: v.destination_port,
      af: v.address_family,
      rd: v.route_domain ?? "",
      proto: v.ip_protocol ?? "",
      pool: v.pool_name ?? "",
      vlans: v.vlans.join(", "),
      vlans_enabled: v.vlans_enabled,
      profiles: v.profiles.map((p) => p.name).join(", "),
      persist: v.persistence ?? "",
      snat: v.snat_type ?? "",
      irules: v.irules.join(", "),
      mask: v.mask ?? "",
      monitors: v.monitor_names.join(", "),
    });
  }

  // --- Pools + members (one row per member) ---
  const poolSheet = wb.addWorksheet("Pools & Members");
  poolSheet.columns = [
    { header: "Pool", key: "pool", width: 40 },
    { header: "Partition", key: "partition", width: 12 },
    { header: "Monitors", key: "monitors", width: 30 },
    { header: "Member Node", key: "node", width: 40 },
    { header: "Member Port", key: "port", width: 12 },
    { header: "Session State", key: "state", width: 16 },
    { header: "Connection Limit", key: "connlimit", width: 16 },
  ];
  styleHeaderRow(poolSheet.getRow(1));
  for (const p of pools.items) {
    if (p.members.length === 0) {
      poolSheet.addRow({ pool: p.name, partition: p.partition, monitors: p.monitor_names.join(", "), node: "", port: "", state: "", connlimit: "" });
      continue;
    }
    for (const m of p.members) {
      poolSheet.addRow({
        pool: p.name,
        partition: p.partition,
        monitors: p.monitor_names.join(", "),
        node: m.node_name,
        port: m.port,
        state: m.session_state ?? "",
        connlimit: m.connection_limit ?? "",
      });
    }
  }

  // --- Nodes ---
  const nodeSheet = wb.addWorksheet("Nodes");
  nodeSheet.columns = [
    { header: "Name", key: "name", width: 40 },
    { header: "Address", key: "address", width: 24 },
    { header: "Address Family", key: "af", width: 12 },
    { header: "Partition", key: "partition", width: 12 },
    { header: "State", key: "state", width: 14 },
    { header: "Used by Pools", key: "pool_count", width: 14 },
    { header: "Used by VIPs", key: "vip_count", width: 14 },
  ];
  styleHeaderRow(nodeSheet.getRow(1));
  for (const n of nodes.items) {
    nodeSheet.addRow({
      name: n.name,
      address: n.address,
      af: n.address_family,
      partition: n.partition,
      state: n.state ?? "",
      pool_count: n.pool_count ?? "",
      vip_count: n.vip_count ?? "",
    });
  }

  // --- VLANs ---
  const vlanSheet = wb.addWorksheet("VLANs");
  vlanSheet.columns = [
    { header: "Name", key: "name", width: 30 },
    { header: "Tag", key: "tag", width: 10 },
    { header: "Interfaces", key: "ifaces", width: 30 },
  ];
  styleHeaderRow(vlanSheet.getRow(1));
  for (const v of vlans.items) {
    vlanSheet.addRow({ name: v.name, tag: v.tag ?? "", ifaces: v.interfaces.join(", ") });
  }

  // --- Monitors ---
  const monSheet = wb.addWorksheet("Monitors");
  monSheet.columns = [
    { header: "Name", key: "name", width: 34 },
    { header: "Type", key: "type", width: 16 },
    { header: "Interval (s)", key: "interval", width: 12 },
    { header: "Timeout (s)", key: "timeout", width: 12 },
  ];
  styleHeaderRow(monSheet.getRow(1));
  for (const m of monitors.items) {
    monSheet.addRow({ name: m.name, type: m.monitor_type ?? "", interval: m.interval ?? "", timeout: m.timeout ?? "" });
  }

  // --- System objects, grouped into one sheet per real category present ---
  const objectsByType = new Map<string, SystemObject[]>();
  for (const o of systemObjects.items) {
    if (!objectsByType.has(o.object_type)) objectsByType.set(o.object_type, []);
    objectsByType.get(o.object_type)!.push(o);
  }
  const SHEET_TITLES: [string, string][] = [
    ["net self", "Self IPs"],
    ["net trunk", "Trunks"],
    ["net route", "Static Routes"],
    ["net route-domain", "Route Domains"],
    ["net dns-resolver", "DNS Resolvers"],
    ["x509 certificate", "SSL Certificates"],
    ["sys license", "License"],
    ["sys license-history", "License History"],
    ["sys software-version", "Software Version"],
    ["sys platform", "Platform"],
    ["cm device", "Device Identity"],
    ["cm device-group", "Device Groups (HA)"],
    ["cm traffic-group", "Traffic Groups"],
    ["sys ntp", "NTP"],
    ["sys snmp", "SNMP"],
    ["sys syslog", "Syslog"],
    ["sys management-route", "Management Routes"],
    ["sys provision", "Resource Provisioning"],
  ];
  const handledTypes = new Set(SHEET_TITLES.map(([t]) => t));
  for (const [type, title] of SHEET_TITLES) {
    addSystemObjectSheet(wb, title, objectsByType.get(type) ?? []);
  }
  const profileObjects = systemObjects.items.filter((o) => o.object_type.startsWith("ltm profile ") || o.object_type.startsWith("ltm persistence "));
  addSystemObjectSheet(wb, "Profiles & Persistence", profileObjects);
  for (const t of profileObjects) handledTypes.add(t.object_type);
  const iruleObjects = systemObjects.items.filter((o) => o.object_type === "ltm rule");
  if (iruleObjects.length) {
    const sheet = wb.addWorksheet("iRules");
    sheet.columns = [
      { header: "Name", key: "name", width: 40 },
      { header: "TCL Body", key: "body", width: 120 },
    ];
    styleHeaderRow(sheet.getRow(1));
    for (const r of iruleObjects) {
      sheet.addRow({ name: r.name, body: clip(text(entries(r.entries_json).body ?? entries(r.entries_json))) });
    }
    handledTypes.add("ltm rule");
  }
  const otherTypes = [...objectsByType.keys()].filter((t) => !handledTypes.has(t) && t !== "sys management-ip" && t !== "sys global-settings");
  addSystemObjectSheet(wb, "Other System Objects", otherTypes.flatMap((t) => objectsByType.get(t) ?? []));
  addSystemObjectSheet(wb, "Device Configuration", [...(objectsByType.get("sys global-settings") ?? []), ...(objectsByType.get("sys management-ip") ?? [])]);

  // --- Command history (already server-side redacted) ---
  if (commandHistory.items.length) {
    const sheet = wb.addWorksheet("Change History (Commands)");
    sheet.columns = [
      { header: "Timestamp", key: "ts", width: 20 },
      { header: "User", key: "user", width: 20 },
      { header: "Command", key: "cmd", width: 100 },
      { header: "Config Change?", key: "mutating", width: 14 },
      { header: "Secret Redacted?", key: "secret", width: 16 },
    ];
    styleHeaderRow(sheet.getRow(1));
    for (const e of commandHistory.items) {
      sheet.addRow({ ts: e.timestamp, user: e.user, cmd: clip(e.command), mutating: e.is_mutating ? "Yes" : "No", secret: e.contains_secret ? "Yes" : "No" });
    }
  }

  // --- Config revisions (already server-side redacted) ---
  if (configRevisions.items.length) {
    const sheet = wb.addWorksheet("Change History (Config Diffs)");
    sheet.columns = [
      { header: "Timestamp", key: "ts", width: 20 },
      { header: "Config File", key: "file", width: 20 },
      { header: "Patch #", key: "num", width: 10 },
      { header: "Lines Added", key: "added", width: 12 },
      { header: "Lines Removed", key: "removed", width: 14 },
      { header: "Secret Redacted?", key: "secret", width: 16 },
      { header: "Diff", key: "diff", width: 120 },
    ];
    styleHeaderRow(sheet.getRow(1));
    for (const r of configRevisions.items) {
      sheet.addRow({
        ts: r.timestamp,
        file: r.config_file,
        num: r.patch_number,
        added: r.lines_added,
        removed: r.lines_removed,
        secret: r.contains_secret ? "Yes" : "No",
        diff: clip(r.diff_text),
      });
    }
  }

  // --- Health check ---
  if (healthCheck) {
    const sheet = wb.addWorksheet("Health Check");
    sheet.columns = [
      { header: "Check", key: "label", width: 34 },
      { header: "Severity", key: "severity", width: 12 },
      { header: "Details", key: "details", width: 70 },
      { header: "Affected", key: "affected", width: 60 },
    ];
    styleHeaderRow(sheet.getRow(1));
    for (const c of healthCheck.checks) {
      const row = sheet.addRow({ label: c.label, severity: c.severity.toUpperCase(), details: c.details, affected: c.affected.join(", ") });
      if (c.severity === "blocked") row.getCell("severity").font = { color: { argb: "FFCC0000" }, bold: true };
      else if (c.severity === "warn") row.getCell("severity").font = { color: { argb: "FFB45309" }, bold: true };
      else row.getCell("severity").font = { color: { argb: "FF047857" }, bold: true };
    }
  }

  // --- Index: every sheet this workbook actually ended up with, as a
  // clickable jump list -- built last since sheets like the system-object
  // categories are only added conditionally when the archive had that
  // object type, so the final sheet list isn't known until now. A "Back
  // to Index" link is added to the top-left of every other sheet so
  // there's a way back without using Excel's own sheet tabs. ---
  const dataSheets = wb.worksheets.filter((ws) => ws.name !== "Summary");
  summary.addRow({});
  const indexHeaderRow = summary.addRow({ field: "Sheet Index", value: `${dataSheets.length} sheets` });
  indexHeaderRow.getCell("field").font = { bold: true, size: 13 };
  for (const ws of dataSheets) {
    const rowCount = ws.rowCount > 0 ? ws.rowCount - 1 : 0; // exclude header row
    const row = summary.addRow({ field: ws.name, value: `${rowCount} row${rowCount === 1 ? "" : "s"}` });
    const linkCell = row.getCell("field");
    linkCell.value = { text: ws.name, hyperlink: `#'${ws.name}'!A1` };
    linkCell.font = { color: { argb: "FF2563A6" }, underline: true };

    ws.spliceRows(1, 0, []); // push the real header row down one, so the back-link gets its own row
    ws.getCell("A1").value = { text: "◂ Back to Index", hyperlink: "#Summary!A1" };
    ws.getCell("A1").font = { color: { argb: "FF2563A6" }, underline: true, italic: true, size: 10 };
  }

  const buffer = await wb.xlsx.writeBuffer();
  saveAs(
    new Blob([buffer], { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" }),
    `${sessionName || "session"}-full-export.xlsx`,
  );
}
