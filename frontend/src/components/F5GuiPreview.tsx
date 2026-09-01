import { useState } from "react";
import { createPortal } from "react-dom";
import { api } from "../api/client";
import type { NodeObj, Pool, Vip } from "../api/types";
import { toast } from "./toastStore";

/** Recreates the look of the F5 BIG-IP Configuration Utility (TMUI) so an
 * engineer can visually sanity-check what a parsed VIP looks like in the
 * real admin console, without needing access to a live device -- and lets
 * them edit fields right here and see the real TMSH command for that edit.
 *
 * The edit -> TMSH step never reimplements the change engine's field
 * resolution on the frontend (that would be a second, driftable copy of
 * logic that already exists and is tested server-side). Instead an edit
 * here builds the exact same MigrationPlan shape the wizard's Step 3/5
 * produce, for this one VIP, and round-trips it through the real
 * create-plan / validate / generate API calls -- so the TMSH shown is
 * never a guess, it's the same backend that generates everything else in
 * this app. Not a pixel-exact clone, and not affiliated with F5, Inc. */

// This mockup must always render as a real (light) F5 console -- never
// reactive to the host app's own dark/light theme toggle. Every color
// below is applied via inline `style`, not a plain Tailwind utility class
// (e.g. never `text-slate-600` / `bg-white`) -- the app's global CSS
// reskin (src/index.css) targets exactly those literal class names, and
// pairing one of them with an inline F5-palette background silently broke
// contrast (light-themed override text landing on a light inline
// background, or vice versa) wherever only one side of a pair got caught.
const F5 = {
  bar: "#14181f",
  navy: "#1f2c3a",
  navyActive: "#0c5c8c",
  breadcrumb: "#eef1f4",
  sectionHead: "#3c5064",
  border: "#c9d2db",
  rowAlt: "#f4f6f8",
  link: "#0b5fa5",
  green: "#3aa757",
  gray: "#8a8f96",
  white: "#ffffff",
  textLabel: "#64748b",
  textValue: "#0f172a",
  textMuted: "#94a3b8",
  textDim: "#8a94a3",
};

interface EditableFields {
  name: string;
  destinationAddress: string;
  destinationPort: string;
  poolName: string;
  vlan: string;
  persistence: string;
}

function fieldsFromVip(vip: Vip): EditableFields {
  return {
    name: vip.name,
    destinationAddress: vip.destination_address,
    destinationPort: String(vip.destination_port),
    poolName: vip.pool_name ?? "",
    vlan: vip.vlans[0] ?? "",
    persistence: vip.persistence ?? "",
  };
}

function StatusDot({ up }: { up: boolean }) {
  return (
    <span
      className="inline-block h-2.5 w-2.5 rounded-full mr-1.5 align-middle"
      style={{ background: up ? F5.green : F5.gray }}
    />
  );
}

function SectionHeader({ label }: { label: string }) {
  return (
    <tr>
      <td colSpan={2} className="px-3 py-1.5 text-white text-[13px] font-semibold" style={{ background: F5.sectionHead }}>
        {label}
      </td>
    </tr>
  );
}

function PropRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <tr className="border-b" style={{ borderColor: F5.border }}>
      <td className="w-56 align-top px-3 py-2 text-right text-[13px]" style={{ color: F5.textLabel, background: F5.white }}>
        {label}
      </td>
      <td className="px-3 py-2 text-[13px]" style={{ color: F5.textValue, background: F5.white }}>
        {value ?? <span style={{ color: F5.textMuted }}>—</span>}
      </td>
    </tr>
  );
}

function EditableRow({
  label,
  value,
  onChange,
  dirty,
  mono,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  dirty: boolean;
  mono?: boolean;
}) {
  return (
    <tr className="border-b" style={{ borderColor: F5.border, background: dirty ? "#fff8e6" : F5.white }}>
      <td className="w-56 align-top px-3 py-2 text-right text-[13px]" style={{ color: F5.textLabel, background: "transparent" }}>
        {label}
      </td>
      <td className="px-3 py-1.5" style={{ background: "transparent" }}>
        <input
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className={`w-full text-[13px] px-2 py-1 rounded border ${mono ? "font-mono" : ""}`}
          style={{ borderColor: dirty ? "#d97706" : F5.border, background: F5.white, color: F5.textValue }}
        />
        {dirty && <span className="text-[11px] ml-1" style={{ color: "#b45309" }}>changed</span>}
      </td>
    </tr>
  );
}

