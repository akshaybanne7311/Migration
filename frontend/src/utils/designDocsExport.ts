import { api } from "../api/client";
import type { GenerateResult, MigrationPlan, SelectionCounts, ValidationResult, Vip } from "../api/types";

// docx + file-saver are only pulled into a JS chunk when one of these
// functions actually runs, same lazy-import pattern as sopExport.ts.

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

async function loadDocx() {
  const [docx, { saveAs }] = await Promise.all([import("docx"), import("file-saver")]);
  const { BorderStyle, Document, HeadingLevel, Packer, Paragraph, ShadingType, Table, TableCell, TableRow, TextRun, WidthType } = docx;
  const CELL_BORDER = { style: BorderStyle.SINGLE, size: 4, color: "CBD5E1" };
  const BORDERS = { top: CELL_BORDER, bottom: CELL_BORDER, left: CELL_BORDER, right: CELL_BORDER };
  const headerCell = (t: string) =>
    new TableCell({
      borders: BORDERS,
      shading: { type: ShadingType.SOLID, color: "1F2C3A", fill: "1F2C3A" },
      children: [new Paragraph({ children: [new TextRun({ text: t, bold: true, color: "FFFFFF", size: 20 })] })],
    });
  const cell = (t: string) =>
    new TableCell({ borders: BORDERS, children: [new Paragraph({ children: [new TextRun({ text: t || "—", size: 20 })] })] });
  const h = (t: string, level: (typeof HeadingLevel)[keyof typeof HeadingLevel] = HeadingLevel.HEADING_2) =>
    new Paragraph({ text: t, heading: level, spacing: { before: 300, after: 150 } });
  const p = (t: string) => new Paragraph({ children: [new TextRun({ text: t, size: 22 })], spacing: { after: 120 } });
  const table = (headers: string[], rows: string[][]) =>
    new Table({
      width: { size: 100, type: WidthType.PERCENTAGE },
      rows: [new TableRow({ children: headers.map(headerCell) }), ...rows.map((r) => new TableRow({ children: r.map(cell) }))],
    });
  return { Document, HeadingLevel, Packer, Paragraph, TextRun, saveAs, h, p, table };
}

/** High-Level Design: source environment architecture, scope, and risk --
 * session-scoped, doesn't need a migration plan. Fetches its own data the
 * same way the full session Excel export does. */
