import type { GenerateResult, SelectionCounts, Vip, ValidationResult } from "../api/types";

// docx + file-saver are only pulled into a JS chunk when this function
// actually runs (dynamic import below), instead of bloating the app's main
// bundle for every user who never clicks "Download SOP".

export async function exportSopDocument(params: {
  sessionName: string;
  selectedVips: Vip[];
  kpis: SelectionCounts | undefined;
  validation: ValidationResult | null;
  generated: GenerateResult | null;
  outputMode: string;
}) {
  const { sessionName, selectedVips, kpis, validation, generated, outputMode } = params;
  const [docx, { saveAs }] = await Promise.all([import("docx"), import("file-saver")]);
  const { BorderStyle, Document, HeadingLevel, Packer, Paragraph, ShadingType, Table, TableCell, TableRow, TextRun, WidthType } = docx;

  const CELL_BORDER = { style: BorderStyle.SINGLE, size: 4, color: "CBD5E1" };
  const BORDERS = { top: CELL_BORDER, bottom: CELL_BORDER, left: CELL_BORDER, right: CELL_BORDER };

  const headerCell = (text: string) =>
    new TableCell({
      borders: BORDERS,
      shading: { type: ShadingType.SOLID, color: "1F2C3A", fill: "1F2C3A" },
      children: [new Paragraph({ children: [new TextRun({ text, bold: true, color: "FFFFFF", size: 20 })] })],
    });

  const cell = (text: string) =>
    new TableCell({ borders: BORDERS, children: [new Paragraph({ children: [new TextRun({ text: text || "—", size: 20 })] })] });

  const h = (text: string, level: (typeof HeadingLevel)[keyof typeof HeadingLevel] = HeadingLevel.HEADING_2) =>
    new Paragraph({ text, heading: level, spacing: { before: 300, after: 150 } });

  const p = (text: string) => new Paragraph({ children: [new TextRun({ text, size: 22 })], spacing: { after: 120 } });

  const checklistItem = (text: string) => new Paragraph({ text: `☐  ${text}`, spacing: { after: 80 } });

  const now = new Date().toLocaleString();
  const isFullRecreate = outputMode === "full_recreate";
  const tmshLines = (generated?.tmsh ?? "").split("\n").filter(Boolean);

  const doc = new Document({
    sections: [
      {
        children: [
          new Paragraph({
            children: [new TextRun({ text: "F5 BIG-IP Migration — Standard Operating Procedure", bold: true, size: 36 })],
            spacing: { after: 100 },
          }),
          new Paragraph({
            children: [new TextRun({ text: `Session: ${sessionName}  |  Generated: ${now}`, size: 20, color: "64748B" })],
            spacing: { after: 400 },
          }),

          h("1. Overview", HeadingLevel.HEADING_1),
          p(
            `This document describes the steps to migrate ${kpis?.vips ?? selectedVips.length} virtual server(s) ` +
              `using the "${isFullRecreate ? "Full recreate for a new device" : "Apply changes to existing objects"}" mode. ` +
              `${isFullRecreate
                ? "The target device does not yet have these objects — the commands below create the full dependency chain (monitors, nodes, pools, virtual servers) from scratch."
                : "The target device already has these objects — the commands below modify only the fields that changed."
              }`,
          ),
          new Table({
            width: { size: 100, type: WidthType.PERCENTAGE },
            rows: [
              new TableRow({ children: [headerCell("Metric"), headerCell("Count")] }),
              new TableRow({ children: [cell("VIPs selected"), cell(String(kpis?.vips ?? selectedVips.length))] }),
              new TableRow({ children: [cell("Pools"), cell(String(kpis?.pools ?? ""))] }),
              new TableRow({ children: [cell("Pool members"), cell(String(kpis?.pool_members ?? ""))] }),
              new TableRow({ children: [cell("Nodes"), cell(String(kpis?.nodes ?? ""))] }),
              new TableRow({ children: [cell("VLAN references"), cell(String(kpis?.vlan_refs ?? ""))] }),
              new TableRow({ children: [cell("Validation status"), cell(validation?.overall ?? "not run")] }),
            ],
          }),

          h("2. Pre-Migration Checklist", HeadingLevel.HEADING_1),
          checklistItem("Take a fresh UCS backup of the source (and target, if different) BIG-IP device."),
          checklistItem("Confirm the maintenance window and notify affected application owners."),
          checklistItem("Confirm target device connectivity (SSH / mgmt) and TMOS version compatibility."),
          checklistItem(
            isFullRecreate
              ? "Confirm the target partition (Common) is clean of naming conflicts for the objects listed in Section 4."
              : "Confirm every node/pool/virtual referenced below already exists on the target device.",
          ),
          checklistItem("If any VLAN referenced below is externally managed (F5OS/rSeries), confirm it already exists on the target — this tool does not create it unless explicitly enabled."),
          checklistItem("Review the Validation Results in Section 3 — do not proceed if the overall status is BLOCKED."),

          h("3. Validation Results", HeadingLevel.HEADING_1),
          ...(validation
            ? [
                new Table({
                  width: { size: 100, type: WidthType.PERCENTAGE },
                  rows: [
                    new TableRow({ children: [headerCell("Check"), headerCell("Severity"), headerCell("Details")] }),
                    ...validation.checks.map(
                      (c) =>
                        new TableRow({
                          children: [cell(c.label), cell(c.severity.toUpperCase()), cell(c.details)],
                        }),
                    ),
                  ],
                }),
                new Paragraph({
                  children: [new TextRun({ text: `Overall status: ${validation.overall}`, bold: true, size: 22 })],
                  spacing: { before: 150, after: 150 },
                }),
              ]
            : [p("Validation was not run before this document was generated. Run Validate in Step 5 first.")]),

          h("4. Migration Steps", HeadingLevel.HEADING_1),
          p("Execute the following on the target device via tmsh, in order. Each command has already been ordered so dependencies (nodes → pools → virtual servers) are created before anything that references them."),
          ...(tmshLines.length
            ? tmshLines.map((line, i) => new Paragraph({ text: `${i + 1}. ${line}`, spacing: { after: 100 } }))
            : [p("No commands were generated for this selection — see the Generate step for details.")]),
          p("After running the commands above:"),
          checklistItem("Confirm each virtual server shows a green (Available) status in the GUI or via `tmsh show ltm virtual`."),
          checklistItem("Run a smoke test against each migrated VIP's destination address/port."),
          checklistItem("Save the running configuration: `tmsh save sys config`."),

          h("5. Rollback Plan", HeadingLevel.HEADING_1),
          p(
            "This tool does not currently auto-generate a rollback script. If an issue is found post-migration, " +
              "restore the pre-migration UCS backup taken in Section 2, or manually revert the specific objects " +
              "listed in Section 4 to their prior values (visible in the source session's VIP/Pool/Node pages).",
          ),

          h("6. Sign-off", HeadingLevel.HEADING_1),
          new Table({
            width: { size: 100, type: WidthType.PERCENTAGE },
            rows: [
              new TableRow({ children: [headerCell("Role"), headerCell("Name"), headerCell("Date"), headerCell("Signature")] }),
              new TableRow({ children: [cell("Prepared by"), cell(""), cell(""), cell("")] }),
              new TableRow({ children: [cell("Reviewed by"), cell(""), cell(""), cell("")] }),
              new TableRow({ children: [cell("Approved by"), cell(""), cell(""), cell("")] }),
            ],
          }),
        ],
      },
    ],
  });

  const blob = await Packer.toBlob(doc);
  saveAs(blob, `${sessionName || "migration"}-SOP.docx`);
}
