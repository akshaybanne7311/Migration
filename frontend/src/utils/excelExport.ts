import type ExcelJS from "exceljs";
import type { GenerateResult, SelectionCounts, Vip, ValidationResult } from "../api/types";

// exceljs + file-saver are only pulled into a JS chunk when this function
// actually runs (dynamic import below), instead of bloating the app's main
// bundle for every user who never clicks an export button.

const HEADER_FILL: ExcelJS.Fill = { type: "pattern", pattern: "solid", fgColor: { argb: "FF1F2C3A" } };
const HEADER_FONT: Partial<ExcelJS.Font> = { color: { argb: "FFFFFFFF" }, bold: true };

function styleHeaderRow(row: ExcelJS.Row) {
  row.eachCell((cell) => {
    cell.fill = HEADER_FILL;
    cell.font = HEADER_FONT;
    cell.alignment = { vertical: "middle" };
  });
}

export async function exportMigrationPlanToExcel(params: {
  sessionName: string;
  selectedVips: Vip[];
  kpis: SelectionCounts | undefined;
  validation: ValidationResult | null;
  generated: GenerateResult | null;
  outputMode: string;
}) {
  const { sessionName, selectedVips, kpis, validation, generated, outputMode } = params;
  const [{ default: ExcelJSRuntime }, { saveAs }] = await Promise.all([import("exceljs"), import("file-saver")]);

  const wb = new ExcelJSRuntime.Workbook();
  wb.creator = "Config Intelligence";
  wb.created = new Date();

  const summary = wb.addWorksheet("Summary");
  summary.columns = [
    { header: "Field", key: "field", width: 28 },
    { header: "Value", key: "value", width: 50 },
  ];
  styleHeaderRow(summary.getRow(1));
  summary.addRows([
    { field: "Session", value: sessionName },
    { field: "Generated at", value: new Date().toLocaleString() },
    { field: "Output mode", value: outputMode === "full_recreate" ? "Full recreate for a new device" : "Apply changes to existing objects" },
    { field: "VIPs selected", value: kpis?.vips ?? selectedVips.length },
    { field: "Pools", value: kpis?.pools ?? "" },
    { field: "Pool members", value: kpis?.pool_members ?? "" },
    { field: "Nodes", value: kpis?.nodes ?? "" },
    { field: "VLAN references", value: kpis?.vlan_refs ?? "" },
    { field: "Validation status", value: validation?.overall ?? "not run" },
  ]);

  const vipsSheet = wb.addWorksheet("Selected VIPs");
  vipsSheet.columns = [
    { header: "VIP Name", key: "name", width: 40 },
    { header: "Destination", key: "dest", width: 24 },
    { header: "Port", key: "port", width: 8 },
    { header: "Protocol", key: "proto", width: 10 },
    { header: "Pool", key: "pool", width: 40 },
    { header: "VLANs", key: "vlans", width: 30 },
    { header: "Persistence", key: "persist", width: 20 },
    { header: "SNAT", key: "snat", width: 14 },
  ];
  styleHeaderRow(vipsSheet.getRow(1));
  for (const v of selectedVips) {
    vipsSheet.addRow({
      name: v.name,
      dest: v.destination_address,
      port: v.destination_port,
      proto: v.ip_protocol ?? "",
      pool: v.pool_name ?? "",
      vlans: v.vlans.join(", "),
      persist: v.persistence ?? "",
      snat: v.snat_type ?? "",
    });
  }

  if (validation) {
    const valSheet = wb.addWorksheet("Validation");
    valSheet.columns = [
      { header: "Check", key: "label", width: 24 },
      { header: "Severity", key: "severity", width: 12 },
      { header: "Details", key: "details", width: 60 },
      { header: "Affected", key: "affected", width: 50 },
    ];
    styleHeaderRow(valSheet.getRow(1));
    for (const c of validation.checks) {
      const row = valSheet.addRow({
        label: c.label,
        severity: c.severity.toUpperCase(),
        details: c.details,
        affected: c.affected.join(", "),
      });
      if (c.severity === "blocked") row.getCell("severity").font = { color: { argb: "FFCC0000" }, bold: true };
      else if (c.severity === "warn") row.getCell("severity").font = { color: { argb: "FFB45309" }, bold: true };
      else row.getCell("severity").font = { color: { argb: "FF047857" }, bold: true };
    }
  }

  if (generated?.rest?.length) {
    const restSheet = wb.addWorksheet("Changes (from REST plan)");
    restSheet.columns = [
      { header: "Method", key: "method", width: 10 },
      { header: "Path", key: "path", width: 45 },
      { header: "Body", key: "body", width: 90 },
    ];
    styleHeaderRow(restSheet.getRow(1));
    for (const call of generated.rest) {
      restSheet.addRow({ method: call.method, path: call.path, body: JSON.stringify(call.body) });
    }
  }

  if (generated?.tmsh) {
    const tmshSheet = wb.addWorksheet("Generated TMSH");
    tmshSheet.columns = [{ header: "Command", key: "cmd", width: 140 }];
    styleHeaderRow(tmshSheet.getRow(1));
    for (const line of generated.tmsh.split("\n").filter(Boolean)) {
      tmshSheet.addRow({ cmd: line });
    }
  }

  const buffer = await wb.xlsx.writeBuffer();
  saveAs(new Blob([buffer], { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" }), `${sessionName || "migration"}-plan.xlsx`);
}