export async function exportHldDocument(params: { sessionId: string; sessionName: string }) {
  const { sessionId, sessionName } = params;
  const [vips, pools, nodes, vlans, systemObjects, healthCheck] = await Promise.all([
    api.listVips(sessionId),
    api.listPools(sessionId),
    api.listNodes(sessionId),
    api.listVlans(sessionId),
    api.listSystemObjects(sessionId),
    api.runHealthCheck(sessionId).catch(() => null),
  ]);
  const { Document, HeadingLevel, Packer, Paragraph, TextRun, saveAs, h, p, table } = await loadDocx();

  const byType = (t: string) => systemObjects.items.filter((o) => o.object_type === t);
  const license = byType("sys license").find((o) => o.name === "current");
  const licenseEntries = license ? entries(license.entries_json) : {};
  const version = byType("sys software-version")[0];
  const versionEntries = version ? entries(version.entries_json) : {};
  const platform = byType("sys platform")[0];
  const platformEntries = platform ? entries(platform.entries_json) : {};
  const device = byType("cm device")[0];
  const deviceEntries = device ? entries(device.entries_json) : {};
  const haGroups = byType("cm device-group");
  const selfIps = byType("net self");
  const trunks = byType("net trunk");
  const routes = byType("net route");
  const certs = byType("x509 certificate");
  const expiredCerts = certs.filter((c) => entries(c.entries_json).is_expired);

  const now = new Date().toLocaleString();

  const doc = new Document({
    sections: [
      {
        children: [
          new Paragraph({
            children: [new TextRun({ text: "High-Level Design (HLD) — Network Device Migration", bold: true, size: 36 })],
            spacing: { after: 100 },
          }),
          new Paragraph({
            children: [new TextRun({ text: `Session: ${sessionName}  |  Generated: ${now}`, size: 20, color: "64748B" })],
            spacing: { after: 400 },
          }),

          h("1. Executive Summary", HeadingLevel.HEADING_1),
          p(
            `This document describes the current-state architecture of ${sessionName} as recovered from its UCS/QKView ` +
              `archive, the scope of a proposed migration, and the risks identified against it. It is the architecture-level ` +
              `companion to the Low-Level Design (LLD), which details the field-by-field object changes for a specific plan.`,
          ),

          h("2. Source Environment", HeadingLevel.HEADING_1),
          table(
            ["Property", "Value"],
            [
              ["Hostname", text(deviceEntries.hostname) || "not parsed"],
              ["Software Version", `${text(versionEntries.product)} ${text(versionEntries.version)} (build ${text(versionEntries.build)})`],
              ["Edition", text(versionEntries.edition) || "—"],
              ["Platform ID", text(platformEntries.platform) || text(licenseEntries.platform_id) || "not parsed"],
              ["License Usage", text(licenseEntries.usage) || "not parsed"],
              ["Licensed Modules", text(licenseEntries.active_modules) || "not parsed"],
              ["Licensed Date", text(licenseEntries.licensed_date) || "—"],
              ["HA Device Groups", String(haGroups.length)],
            ],
          ),

          h("3. Current-State Network Topology", HeadingLevel.HEADING_1),
          p("Counts below are of objects actually parsed from the source archive -- not estimates."),
          table(
            ["Object", "Count"],
            [
              ["Virtual Servers", String(vips.total)],
              ["Pools", String(pools.total)],
              ["Nodes", String(nodes.total)],
              ["VLANs", String(vlans.total)],
              ["Self IPs", String(selfIps.length)],
              ["Trunks", String(trunks.length)],
              ["Static Routes", String(routes.length)],
              ["SSL Certificates", String(certs.length)],
            ],
          ),

          h("4. Scope of Migration", HeadingLevel.HEADING_1),
          p(
            "Scope (which VIPs, and what changes to each) is defined per migration plan in the Smart Migration wizard. " +
              "This HLD covers the full source environment; see the accompanying LLD for the specific object set and " +
              "field-level changes of a given plan.",
          ),

          h("5. Risk Assessment", HeadingLevel.HEADING_1),
          ...(healthCheck
            ? [
                p(`Automated health check overall status: ${healthCheck.overall}.`),
                table(
                  ["Risk", "Severity", "Detail"],
                  healthCheck.checks
                    .filter((c) => c.severity !== "pass")
                    .map((c) => [c.label, c.severity.toUpperCase(), c.details]),
                ),
              ]
            : [p("Health check was not available when this document was generated.")]),
          ...(expiredCerts.length
            ? [p(`${expiredCerts.length} certificate(s) parsed from this archive are already expired -- see Section 2 of the full session Excel export for detail.`)]
            : []),

          h("6. Assumptions & Constraints", HeadingLevel.HEADING_1),
          p("- Target device is assumed to be running a compatible or newer TMOS version than the source (see Section 2)."),
          p("- Any externally-managed VLAN referenced by a migrated object is assumed to already exist on the target unless network object creation is explicitly enabled in the plan."),
          p("- License entitlement on the target must cover the modules listed in Section 2 for full feature parity."),
          p("- This document reflects a point-in-time snapshot of the source archive; the live device may have changed since capture."),

          h("7. High-Level Migration Approach", HeadingLevel.HEADING_1),
          p("Phase 1 — Discovery & Validation: parse and validate the source config (this tool), reconcile against the target environment."),
          p("Phase 2 — Planning: build a migration plan in Smart Migration (selected VIPs, field changes, node re-mapping), produce the LLD."),
          p("Phase 3 — Execution: run the generated tmsh/REST/AS3/Ansible output against the target in a maintenance window, per the SOP."),
          p("Phase 4 — Verification: confirm object availability and smoke-test traffic, per the SOP's post-migration checklist."),
        ],
      },
    ],
  });

  const blob = await Packer.toBlob(doc);
  saveAs(blob, `${sessionName || "session"}-HLD.docx`);
}

/** Low-Level Design: field-by-field object mapping for one specific
 * migration plan -- old value -> new value, exactly what the plan will
 * change, plus every generated command format. Plan-scoped, mirrors the
 * SOP's inputs (called from the same place, Step 5). */