function VirtualServerListView({ vips, onOpen }: { vips: Vip[]; onOpen: (v: Vip) => void }) {
  return (
    <table className="w-full text-[13px] border-collapse">
      <thead>
        <tr style={{ background: "#dfe6ec" }}>
          <th className="text-left px-3 py-2 font-semibold border" style={{ borderColor: F5.border, color: F5.textLabel }}>
            Status
          </th>
          <th className="text-left px-3 py-2 font-semibold border" style={{ borderColor: F5.border, color: F5.textLabel }}>
            Name
          </th>
          <th className="text-left px-3 py-2 font-semibold border" style={{ borderColor: F5.border, color: F5.textLabel }}>
            Destination
          </th>
          <th className="text-left px-3 py-2 font-semibold border" style={{ borderColor: F5.border, color: F5.textLabel }}>
            Service Port
          </th>
          <th className="text-left px-3 py-2 font-semibold border" style={{ borderColor: F5.border, color: F5.textLabel }}>
            Type
          </th>
          <th className="text-left px-3 py-2 font-semibold border" style={{ borderColor: F5.border, color: F5.textLabel }}>
            Resources
          </th>
          <th className="text-left px-3 py-2 font-semibold border" style={{ borderColor: F5.border, color: F5.textLabel }}>
            Partition
          </th>
        </tr>
      </thead>
      <tbody>
        {vips.map((v, i) => (
          <tr key={v.name} style={{ background: i % 2 ? F5.rowAlt : "white" }}>
            <td className="px-3 py-1.5 border" style={{ borderColor: F5.border }}>
              <StatusDot up={!!v.pool_name} />
              {v.pool_name ? "Available" : "Offline"}
            </td>
            <td className="px-3 py-1.5 border" style={{ borderColor: F5.border }}>
              <button onClick={() => onOpen(v)} className="hover:underline" style={{ color: F5.link }}>
                {v.name.replace("/Common/", "")}
              </button>
            </td>
            <td className="px-3 py-1.5 border font-mono text-[12px]" style={{ borderColor: F5.border }}>
              {v.destination_address}
            </td>
            <td className="px-3 py-1.5 border" style={{ borderColor: F5.border }}>
              {v.destination_port} ({v.ip_protocol ?? "tcp"})
            </td>
            <td className="px-3 py-1.5 border" style={{ borderColor: F5.border }}>
              Standard
            </td>
            <td className="px-3 py-1.5 border" style={{ borderColor: F5.border }}>
              {v.pool_name ? v.pool_name.replace("/Common/", "") : "None"}
            </td>
            <td className="px-3 py-1.5 border" style={{ borderColor: F5.border }}>
              Common
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function F5GuiPreview({
  vip,
  pool,
  allVips,
  nodesByName,
  sessionId,
  onClose,
}: {
  vip: Vip;
  pool: Pool | undefined;
  allVips: Vip[];
  nodesByName: Record<string, NodeObj>;
  sessionId: string | null;
  onClose: () => void;
}) {
  const [view, setView] = useState<"properties" | "list">("properties");
  const [openVip, setOpenVip] = useState(vip);
  const [fields, setFields] = useState<EditableFields>(() => fieldsFromVip(vip));
  const [busy, setBusy] = useState(false);
  const [tmsh, setTmsh] = useState<string | null>(null);

  function openDifferentVip(v: Vip) {
    setOpenVip(v);
    setFields(fieldsFromVip(v));
    setTmsh(null);
    setView("properties");
  }

  const original = fieldsFromVip(openVip);
  const dirty = {
    name: fields.name !== original.name,
    destinationAddress: fields.destinationAddress !== original.destinationAddress,
    destinationPort: fields.destinationPort !== original.destinationPort,
    poolName: fields.poolName !== original.poolName,
    vlan: fields.vlan !== original.vlan,
    persistence: fields.persistence !== original.persistence,
  };
  const hasChanges = Object.values(dirty).some(Boolean);

  async function handlePreviewTmsh() {
    if (!sessionId) {
      toast("error", "No session selected — can't reach the backend to compute TMSH.");
      return;
    }
    setBusy(true);
    setTmsh(null);
    try {
      const commonChanges = [];
      if (dirty.name) {
        commonChanges.push({ change_type: "vip_name" as const, payload: { find: openVip.name, replace: fields.name } });
      }
      if (dirty.destinationAddress || dirty.destinationPort) {
        commonChanges.push({
          change_type: "vip_ip_port" as const,
          payload: {
            new_address: dirty.destinationAddress ? fields.destinationAddress : undefined,
            new_port: dirty.destinationPort ? Number(fields.destinationPort) : undefined,
          },
        });
      }
      if (dirty.poolName) {
        commonChanges.push({ change_type: "pool_name" as const, payload: { find: openVip.pool_name ?? "", replace: fields.poolName } });
      }
      if (dirty.vlan) {
        commonChanges.push({
          change_type: "vlans" as const,
          payload: { old_vlan: openVip.vlans[0] ?? undefined, new_vlan: fields.vlan },
        });
      }
      if (dirty.persistence) {
        commonChanges.push({ change_type: "persistence" as const, payload: { new_persistence: fields.persistence } });
      }

      const plan = {
        session_id: sessionId,
        selected_vips: [openVip.name],
        common_changes: commonChanges,
        node_changes: [],
        pool_member_edits: [],
        exceptions: [],
        create_network_objects: false,
        output_mode: "changes_only" as const,
      };

      const created = await api.createPlan(sessionId, plan);
      const validation = await api.validatePlan(sessionId, created.id);
      if (validation.overall === "BLOCKED") {
        setTmsh(
          "// Validation BLOCKED:\n" + validation.checks.filter((c) => c.severity === "blocked").map((c) => `// - ${c.label}: ${c.details}`).join("\n"),
        );
        return;
      }
      const result = await api.generatePlan(sessionId, created.id);
      setTmsh(result.tmsh || "// No TMSH produced for this edit.");
      toast("success", "TMSH computed for your edits.");
    } catch (e) {
      toast("error", e instanceof Error ? e.message : "Could not compute TMSH for these changes");
    } finally {
      setBusy(false);
    }
  }

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-start justify-center p-3 overflow-y-auto"
      style={{ background: "rgba(0,0,0,0.6)" }}
      onClick={onClose}
    >
      <div
        className="w-[97vw] max-h-[95vh] rounded-md shadow-2xl overflow-hidden flex flex-col shrink-0"
        style={{ background: F5.white, color: F5.textValue }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* fake browser chrome for realism */}
        <div className="flex items-center gap-2 px-3 py-2" style={{ background: "#e4e7eb" }}>
          <span className="h-2.5 w-2.5 rounded-full bg-red-400" />
          <span className="h-2.5 w-2.5 rounded-full bg-yellow-400" />
          <span className="h-2.5 w-2.5 rounded-full bg-green-400" />
          <span
            className="ml-3 flex-1 text-[11px] rounded px-2 py-0.5 font-mono truncate"
            style={{ color: F5.textLabel, background: F5.white }}
          >
            https://&lt;bigip-host&gt;/tmui/Control/jspmap/tmui/locallb/virtual/{view === "properties" ? "properties.jsp" : "list.jsp"}
          </span>
          <button onClick={onClose} className="text-sm px-2" style={{ color: F5.textLabel }}>
            ×
          </button>
        </div>

        {/* F5 top bar */}
        <div className="flex items-center justify-between px-4 py-2" style={{ background: F5.bar }}>
          <div className="flex items-center gap-3">
            <span className="text-white font-bold text-lg tracking-tight">
              <span style={{ color: "#e2231a" }}>F5</span>
              <span className="text-slate-300 font-normal text-xs ml-2">BIG-IP® Configuration Utility</span>
            </span>
          </div>
          <div className="text-slate-300 text-xs">Partition: Common &nbsp;|&nbsp; admin &nbsp;|&nbsp; Log off</div>
        </div>

        <div className="flex flex-1 min-h-0">
          {/* left nav */}
          <div className="w-48 shrink-0 text-[13px] py-2 overflow-y-auto" style={{ background: F5.navy }}>
            {["Statistics", "iApps", "Local Traffic", "Network", "System"].map((item) => (
              <div key={item}>
                <div
                  className="px-3 py-1.5 text-slate-200"
                  style={item === "Local Traffic" ? { background: F5.navyActive, color: "white", fontWeight: 600 } : undefined}
                >
                  {item}
                </div>
                {item === "Local Traffic" && (
                  <div className="pl-4 pb-1">
                    {["Virtual Servers", "Pools", "Nodes", "Monitors", "Profiles", "iRules"].map((sub) => (
                      <div
                        key={sub}
                        className="px-2 py-1 text-slate-300 text-[12px] cursor-pointer hover:text-white"
                        style={sub === "Virtual Servers" ? { color: "white", fontWeight: 600 } : undefined}
                      >
                        {sub}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* content */}
          <div className="flex-1 min-w-0 min-h-0 flex flex-col">
            <div
              className="px-4 py-2 text-[12px]"
              style={{ background: F5.breadcrumb, borderBottom: `1px solid ${F5.border}`, color: F5.textLabel }}
            >
              Local Traffic » Virtual Servers » Virtual Server List
              {view === "properties" && (
                <>
                  {" » "}
                  <span className="font-medium" style={{ color: F5.textValue }}>
                    {openVip.name.replace("/Common/", "")}
                  </span>
                </>
              )}
            </div>
            <div className="flex gap-4 px-4 pt-2 text-[13px]" style={{ borderBottom: `1px solid ${F5.border}` }}>
              <button
                onClick={() => setView("list")}
                className="pb-2 px-1"
                style={view === "list" ? { borderBottom: `2px solid ${F5.navyActive}`, color: F5.navyActive, fontWeight: 600 } : { color: "#64748b" }}
              >
                Virtual Server List
              </button>
              <button
                onClick={() => setView("properties")}
                className="pb-2 px-1"
                style={view === "properties" ? { borderBottom: `2px solid ${F5.navyActive}`, color: F5.navyActive, fontWeight: 600 } : { color: "#64748b" }}
              >
                Properties
              </button>
            </div>
            <div className="flex-1 overflow-auto p-4" style={{ background: "#f7f9fa" }}>
              {view === "list" ? (
                <VirtualServerListView vips={allVips} onOpen={openDifferentVip} />
              ) : (
                <>
                  <table className="w-full border-collapse" style={{ border: `1px solid ${F5.border}` }}>
                    <tbody>
                      <SectionHeader label="General Properties" />
                      <EditableRow label="Name" value={fields.name.replace("/Common/", "")} dirty={dirty.name} onChange={(v) => setFields((f) => ({ ...f, name: v.startsWith("/") ? v : `/Common/${v}` }))} />
                      <PropRow label="Partition / Path" value="Common" />
                      <PropRow label="Type" value="Standard" />
                      <EditableRow
                        label="Destination Address"
                        value={fields.destinationAddress}
                        dirty={dirty.destinationAddress}
                        mono
                        onChange={(v) => setFields((f) => ({ ...f, destinationAddress: v }))}
                      />
                      <EditableRow
                        label="Service Port"
                        value={fields.destinationPort}
                        dirty={dirty.destinationPort}
                        mono
                        onChange={(v) => setFields((f) => ({ ...f, destinationPort: v.replace(/[^0-9]/g, "") }))}
                      />
                      <PropRow
                        label="State"
                        value={
                          <span className="inline-flex items-center">
                            <StatusDot up />
                            Enabled
                          </span>
                        }
                      />

                      <SectionHeader label="Configuration: Basic" />
                      <PropRow label="Protocol" value={(openVip.ip_protocol ?? "tcp").toUpperCase()} />
                      <EditableRow
                        label="VLAN"
                        value={fields.vlan.replace("/Common/", "")}
                        dirty={dirty.vlan}
                        onChange={(v) => setFields((f) => ({ ...f, vlan: v.startsWith("/") ? v : `/Common/${v}` }))}
                      />
                      <PropRow label="Source Address Translation" value={openVip.snat_type ?? "None"} />
                      <PropRow label="Profiles" value={openVip.profiles.length ? openVip.profiles.map((p) => p.name).join(", ") : "—"} />

                      <SectionHeader label="Resources" />
                      <PropRow label="iRules" value={openVip.irules.length ? openVip.irules.map((r) => r.replace("/Common/", "")).join(", ") : "None"} />
                      <EditableRow
                        label="Default Pool"
                        value={fields.poolName.replace("/Common/", "")}
                        dirty={dirty.poolName}
                        onChange={(v) => setFields((f) => ({ ...f, poolName: v.startsWith("/") ? v : `/Common/${v}` }))}
                      />
                      <EditableRow
                        label="Default Persistence Profile"
                        value={fields.persistence.replace("/Common/", "")}
                        dirty={dirty.persistence}
                        onChange={(v) => setFields((f) => ({ ...f, persistence: v.startsWith("/") ? v : `/Common/${v}` }))}
                      />

                      {pool && (
                        <>
                          <SectionHeader label={`Pool Members: ${pool.name.replace("/Common/", "")}`} />
                          <tr>
                            <td colSpan={2} className="p-0">
                              <table className="w-full text-[12px]">
                                <thead>
                                  <tr style={{ background: "#dfe6ec" }}>
                                    <th className="text-left px-3 py-1.5 border" style={{ borderColor: F5.border }}>Status</th>
                                    <th className="text-left px-3 py-1.5 border" style={{ borderColor: F5.border }}>Member</th>
                                    <th className="text-left px-3 py-1.5 border" style={{ borderColor: F5.border }}>Address</th>
                                    <th className="text-left px-3 py-1.5 border" style={{ borderColor: F5.border }}>Port</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {pool.members.map((m, i) => (
                                    <tr key={`${m.node_name}:${m.port}`} style={{ background: i % 2 ? F5.rowAlt : "white" }}>
                                      <td className="px-3 py-1.5 border" style={{ borderColor: F5.border }}>
                                        <StatusDot up={m.session_state !== "user-disabled"} />
                                        {m.session_state === "user-disabled" ? "Disabled" : "Available"}
                                      </td>
                                      <td className="px-3 py-1.5 border" style={{ borderColor: F5.border }}>{m.node_name.replace("/Common/", "")}</td>
                                      <td className="px-3 py-1.5 border font-mono" style={{ borderColor: F5.border }}>
                                        {nodesByName[m.node_name]?.address ?? "—"}
                                      </td>
                                      <td className="px-3 py-1.5 border" style={{ borderColor: F5.border }}>{m.port}</td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </td>
                          </tr>
                        </>
                      )}
                    </tbody>
                  </table>

                  <div className="mt-4 flex items-center gap-2">
                    <button
                      onClick={handlePreviewTmsh}
                      disabled={!hasChanges || busy}
                      className="px-4 py-1.5 text-[13px] text-white rounded disabled:opacity-40 disabled:cursor-not-allowed"
                      style={{ background: F5.navyActive }}
                    >
                      {busy ? "Computing…" : "Update"}
                    </button>
                    <button
                      className="px-4 py-1.5 text-[13px] border rounded"
                      style={{ borderColor: F5.border, color: F5.textLabel }}
                    >
                      Delete
                    </button>
                    {hasChanges && !busy && (
                      <span className="text-[12px]" style={{ color: F5.textLabel }}>
                        Click Update to compute the real TMSH command for the field(s) you changed.
                      </span>
                    )}
                  </div>

                  {tmsh !== null && (
                    <div className="mt-4 rounded overflow-hidden" style={{ background: "#03050a" }}>
                      <div className="flex items-center gap-1.5 px-3 py-1.5" style={{ borderBottom: "1px solid rgba(255,255,255,0.08)" }}>
                        <span className="h-2 w-2 rounded-full" style={{ background: "#ff5c5c" }} />
                        <span className="h-2 w-2 rounded-full" style={{ background: "#ffbd2e" }} />
                        <span className="h-2 w-2 rounded-full" style={{ background: "#27c93f" }} />
                        <span className="ml-2 text-[10px]" style={{ color: F5.textDim }}>
                          tmsh — computed by the same engine as Step 5
                        </span>
                      </div>
                      <pre className="text-[12px] leading-relaxed p-3 overflow-auto max-h-40 whitespace-pre-wrap break-all font-mono" style={{ color: "#2bffb0" }}>
                        {tmsh}
                      </pre>
                    </div>
                  )}
                </>
              )}
            </div>
          </div>
        </div>

        <div className="px-4 py-1.5 text-[11px] border-t" style={{ borderColor: F5.border, color: F5.textMuted }}>
          Preview only — recreates the BIG-IP Configuration Utility layout from parsed data; edits here compute real TMSH via the backend but are never applied to a live device. Not affiliated with F5, Inc.
        </div>
      </div>
    </div>,
    document.body,
  );
}