export async function exportLldDocument(params: {
  sessionName: string;
  plan: MigrationPlan;
  vipsByName: Map<string, Vip>;
  kpis: SelectionCounts | undefined;
  validation: ValidationResult | null;
  generated: GenerateResult | null;
}) {
  const { sessionName, plan, vipsByName, kpis, validation, generated } = params;
  const { Document, HeadingLevel, Packer, Paragraph, TextRun, saveAs, h, p, table } = await loadDocx();

  const now = new Date().toLocaleString();
  const CHANGE_TYPE_LABEL: Record<string, string> = {
    vip_name: "Virtual Server Name",
    vip_ip_port: "Destination Address / Port",
    pool_name: "Pool Name",
    pool_members: "Pool Members",
    vlans: "VLANs",
    profiles: "Profiles",
    persistence: "Persistence Profile",
    monitor: "Health Monitor",
  };

  const memberRefText = (r: { node_name?: string | null; address?: string | null; port: number; new_node_name?: string | null; remove_node?: boolean }) =>
    `${r.new_node_name ?? r.node_name ?? r.address ?? "?"}:${r.port}${r.remove_node ? " (removed)" : ""}`;

  const doc = new Document({
    sections: [
      {
        children: [
          new Paragraph({
            children: [new TextRun({ text: "Low-Level Design (LLD) — Migration Plan", bold: true, size: 36 })],
            spacing: { after: 100 },
          }),
          new Paragraph({
            children: [new TextRun({ text: `Session: ${sessionName}  |  Generated: ${now}`, size: 20, color: "64748B" })],
            spacing: { after: 400 },
          }),

          h("1. Object Scope", HeadingLevel.HEADING_1),
          table(
            ["Metric", "Count"],
            [
              ["Virtual Servers in scope", String(kpis?.vips ?? plan.selected_vips.length)],
              ["Pools affected", String(kpis?.pools ?? "")],
              ["Pool members affected", String(kpis?.pool_members ?? "")],
              ["Nodes affected", String(kpis?.nodes ?? "")],
              ["Output mode", plan.output_mode === "full_recreate" ? "Full recreate for a new device" : "Apply changes to existing objects"],
              ["Validation status", validation?.overall ?? "not run"],
            ],
          ),

          h("2. Virtual Servers In Scope", HeadingLevel.HEADING_1),
          table(
            ["VIP", "Current Destination", "Current Pool", "Current Persistence"],
            plan.selected_vips.map((name) => {
              const v = vipsByName.get(name);
              return [
                name.replace("/Common/", ""),
                v ? `${v.destination_address}:${v.destination_port}` : "not found in session",
                v?.pool_name?.replace("/Common/", "") ?? "—",
                v?.persistence?.replace("/Common/", "") ?? "—",
              ];
            }),
          ),

          h("3. Common Changes (applied to every VIP above, unless overridden in Section 4)", HeadingLevel.HEADING_1),
          plan.common_changes.length
            ? table(
                ["Field", "New Value"],
                plan.common_changes.map((c) => [CHANGE_TYPE_LABEL[c.change_type] ?? c.change_type, text(c.payload)]),
              )
            : p("No common changes configured -- either this plan only touches node/pool-member mappings below, or it's a full-recreate with no field overrides."),

          h("4. Per-VIP Exceptions", HeadingLevel.HEADING_1),
          ...(plan.exceptions.length ? [] : [p("No per-VIP exceptions configured.")]),
          ...plan.exceptions.flatMap((ex) => [
            h(ex.vip_name.replace("/Common/", ""), HeadingLevel.HEADING_3),
            table(
              ["Field", "Override Value"],
              Object.entries(ex.overrides).map(([field, payload]) => [CHANGE_TYPE_LABEL[field] ?? field, text(payload)]),
            ),
          ]),

          h("5. Node Re-mapping", HeadingLevel.HEADING_1),
          plan.node_changes.length
            ? table(
                ["Old Node", "New IP Address", "New Node Name"],
                plan.node_changes.map((n) => [n.old_node_ref.replace("/Common/", ""), n.new_ip, n.new_node_name ?? "(unchanged)"]),
              )
            : p("No node IP re-mapping configured for this plan."),

          h("6. Pool Member Edits", HeadingLevel.HEADING_1),
          plan.pool_member_edits.length
            ? table(
                ["Pool", "Action", "Old Members", "New Members"],
                plan.pool_member_edits.map((e) => [
                  e.vip_name.replace("/Common/", ""),
                  e.action,
                  e.old_refs.map(memberRefText).join(", ") || "—",
                  e.new_refs.map(memberRefText).join(", ") || "—",
                ]),
              )
            : p("No pool member edits configured for this plan."),

          h("7. Generated Commands", HeadingLevel.HEADING_1),
          p("Every output format this tool generated for this exact plan, in execution order."),
          h("7.1 tmsh", HeadingLevel.HEADING_3),
          ...(generated?.tmsh.split("\n").filter(Boolean).map((line, i) => p(`${i + 1}. ${line}`)) ?? [p("Not generated.")]),
          h("7.2 iControl REST", HeadingLevel.HEADING_3),
          generated?.rest.length
            ? table(["Method", "Path", "Body"], generated.rest.map((c) => [c.method, c.path, JSON.stringify(c.body)]))
            : p("Not generated."),
          h("7.3 AS3", HeadingLevel.HEADING_3),
          p(generated?.as3 ? "See the JSON declaration in the Generate step or the Excel plan export -- omitted here for length." : "Not generated."),
          h("7.4 Ansible", HeadingLevel.HEADING_3),
          p(generated?.ansible ? "See the Ansible tab in the Generate step or the Excel plan export -- omitted here for length." : "Not generated."),

          h("8. Per-Object Validation Criteria", HeadingLevel.HEADING_1),
          p("After execution, confirm for each VIP in Section 2: object exists on target with the field values from Sections 3-4, shows Available status, and passes a smoke test against its destination address/port."),
        ],
      },
    ],
  });

  const blob = await Packer.toBlob(doc);
  saveAs(blob, `${sessionName || "session"}-LLD.docx`);
}
