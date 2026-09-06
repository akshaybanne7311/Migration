import { Fragment, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import { api } from "../api/client";
import type { GenerateResult, Monitor, NodeObj, OutputMode, Pool, SystemObject, ValidationResult, Vip, Vlan } from "../api/types";
import { toast } from "./toastStore";
import { exportMigrationPlanToExcel } from "../utils/excelExport";
import { exportSopDocument } from "../utils/sopExport";

type Section =
  | "virtual-servers"
  | "pools"
  | "nodes"
  | "monitors"
  | "profiles"
  | "irules"
  | "net-vlans"
  | "net-self-ips"
  | "net-trunks"
  | "net-routes"
  | "net-route-domains"
  | "net-dns-resolvers"
  | "sys-configuration"
  | "sys-ntp"
  | "sys-snmp"
  | "sys-syslog"
  | "sys-mgmt-routes"
  | "sys-provisioning"
  | "sys-certificates"
  | "sys-license"
  | "dm-devices"
  | "dm-device-groups"
  | "dm-traffic-groups"
  | "statistics"
  | "iapps";

const SECTION_LABEL: Record<Section, string> = {
  "virtual-servers": "Local Traffic » Virtual Servers » Virtual Server List",
  pools: "Local Traffic » Pools » Pool List",
  nodes: "Local Traffic » Nodes » Node List",
  monitors: "Local Traffic » Monitors",
  profiles: "Local Traffic » Profiles",
  irules: "Local Traffic » iRules",
  "net-vlans": "Network » VLANs",
  "net-self-ips": "Network » Self IPs",
  "net-trunks": "Network » Trunks",
  "net-routes": "Network » Routes",
  "net-route-domains": "Network » Route Domains",
  "net-dns-resolvers": "Network » DNS Resolvers",
  "sys-configuration": "System » Configuration » Device",
  "sys-ntp": "System » Configuration » Device » NTP",
  "sys-snmp": "System » Configuration » Device » SNMP",
  "sys-syslog": "System » Configuration » Device » Syslog",
  "sys-mgmt-routes": "System » Configuration » Device » Management Routes",
  "sys-provisioning": "System » Resource Provisioning",
  "sys-certificates": "System » Certificate Management » SSL Certificate List",
  "sys-license": "System » License & Version",
  "dm-devices": "Device Management » Devices",
  "dm-device-groups": "Device Management » Device Groups",
  "dm-traffic-groups": "Device Management » Traffic Groups",
  statistics: "Statistics",
  iapps: "iApps",
};

const NETWORK_SUB_SECTIONS: [Section, string][] = [
  ["net-vlans", "VLANs"],
  ["net-self-ips", "Self IPs"],
  ["net-trunks", "Trunks"],
  ["net-routes", "Routes"],
  ["net-route-domains", "Route Domains"],
  ["net-dns-resolvers", "DNS Resolvers"],
];

const SYSTEM_SUB_SECTIONS: [Section, string][] = [
  ["sys-configuration", "Configuration"],
  ["sys-ntp", "NTP"],
  ["sys-snmp", "SNMP"],
  ["sys-syslog", "Syslog"],
  ["sys-mgmt-routes", "Management Routes"],
  ["sys-provisioning", "Resource Provisioning"],
  ["sys-certificates", "SSL Certificates"],
  ["sys-license", "License & Version"],
];

const DEVICE_MGMT_SUB_SECTIONS: [Section, string][] = [
  ["dm-devices", "Devices"],
  ["dm-device-groups", "Device Groups"],
  ["dm-traffic-groups", "Traffic Groups"],
];

/** Recreates the look of a typical device configuration console so an
 * engineer can visually sanity-check what a parsed VIP looks like in an
 * admin console, without needing access to a live device -- and lets
 * them edit fields right here and see the real TMSH command for that edit.
 *
 * The edit -> TMSH step never reimplements the change engine's field
 * resolution on the frontend (that would be a second, driftable copy of
 * logic that already exists and is tested server-side). Instead an edit
 * here builds the exact same MigrationPlan shape the wizard's Step 3/5
 * produce, for this one VIP, and round-trips it through the real
 * create-plan / validate / generate API calls -- so the TMSH shown is
 * never a guess, it's the same backend that generates everything else in
 * this app. Not a pixel-exact clone of any particular vendor's console. */

// This mockup must always render as a real (light) device console -- never
// reactive to the host app's own dark/light theme toggle. Every color
// below is applied via inline `style`, not a plain Tailwind utility class
// (e.g. never `text-slate-600` / `bg-white`) -- the app's global CSS
// reskin (src/index.css) targets exactly those literal class names, and
// pairing one of them with an inline device-palette background silently broke
// contrast (light-themed override text landing on a light inline
// background, or vice versa) wherever only one side of a pair got caught.
const UI = {
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
      style={{ background: up ? UI.green : UI.gray }}
    />
  );
}

function SectionHeader({ label }: { label: string }) {
  return (
    <tr>
      <td colSpan={2} className="px-3 py-1.5 text-white text-[13px] font-semibold" style={{ background: UI.sectionHead }}>
        {label}
      </td>
    </tr>
  );
}

function PropRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <tr className="border-b" style={{ borderColor: UI.border }}>
      <td className="w-56 align-top px-3 py-2 text-right text-[13px]" style={{ color: UI.textLabel, background: UI.white }}>
        {label}
      </td>
      <td className="px-3 py-2 text-[13px]" style={{ color: UI.textValue, background: UI.white }}>
        {value ?? <span style={{ color: UI.textMuted }}>—</span>}
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
    <tr className="border-b" style={{ borderColor: UI.border, background: dirty ? "#fff8e6" : UI.white }}>
      <td className="w-56 align-top px-3 py-2 text-right text-[13px]" style={{ color: UI.textLabel, background: "transparent" }}>
        {label}
      </td>
      <td className="px-3 py-1.5" style={{ background: "transparent" }}>
        <input
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className={`w-full text-[13px] px-2 py-1 rounded border ${mono ? "font-mono" : ""}`}
          style={{ borderColor: dirty ? "#d97706" : UI.border, background: UI.white, color: UI.textValue }}
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
          <th className="text-left px-3 py-2 font-semibold border" style={{ borderColor: UI.border, color: UI.textLabel }}>
            Status
          </th>
          <th className="text-left px-3 py-2 font-semibold border" style={{ borderColor: UI.border, color: UI.textLabel }}>
            Name
          </th>
          <th className="text-left px-3 py-2 font-semibold border" style={{ borderColor: UI.border, color: UI.textLabel }}>
            Destination
          </th>
          <th className="text-left px-3 py-2 font-semibold border" style={{ borderColor: UI.border, color: UI.textLabel }}>
            Service Port
          </th>
          <th className="text-left px-3 py-2 font-semibold border" style={{ borderColor: UI.border, color: UI.textLabel }}>
            Type
          </th>
          <th className="text-left px-3 py-2 font-semibold border" style={{ borderColor: UI.border, color: UI.textLabel }}>
            Resources
          </th>
          <th className="text-left px-3 py-2 font-semibold border" style={{ borderColor: UI.border, color: UI.textLabel }}>
            Partition
          </th>
        </tr>
      </thead>
      <tbody>
        {vips.map((v, i) => (
          <tr key={v.name} style={{ background: i % 2 ? UI.rowAlt : "white" }}>
            <td className="px-3 py-1.5 border" style={{ borderColor: UI.border }}>
              <StatusDot up={!!v.pool_name} />
              {v.pool_name ? "Available" : "Offline"}
            </td>
            <td className="px-3 py-1.5 border" style={{ borderColor: UI.border }}>
              <button onClick={() => onOpen(v)} className="hover:underline" style={{ color: UI.link }}>
                {v.name.replace("/Common/", "")}
              </button>
            </td>
            <td className="px-3 py-1.5 border font-mono text-[12px]" style={{ borderColor: UI.border }}>
              {v.destination_address}
            </td>
            <td className="px-3 py-1.5 border" style={{ borderColor: UI.border }}>
              {v.destination_port} ({v.ip_protocol ?? "tcp"})
            </td>
            <td className="px-3 py-1.5 border" style={{ borderColor: UI.border }}>
              Standard
            </td>
            <td className="px-3 py-1.5 border" style={{ borderColor: UI.border }}>
              {v.pool_name ? v.pool_name.replace("/Common/", "") : "None"}
            </td>
            <td className="px-3 py-1.5 border" style={{ borderColor: UI.border }}>
              Common
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function listTh(label: string) {
  return (
    <th key={label} className="text-left px-3 py-2 font-semibold border" style={{ borderColor: UI.border, color: UI.textLabel }}>
      {label}
    </th>
  );
}

function listTd(content: React.ReactNode, mono?: boolean, key?: React.Key) {
  return (
    <td key={key} className={`px-3 py-1.5 border ${mono ? "font-mono text-[12px]" : ""}`} style={{ borderColor: UI.border }}>
      {content}
    </td>
  );
}

/** Canonical F5 GUI field slots for attached profiles, in the order the
 * real Virtual Server Properties page shows them -- each maps to the real
 * "ltm profile <type>" suffix that fills it. Slots not seen on any of the
 * 9 real devices this was checked against (client-ssl, ftp, rtsp, ...)
 * still render as their real field name with "None", exactly like the
 * real GUI shows an empty field slot rather than hiding it. */
const PROFILE_FIELD_SLOTS: [string, string][] = [
  ["http", "HTTP Profile"],
  ["http2", "HTTP/2 Profile"],
  ["client-ssl", "SSL Profile (Client)"],
  ["server-ssl", "SSL Profile (Server)"],
  ["tcp", "Protocol Profile"],
  ["udp", "Protocol Profile"],
  ["fastl4", "Protocol Profile"],
  ["ftp", "FTP Profile"],
  ["rtsp", "RTSP Profile"],
  ["sip", "SIP Profile"],
  ["diameter", "Diameter Profile"],
  ["dns", "DNS Profile"],
  ["fix", "FIX Profile"],
  ["html", "HTML Profile"],
  ["rewrite", "Rewrite Profile"],
];

function stanzaField(json: string, key: string): string | undefined {
  try {
    const parsed = JSON.parse(json);
    const val = parsed?.[key];
    return typeof val === "string" ? val : undefined;
  } catch {
    return undefined;
  }
}

function PoolListView({ pools }: { pools: Pool[] }) {
  if (pools.length === 0) return <EmptySectionNote text="No pools parsed from this session." />;
  return (
    <ExpandableListView
      rows={pools}
      columns={["Status", "Name", "Description", "Members", "Monitors", "Load Balancing", "Service Down Action", "Partition"]}
      renderCells={(p) => [
        <>
          <StatusDot up={p.members.some((m) => m.session_state !== "user-disabled")} />
          {p.members.length > 0 ? "Available" : "No members"}
        </>,
        p.name.replace("/Common/", ""),
        stanzaField(p.source_stanza_json, "description") ?? "—",
        `${p.members.length} member${p.members.length === 1 ? "" : "s"}`,
        p.monitor_names.length ? p.monitor_names.map((m) => m.replace("/Common/", "")).join(", ") : "None",
        stanzaField(p.source_stanza_json, "load-balancing-mode") ?? "round-robin",
        stanzaField(p.source_stanza_json, "service-down-action") ?? "None",
        p.partition,
      ]}
    />
  );
}

function NodeListView({ nodes }: { nodes: NodeObj[] }) {
  if (nodes.length === 0) return <EmptySectionNote text="No nodes parsed from this session." />;
  return (
    <ExpandableListView
      rows={nodes}
      columns={["Status", "Name", "Description", "Address", "Family", "Used by pools", "Used by VIPs", "Partition"]}
      renderCells={(n) => [
        <>
          <StatusDot up={n.state !== "user-disabled"} />
          {n.state ?? "Enabled"}
        </>,
        n.name.replace("/Common/", ""),
        stanzaField(n.source_stanza_json, "description") ?? "—",
        n.address,
        n.address_family.toUpperCase(),
        n.pool_count ?? "—",
        n.vip_count ?? "—",
        n.partition,
      ]}
    />
  );
}

function VlanListView({ vlans }: { vlans: Vlan[] }) {
  if (vlans.length === 0) return <EmptySectionNote text="No VLANs parsed from this session." />;
  return (
    <ExpandableListView
      rows={vlans}
      columns={["Name", "Tag", "Interfaces"]}
      renderCells={(v) => [v.name.replace("/Common/", ""), v.tag ?? "—", v.interfaces.length ? v.interfaces.join(", ") : "None"]}
    />
  );
}

function EmptySectionNote({ text }: { text: string }) {
  return (
    <div className="text-[13px] px-1 py-6 text-center" style={{ color: UI.textMuted }}>
      {text}
    </div>
  );
}

/** Pretty-prints the exact stanza the parser read out of bigip.conf for this
 * object -- every field the archive ever had, including anything the typed
 * domain model (Vip/Pool/NodeObj) doesn't surface, so nothing from the
 * source UCS/QKView is ever hidden from view. */
function RawStanzaBlock({ label, json }: { label: string; json: string }) {
  let pretty = json;
  try {
    pretty = JSON.stringify(JSON.parse(json), null, 2);
  } catch {
    // not valid JSON (shouldn't happen) -- fall back to showing it raw
  }
  return (
    <details>
      <summary className="cursor-pointer text-[12px] select-none py-1" style={{ color: UI.link }}>
        {label}
      </summary>
      <pre
        className="text-[11px] leading-snug p-2 mt-1 overflow-auto max-h-72 whitespace-pre-wrap break-all font-mono rounded"
        style={{ background: "#0b1220", color: "#7dd3fc" }}
      >
        {pretty}
      </pre>
    </details>
  );
}

function ExpandableListView<T extends { name: string }>({
  rows,
  columns,
  renderCells,
  rawJson = (row) => (row as unknown as { source_stanza_json: string }).source_stanza_json,
  renderExpanded,
}: {
  rows: T[];
  columns: string[];
  renderCells: (row: T) => React.ReactNode[];
  rawJson?: (row: T) => string;
  /** Overrides the default raw-JSON expand content -- e.g. an iRule's expand
   * shows its real TCL script text, not a JSON dump of a mis-tokenized blob. */
  renderExpanded?: (row: T) => React.ReactNode;
}) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  function toggle(name: string) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  }
  return (
    <table className="w-full text-[13px] border-collapse">
      <thead>
        <tr style={{ background: "#dfe6ec" }}>
          {listTh("")}
          {columns.map(listTh)}
        </tr>
      </thead>
      <tbody>
        {rows.map((row, i) => {
          const isOpen = expanded.has(row.name);
          const cells = renderCells(row);
          return (
            <Fragment key={row.name}>
              <tr
                style={{ background: i % 2 ? UI.rowAlt : "white", cursor: "pointer" }}
                onClick={() => toggle(row.name)}
              >
                {listTd(
                  <span style={{ display: "inline-block", transform: isOpen ? "rotate(90deg)" : undefined, color: UI.textMuted }}>
                    ▶
                  </span>,
                )}
                {cells.map((c, ci) => listTd(c, false, ci))}
              </tr>
              {isOpen && (
                <tr style={{ background: "#eef2f6" }}>
                  <td colSpan={columns.length + 1} className="px-4 py-2 border" style={{ borderColor: UI.border }}>
                    {renderExpanded ? (
                      renderExpanded(row)
                    ) : (
                      <RawStanzaBlock label="Raw parsed config (from bigip.conf)" json={rawJson(row)} />
                    )}
                  </td>
                </tr>
              )}
            </Fragment>
          );
        })}
      </tbody>
    </table>
  );
}

function parseEntries(json: string): Record<string, unknown> {
  try {
    const parsed = JSON.parse(json);
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

function entryToText(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "string") return v;
  if (Array.isArray(v)) return v.length ? v.join(", ") : "—";
  if (typeof v === "object") {
    const keys = Object.keys(v as Record<string, unknown>);
    return keys.length ? keys.join(", ") : "—";
  }
  return String(v);
}

function objectsOfType(objects: SystemObject[], type: string): SystemObject[] {
  return objects.filter((o) => o.object_type === type);
}

function objectsOfTypePrefix(objects: SystemObject[], prefixes: string[]): SystemObject[] {
  return objects.filter((o) => prefixes.some((p) => o.object_type.startsWith(p)));
}

function SelfIpListView({ objects }: { objects: SystemObject[] }) {
  const rows = objectsOfType(objects, "net self");
  if (rows.length === 0) return <EmptySectionNote text="No self IPs parsed from this session (device's own addresses on each VLAN)." />;
  return (
    <ExpandableListView
      rows={rows}
      columns={["Name", "Address", "VLAN", "Traffic Group", "Port Lockdown"]}
      rawJson={(r) => r.entries_json}
      renderCells={(r) => {
        const e = parseEntries(r.entries_json);
        return [
          r.name.replace("/Common/", ""),
          entryToText(e.address),
          entryToText(e.vlan).replace("/Common/", ""),
          entryToText(e["traffic-group"]),
          entryToText(e["allow-service"]),
        ];
      }}
    />
  );
}

function TrunkListView({ objects }: { objects: SystemObject[] }) {
  const rows = objectsOfType(objects, "net trunk");
  if (rows.length === 0) return <EmptySectionNote text="No trunks parsed from this session." />;
  return (
    <ExpandableListView
      rows={rows}
      columns={["Name", "Interfaces", "LACP"]}
      rawJson={(r) => r.entries_json}
      renderCells={(r) => {
        const e = parseEntries(r.entries_json);
        return [r.name, entryToText(e.interfaces), entryToText(e.lacp) === "—" ? "disabled" : entryToText(e.lacp)];
      }}
    />
  );
}

function RouteListView({ objects }: { objects: SystemObject[] }) {
  const rows = objectsOfType(objects, "net route");
  if (rows.length === 0) return <EmptySectionNote text="No static routes parsed from this session." />;
  return (
    <ExpandableListView
      rows={rows}
      columns={["Name", "Destination", "Gateway"]}
      rawJson={(r) => r.entries_json}
      renderCells={(r) => {
        const e = parseEntries(r.entries_json);
        return [r.name.replace("/Common/", ""), entryToText(e.network), entryToText(e.gw)];
      }}
    />
  );
}

function RouteDomainListView({ objects }: { objects: SystemObject[] }) {
  const rows = objectsOfType(objects, "net route-domain");
  if (rows.length === 0) return <EmptySectionNote text="No route domains parsed from this session." />;
  return (
    <ExpandableListView
      rows={rows}
      columns={["Name", "ID", "VLANs"]}
      rawJson={(r) => r.entries_json}
      renderCells={(r) => {
        const e = parseEntries(r.entries_json);
        return [r.name.replace("/Common/", ""), entryToText(e.id), entryToText(e.vlans)];
      }}
    />
  );
}

function ManagementRouteListView({ objects }: { objects: SystemObject[] }) {
  const rows = objectsOfType(objects, "sys management-route");
  if (rows.length === 0) return <EmptySectionNote text="No management routes parsed from this session." />;
  return (
    <ExpandableListView
      rows={rows}
      columns={["Name", "Network", "Gateway"]}
      rawJson={(r) => r.entries_json}
      renderCells={(r) => {
        const e = parseEntries(r.entries_json);
        return [r.name.replace("/Common/", ""), entryToText(e.network), entryToText(e.gateway)];
      }}
    />
  );
}

function DnsResolverListView({ objects }: { objects: SystemObject[] }) {
  const rows = objectsOfType(objects, "net dns-resolver");
  if (rows.length === 0) return <EmptySectionNote text="No DNS resolvers parsed from this session." />;
  return (
    <ExpandableListView
      rows={rows}
      columns={["Name", "Forward Zones"]}
      rawJson={(r) => r.entries_json}
      renderCells={(r) => {
        const e = parseEntries(r.entries_json);
        const zones = e["forward-zones"];
        const zoneNames = zones && typeof zones === "object" ? Object.keys(zones as Record<string, unknown>) : [];
        return [r.name.replace("/Common/", ""), zoneNames.length ? zoneNames.join(", ") : "—"];
      }}
    />
  );
}

/** Real X.509 certificates pulled from PEM files inside the archive
 * (config/ssl/ssl.crt/*, filestore certificate_d/*) -- not device config
 * stanzas. Sorted server-side by soonest-expiring first. */
function CertificateListView({ objects, sessionId }: { objects: SystemObject[]; sessionId: string | null }) {
  const rows = objectsOfType(objects, "x509 certificate");
  if (rows.length === 0) return <EmptySectionNote text="No PEM-encoded certificate files were found inside this archive." />;
  return (
    <ExpandableListView
      rows={rows}
      columns={["Common Name", "Issuer", "Expires", "Status", "Self-signed", "Source file(s)", "Original file"]}
      rawJson={(r) => r.entries_json}
      renderCells={(r) => {
        const e = parseEntries(r.entries_json);
        const days = e.days_until_expiry as number | undefined;
        const expired = Boolean(e.is_expired);
        const soon = typeof days === "number" && days >= 0 && days <= 60;
        let status = "OK";
        if (expired) status = `expired ${Math.abs(days ?? 0)}d ago`;
        else if (soon) status = `expires in ${days}d`;
        const sources = Array.isArray(e.source_paths) ? (e.source_paths as string[]) : [];
        const fingerprint = entryToText(e.fingerprint_sha256);
        return [
          entryToText(e.subject_cn ?? r.name),
          entryToText(e.issuer_cn),
          entryToText(e.not_after).slice(0, 10),
          status,
          e.is_self_signed ? "yes" : "no",
          sources.length ? sources.join(", ") : "—",
          sessionId && fingerprint !== "—" ? (
            <a
              key="dl"
              href={api.certificateDownloadUrl(sessionId, fingerprint)}
              onClick={(evt) => evt.stopPropagation()}
              className="underline"
              style={{ color: UI.navyActive }}
            >
              Download .crt
            </a>
          ) : (
            "—"
          ),
        ];
      }}
      renderExpanded={(r) => (
        <>
          <div className="text-[12px] mb-2" style={{ color: UI.textMuted }}>
            Parsed directly from a real PEM certificate file inside this session's archive — not from bigip.conf.
          </div>
          <RawStanzaBlock label="Certificate details" json={r.entries_json} />
        </>
      )}
    />
  );
}

/** Single-instance system settings (hostname, NTP, SNMP, syslog, ...) shown
 * as a key/value properties table -- there's exactly one of these per
 * device, unlike self IPs/trunks/routes which are lists. */
function SystemInfoView({
  objects,
  types,
  emptyText,
  sourceLabel = "Raw parsed config (from bigip.conf)",
}: {
  objects: SystemObject[];
  types: string[];
  emptyText: string;
  sourceLabel?: string;
}) {
  const matches = objects.filter((o) => types.includes(o.object_type));
  if (matches.length === 0) return <EmptySectionNote text={emptyText} />;
  return (
    <>
      {matches.map((obj) => {
        const entries = parseEntries(obj.entries_json);
        const keys = Object.keys(entries);
        return (
          <table key={`${obj.object_type}:${obj.name}`} className="w-full border-collapse mb-4" style={{ border: `1px solid ${UI.border}` }}>
            <tbody>
              <SectionHeader label={obj.name ? `${obj.object_type} ${obj.name}` : obj.object_type} />
              {keys.length === 0 && (
                <tr>
                  <td colSpan={2} className="px-3 py-2 text-[13px]" style={{ color: UI.textMuted }}>
                    No additional fields parsed for this object.
                  </td>
                </tr>
              )}
              {keys.map((k) => (
                <PropRow key={k} label={k} value={entryToText(entries[k])} />
              ))}
              <tr>
                <td colSpan={2} className="px-3 py-2" style={{ background: UI.white }}>
                  <RawStanzaBlock label={sourceLabel} json={obj.entries_json} />
                </td>
              </tr>
            </tbody>
          </table>
        );
      })}
    </>
  );
}

function MonitorListView({
  monitors,
  usedByMap,
}: {
  monitors: Monitor[];
  usedByMap: Map<string, string[]>;
}) {
  if (monitors.length === 0) return <EmptySectionNote text="No health monitors were parsed from this session." />;
  return (
    <ExpandableListView
      rows={monitors}
      columns={["Name", "Type", "Interval", "Timeout", "Referenced by"]}
      rawJson={(m) => m.source_stanza_json}
      renderCells={(m) => {
        const usedBy = usedByMap.get(m.name) ?? [];
        return [
          m.name.replace("/Common/", ""),
          m.monitor_type ?? "—",
          m.interval !== null ? `${m.interval}s` : "—",
          m.timeout !== null ? `${m.timeout}s` : "—",
          `${usedBy.length} object${usedBy.length === 1 ? "" : "s"}`,
        ];
      }}
    />
  );
}

/** Profile/persistence-profile and iRule sections show EVERY real object
 * parsed from the config -- not just ones the currently-visible VIP set
 * happens to reference. Confirmed on real data this matters: a device can
 * have iRules (and profiles) sitting in its config unattached to any of
 * the VIPs being migrated (leftover from a decommissioned VIP, shared
 * infra, etc.) -- exactly the kind of thing a migration should surface
 * rather than silently drop because "no VIP in this view points at it." */
function ProfileListView({ objects, usedByMap }: { objects: SystemObject[]; usedByMap: Map<string, string[]> }) {
  const rows = objectsOfTypePrefix(objects, ["ltm profile ", "ltm persistence "]);
  if (rows.length === 0) return <EmptySectionNote text="No profile or persistence-profile definitions were parsed from this session." />;
  return (
    <ExpandableListView
      rows={rows}
      columns={["Profile", "Kind", "Referenced by"]}
      rawJson={(o) => o.entries_json}
      renderCells={(o) => {
        const usedBy = usedByMap.get(o.name) ?? [];
        return [
          o.name.replace("/Common/", ""),
          o.object_type.replace(/^ltm (profile|persistence) /, ""),
          usedBy.length ? `${usedBy.length} VIP${usedBy.length === 1 ? "" : "s"}` : "not attached to any VIP here",
        ];
      }}
      renderExpanded={(o) => (
        <RawStanzaBlock label={`Real "${o.object_type}" definition (from bigip.conf)`} json={o.entries_json} />
      )}
    />
  );
}

function IRuleListView({ objects, usedByMap }: { objects: SystemObject[]; usedByMap: Map<string, string[]> }) {
  const rows = objectsOfType(objects, "ltm rule");
  if (rows.length === 0) return <EmptySectionNote text="No iRules were parsed from this session." />;
  return (
    <ExpandableListView
      rows={rows}
      columns={["iRule", "Referenced by"]}
      rawJson={(o) => o.entries_json}
      renderCells={(o) => {
        const usedBy = usedByMap.get(o.name) ?? [];
        return [o.name.replace("/Common/", ""), usedBy.length ? `${usedBy.length} VIP${usedBy.length === 1 ? "" : "s"}` : "not attached to any VIP here"];
      }}
      renderExpanded={(o) => {
        const script = parseEntries(o.entries_json).script as string | undefined;
        if (!script) {
          return (
            <div className="text-[12px]" style={{ color: UI.textDim }}>
              This iRule's body couldn't be extracted (malformed/truncated brace structure in the source archive).
            </div>
          );
        }
        return (
          <details open>
            <summary className="cursor-pointer text-[12px] select-none py-1" style={{ color: UI.link }}>
              Real iRule script (verbatim TCL, from bigip.conf)
            </summary>
            <pre
              className="text-[11px] leading-relaxed p-3 mt-1 overflow-auto max-h-96 whitespace-pre font-mono rounded"
              style={{ background: "#0b1220", color: "#7dd3fc" }}
            >
              {script}
            </pre>
          </details>
        );
      }}
    />
  );
}

export function GuiPreview({
  vip,
  pool,
  allVips,
  allPools = [],
  allNodes = [],
  allVlans = [],
  systemObjects = [],
  allMonitors = [],
  nodesByName,
  sessionId,
  onClose,
}: {
  vip: Vip;
  pool: Pool | undefined;
  allVips: Vip[];
  allPools?: Pool[];
  allNodes?: NodeObj[];
  allVlans?: Vlan[];
  systemObjects?: SystemObject[];
  allMonitors?: Monitor[];
  nodesByName: Record<string, NodeObj>;
  sessionId: string | null;
  onClose: () => void;
}) {
  const [view, setView] = useState<"properties" | "list">("properties");
  const [section, setSection] = useState<Section>("virtual-servers");
  const [openVip, setOpenVip] = useState(vip);
  const [fields, setFields] = useState<EditableFields>(() => fieldsFromVip(vip));
  const [busy, setBusy] = useState(false);
  const [tmsh, setTmsh] = useState<string | null>(null);
  const [outputMode, setOutputMode] = useState<OutputMode>("changes_only");
  const [validation, setValidation] = useState<ValidationResult | null>(null);
  const [generated, setGenerated] = useState<GenerateResult | null>(null);
  const [exporting, setExporting] = useState<"excel" | "sop" | null>(null);

  const virtualAddress = useMemo(() => {
    const match = systemObjects.find(
      (o) => o.object_type === "ltm virtual-address" && parseEntries(o.entries_json).address === openVip.destination_address,
    );
    return match ? parseEntries(match.entries_json) : null;
  }, [systemObjects, openVip.destination_address]);

  // Extra real fields TMOS captured for this virtual that the typed Vip
  // model doesn't have its own column for -- pulled straight from the raw
  // parsed stanza rather than re-parsed, so these can only ever show what
  // the archive actually had (confirmed present across all 8 real devices:
  // description, source, source-port, translate-address, translate-port,
  // serverssl-use-sni).
  const vipStanza = useMemo(() => parseEntries(openVip.source_stanza_json), [openVip.source_stanza_json]);

  // Real F5 GUI groups attached profiles by TYPE into named fields ("HTTP
  // Profile", "SSL Profile (Client)", ...), not one flat list -- the type
  // comes from the real "ltm profile <type> <name>" system_object, not a
  // guess. Confirmed across all 9 real sessions: no VIP's profile block
  // carries an explicit "context" key, so client/server labels below are
  // only used where the profile TYPE itself is unambiguous (client-ssl,
  // server-ssl); everything else is labeled by its real type name instead
  // of a guessed side.
  const profileTypeByName = useMemo(() => {
    const map = new Map<string, string>();
    for (const o of systemObjects) {
      if (o.object_type.startsWith("ltm profile ")) {
        map.set(o.name, o.object_type.slice("ltm profile ".length));
      }
    }
    return map;
  }, [systemObjects]);

  const profilesByType = useMemo(() => {
    const groups = new Map<string, string[]>();
    for (const p of openVip.profiles) {
      const type = profileTypeByName.get(p.name) ?? "other";
      if (!groups.has(type)) groups.set(type, []);
      groups.get(type)!.push(p.name.replace("/Common/", ""));
    }
    return groups;
  }, [openVip.profiles, profileTypeByName]);

  // Collapses PROFILE_FIELD_SLOTS (some labels like "Protocol Profile"
  // cover more than one real type) into one row per distinct GUI label,
  // each showing every real attached profile matching that label's
  // type(s), or "None" when the archive had nothing for that slot -- the
  // same way the real GUI always shows the field, populated or not.
  const profileFieldRows = useMemo(() => {
    const labelToTypes = new Map<string, string[]>();
    for (const [type, label] of PROFILE_FIELD_SLOTS) {
      if (!labelToTypes.has(label)) labelToTypes.set(label, []);
      labelToTypes.get(label)!.push(type);
    }
    const seenTypes = new Set(PROFILE_FIELD_SLOTS.map(([type]) => type));
    const rows: { label: string; value: string }[] = [];
    for (const [label, types] of labelToTypes) {
      const names = types.flatMap((t) => profilesByType.get(t) ?? []);
      rows.push({ label, value: names.length ? names.join(", ") : "None" });
    }
    const other = [...profilesByType.entries()].filter(([type]) => type !== "other" && !seenTypes.has(type));
    for (const [type, names] of other) {
      rows.push({ label: `Profile (${type})`, value: names.join(", ") });
    }
    if (profilesByType.has("other")) {
      rows.push({ label: "Other Profiles", value: profilesByType.get("other")!.join(", ") });
    }
    return rows;
  }, [profilesByType]);

  const monitors = useMemo(() => {
    const byName = new Map<string, Set<string>>();
    for (const p of allPools) {
      for (const m of p.monitor_names) {
        if (!byName.has(m)) byName.set(m, new Set());
        byName.get(m)!.add(p.name);
      }
    }
    for (const v of allVips) {
      for (const m of v.monitor_names) {
        if (!byName.has(m)) byName.set(m, new Set());
        byName.get(m)!.add(v.name);
      }
    }
    return Array.from(byName.entries()).map(([name, usedBy]) => ({ name, usedBy: Array.from(usedBy) }));
  }, [allPools, allVips]);

  const profiles = useMemo(() => {
    const byName = new Map<string, { context: string | null; usedBy: Set<string> }>();
    for (const v of allVips) {
      for (const p of v.profiles) {
        if (!byName.has(p.name)) byName.set(p.name, { context: p.context, usedBy: new Set() });
        byName.get(p.name)!.usedBy.add(v.name);
      }
    }
    return Array.from(byName.entries()).map(([name, { context, usedBy }]) => ({
      name,
      detail: context ?? undefined,
      usedBy: Array.from(usedBy),
    }));
  }, [allVips]);

  const irules = useMemo(() => {
    const byName = new Map<string, Set<string>>();
    for (const v of allVips) {
      for (const r of v.irules) {
        if (!byName.has(r)) byName.set(r, new Set());
        byName.get(r)!.add(v.name);
      }
    }
    return Array.from(byName.entries()).map(([name, usedBy]) => ({ name, usedBy: Array.from(usedBy) }));
  }, [allVips]);

  const monitorUsedByMap = useMemo(() => new Map(monitors.map((m) => [m.name, m.usedBy])), [monitors]);
  const profileUsedByMap = useMemo(() => new Map(profiles.map((p) => [p.name, p.usedBy])), [profiles]);
  const iruleUsedByMap = useMemo(() => new Map(irules.map((r) => [r.name, r.usedBy])), [irules]);

  function openDifferentVip(v: Vip) {
    setOpenVip(v);
    setFields(fieldsFromVip(v));
    setTmsh(null);
    setValidation(null);
    setGenerated(null);
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
    setValidation(null);
    setGenerated(null);
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
        output_mode: outputMode,
      };

      const created = await api.createPlan(sessionId, plan);
      const validationResult = await api.validatePlan(sessionId, created.id);
      setValidation(validationResult);
      if (validationResult.overall === "BLOCKED") {
        setTmsh(
          "// Validation BLOCKED:\n" + validationResult.checks.filter((c) => c.severity === "blocked").map((c) => `// - ${c.label}: ${c.details}`).join("\n"),
        );
        return;
      }
      const result = await api.generatePlan(sessionId, created.id);
      setGenerated(result);
      setTmsh(result.tmsh || "// No TMSH produced for this edit.");
      toast(
        "success",
        outputMode === "full_recreate" ? "Full TMSH deployment script computed." : "TMSH computed for your edits.",
      );
    } catch (e) {
      toast("error", e instanceof Error ? e.message : "Could not compute TMSH for these changes");
    } finally {
      setBusy(false);
    }
  }

  async function handleExportExcel() {
    setExporting("excel");
    try {
      await exportMigrationPlanToExcel({
        sessionName: openVip.name,
        selectedVips: [openVip],
        kpis: undefined,
        validation,
        generated,
        outputMode,
      });
      toast("success", "Excel workbook downloaded.");
    } catch (e) {
      toast("error", e instanceof Error ? e.message : "Excel export failed");
    } finally {
      setExporting(null);
    }
  }

  async function handleExportSop() {
    setExporting("sop");
    try {
      await exportSopDocument({
        sessionName: openVip.name,
        selectedVips: [openVip],
        kpis: undefined,
        validation,
        generated,
        outputMode,
      });
      toast("success", "SOP document downloaded.");
    } catch (e) {
      toast("error", e instanceof Error ? e.message : "SOP export failed");
    } finally {
      setExporting(null);
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
        style={{ background: UI.white, color: UI.textValue }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* fake browser chrome for realism */}
        <div className="flex items-center gap-2 px-3 py-2" style={{ background: "#e4e7eb" }}>
          <span className="h-2.5 w-2.5 rounded-full bg-red-400" />
          <span className="h-2.5 w-2.5 rounded-full bg-yellow-400" />
          <span className="h-2.5 w-2.5 rounded-full bg-green-400" />
          <span
            className="ml-3 flex-1 text-[11px] rounded px-2 py-0.5 font-mono truncate"
            style={{ color: UI.textLabel, background: UI.white }}
          >
            https://&lt;device-host&gt;/config/
            {section.startsWith("net-")
              ? section.replace("net-", "network/")
              : section.startsWith("sys-")
                ? section.replace("sys-", "system/")
                : section.startsWith("dm-")
                  ? section.replace("dm-", "device-management/")
                  : section === "statistics" || section === "iapps"
                    ? section
                    : `local-traffic/${section}`}
            {section === "virtual-servers" ? `/${view === "properties" ? "properties" : "list"}` : ""}
          </span>
          <button onClick={onClose} className="text-sm px-2" style={{ color: UI.textLabel }}>
            ×
          </button>
        </div>

        {/* device console top bar */}
        <div className="flex items-center justify-between px-4 py-2" style={{ background: UI.bar }}>
          <div className="flex items-center gap-3">
            <span className="text-white font-bold text-lg tracking-tight flex items-center">
              <span
                className="inline-block h-2.5 w-2.5 rounded-sm mr-2"
                style={{ background: "var(--cyan, #ff5a1f)" }}
              />
              <span className="text-slate-300 font-normal text-xs">Device Configuration Utility</span>
            </span>
          </div>
          <div className="text-slate-300 text-xs">Partition: Common &nbsp;|&nbsp; admin &nbsp;|&nbsp; Log off</div>
        </div>

        <div className="flex flex-1 min-h-0">
          {/* left nav */}
          <div className="w-48 shrink-0 text-[13px] py-2 overflow-y-auto" style={{ background: UI.navy }}>
            <div
              className="px-3 py-1.5 text-slate-200 cursor-pointer hover:text-white"
              onClick={() => setSection("statistics")}
              style={section === "statistics" ? { background: UI.navyActive, color: "white", fontWeight: 600 } : undefined}
            >
              Statistics
            </div>
            <div
              className="px-3 py-1.5 text-slate-200 cursor-pointer hover:text-white"
              onClick={() => setSection("iapps")}
              style={section === "iapps" ? { background: UI.navyActive, color: "white", fontWeight: 600 } : undefined}
            >
              iApps
            </div>
            <div>
              <div
                className="px-3 py-1.5 text-slate-200"
                style={
                  ["virtual-servers", "pools", "nodes", "monitors", "profiles", "irules"].includes(section)
                    ? { background: UI.navyActive, color: "white", fontWeight: 600 }
                    : undefined
                }
              >
                Local Traffic
              </div>
              <div className="pl-4 pb-1">
                {(
                  [
                    ["virtual-servers", "Virtual Servers"],
                    ["pools", "Pools"],
                    ["nodes", "Nodes"],
                    ["monitors", "Monitors"],
                    ["profiles", "Profiles"],
                    ["irules", "iRules"],
                  ] as [Section, string][]
                ).map(([key, label]) => (
                  <div
                    key={key}
                    onClick={() => setSection(key)}
                    className="px-2 py-1 text-slate-300 text-[12px] cursor-pointer hover:text-white"
                    style={section === key ? { color: "white", fontWeight: 600 } : undefined}
                  >
                    {label}
                  </div>
                ))}
              </div>
            </div>
            <div>
              <div
                className="px-3 py-1.5 text-slate-200"
                style={
                  NETWORK_SUB_SECTIONS.some(([key]) => key === section)
                    ? { background: UI.navyActive, color: "white", fontWeight: 600 }
                    : undefined
                }
              >
                Network
              </div>
              <div className="pl-4 pb-1">
                {NETWORK_SUB_SECTIONS.map(([key, label]) => (
                  <div
                    key={key}
                    onClick={() => setSection(key)}
                    className="px-2 py-1 text-slate-300 text-[12px] cursor-pointer hover:text-white"
                    style={section === key ? { color: "white", fontWeight: 600 } : undefined}
                  >
                    {label}
                  </div>
                ))}
              </div>
            </div>
            <div>
              <div
                className="px-3 py-1.5 text-slate-200"
                style={
                  SYSTEM_SUB_SECTIONS.some(([key]) => key === section)
                    ? { background: UI.navyActive, color: "white", fontWeight: 600 }
                    : undefined
                }
              >
                System
              </div>
              <div className="pl-4 pb-1">
                {SYSTEM_SUB_SECTIONS.map(([key, label]) => (
                  <div
                    key={key}
                    onClick={() => setSection(key)}
                    className="px-2 py-1 text-slate-300 text-[12px] cursor-pointer hover:text-white"
                    style={section === key ? { color: "white", fontWeight: 600 } : undefined}
                  >
                    {label}
                  </div>
                ))}
              </div>
            </div>
            <div>
              <div
                className="px-3 py-1.5 text-slate-200"
                style={
                  DEVICE_MGMT_SUB_SECTIONS.some(([key]) => key === section)
                    ? { background: UI.navyActive, color: "white", fontWeight: 600 }
                    : undefined
                }
              >
                Device Management
              </div>
              <div className="pl-4 pb-1">
                {DEVICE_MGMT_SUB_SECTIONS.map(([key, label]) => (
                  <div
                    key={key}
                    onClick={() => setSection(key)}
                    className="px-2 py-1 text-slate-300 text-[12px] cursor-pointer hover:text-white"
                    style={section === key ? { color: "white", fontWeight: 600 } : undefined}
                  >
                    {label}
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* content */}
          <div className="flex-1 min-w-0 min-h-0 flex flex-col">
            <div
              className="px-4 py-2 text-[12px]"
              style={{ background: UI.breadcrumb, borderBottom: `1px solid ${UI.border}`, color: UI.textLabel }}
            >
              {SECTION_LABEL[section]}
              {section === "virtual-servers" && view === "properties" && (
                <>
                  {" » "}
                  <span className="font-medium" style={{ color: UI.textValue }}>
                    {openVip.name.replace("/Common/", "")}
                  </span>
                </>
              )}
            </div>
            {section === "virtual-servers" && (
              <div className="flex gap-4 px-4 pt-2 text-[13px]" style={{ borderBottom: `1px solid ${UI.border}` }}>
                <button
                  onClick={() => setView("list")}
                  className="pb-2 px-1"
                  style={view === "list" ? { borderBottom: `2px solid ${UI.navyActive}`, color: UI.navyActive, fontWeight: 600 } : { color: "#64748b" }}
                >
                  Virtual Server List
                </button>
                <button
                  onClick={() => setView("properties")}
                  className="pb-2 px-1"
                  style={view === "properties" ? { borderBottom: `2px solid ${UI.navyActive}`, color: UI.navyActive, fontWeight: 600 } : { color: "#64748b" }}
                >
                  Properties
                </button>
              </div>
            )}
            <div className="flex-1 overflow-auto p-4" style={{ background: "#f7f9fa" }}>
              {section === "pools" && <PoolListView pools={allPools} />}
              {section === "nodes" && <NodeListView nodes={allNodes} />}
              {section === "net-vlans" && <VlanListView vlans={allVlans} />}
              {section === "net-self-ips" && <SelfIpListView objects={systemObjects} />}
              {section === "net-trunks" && <TrunkListView objects={systemObjects} />}
              {section === "net-routes" && <RouteListView objects={systemObjects} />}
              {section === "net-route-domains" && <RouteDomainListView objects={systemObjects} />}
              {section === "net-dns-resolvers" && <DnsResolverListView objects={systemObjects} />}
              {section === "sys-configuration" && (
                <SystemInfoView
                  objects={systemObjects}
                  types={["sys global-settings", "sys management-ip"]}
                  emptyText="No device configuration (hostname, management IP) parsed from this session."
                />
              )}
              {section === "sys-ntp" && (
                <SystemInfoView objects={systemObjects} types={["sys ntp"]} emptyText="No NTP configuration parsed from this session." />
              )}
              {section === "sys-snmp" && (
                <SystemInfoView objects={systemObjects} types={["sys snmp"]} emptyText="No SNMP configuration parsed from this session." />
              )}
              {section === "sys-syslog" && (
                <SystemInfoView objects={systemObjects} types={["sys syslog"]} emptyText="No syslog configuration parsed from this session." />
              )}
              {section === "sys-mgmt-routes" && <ManagementRouteListView objects={systemObjects} />}
              {section === "sys-provisioning" && (
                <SystemInfoView
                  objects={systemObjects}
                  types={["sys provision"]}
                  emptyText="No provisioned module info parsed from this session."
                />
              )}
              {section === "sys-certificates" && <CertificateListView objects={systemObjects} sessionId={sessionId} />}
              {section === "sys-license" && (
                <>
                  <SystemInfoView
                    objects={systemObjects}
                    types={["sys software-version"]}
                    emptyText="No software version info was parsed (config/ucs_version wasn't found in this archive)."
                    sourceLabel="Raw parsed metadata (from config/ucs_version)"
                  />
                  <SystemInfoView
                    objects={systemObjects}
                    types={["sys platform"]}
                    emptyText="No hardware/VE platform info was parsed (config/.ucs_platform wasn't found in this archive)."
                    sourceLabel="Raw parsed metadata (from config/.ucs_platform)"
                  />
                  <SystemInfoView
                    objects={systemObjects.filter((o) => o.object_type === "sys license" && o.name === "current")}
                    types={["sys license"]}
                    emptyText="No license file was parsed (config/bigip.license wasn't found in this archive)."
                    sourceLabel="Raw parsed metadata (from config/bigip.license) -- not a TMOS config stanza"
                  />
                  {systemObjects.some((o) => o.object_type === "sys license-history") && (
                    <div className="mb-2">
                      <div className="text-[12px] mb-2" style={{ color: UI.textMuted }}>
                        Historical license backups found in this archive (config/bigip.license.&lt;date&gt;) -- real
                        re-licensing events over this device's lifetime, oldest first:
                      </div>
                      <SystemInfoView
                        objects={[...systemObjects]
                          .filter((o) => o.object_type === "sys license-history")
                          .sort((a, b) => a.name.localeCompare(b.name))}
                        types={["sys license-history"]}
                        emptyText=""
                        sourceLabel="Raw parsed metadata (historical config/bigip.license.<date> backup)"
                      />
                    </div>
                  )}
                </>
              )}
              {section === "dm-devices" && (
                <SystemInfoView objects={systemObjects} types={["cm device"]} emptyText="No device identity info parsed from this session." />
              )}
              {section === "dm-device-groups" && (
                <SystemInfoView
                  objects={systemObjects}
                  types={["cm device-group"]}
                  emptyText="No device (HA/sync) groups parsed from this session."
                />
              )}
              {section === "dm-traffic-groups" && (
                <SystemInfoView
                  objects={systemObjects}
                  types={["cm traffic-group"]}
                  emptyText="No traffic groups parsed from this session."
                />
              )}
              {section === "monitors" && <MonitorListView monitors={allMonitors} usedByMap={monitorUsedByMap} />}
              {section === "profiles" && <ProfileListView objects={systemObjects} usedByMap={profileUsedByMap} />}
              {section === "irules" && <IRuleListView objects={systemObjects} usedByMap={iruleUsedByMap} />}
              {section === "statistics" && (
                <EmptySectionNote text="Live statistics aren't available for a parsed configuration snapshot — this session has no traffic data, only the device's saved config." />
              )}
              {section === "iapps" && (
                <EmptySectionNote text="iApp templates aren't parsed from UCS/QKView archives in this tool." />
              )}
              {section === "virtual-servers" && (view === "list" ? (
                <VirtualServerListView vips={allVips} onOpen={openDifferentVip} />
              ) : (
                <>
                  <table className="w-full border-collapse" style={{ border: `1px solid ${UI.border}` }}>
                    <tbody>
                      <SectionHeader label="General Properties" />
                      <EditableRow label="Name" value={fields.name.replace("/Common/", "")} dirty={dirty.name} onChange={(v) => setFields((f) => ({ ...f, name: v.startsWith("/") ? v : `/Common/${v}` }))} />
                      <PropRow label="Description" value={entryToText(vipStanza.description)} />
                      <PropRow label="Partition / Path" value="Common" />
                      <PropRow label="Type" value="Standard" />
                      <PropRow
                        label="Source"
                        value={
                          entryToText(vipStanza.source) === "—"
                            ? "0.0.0.0/0 (default -- not explicitly set in config)"
                            : entryToText(vipStanza.source)
                        }
                      />
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
                      <PropRow label="Address Family" value={openVip.address_family.toUpperCase()} />
                      <PropRow label="Route Domain" value={openVip.route_domain !== null ? `%${openVip.route_domain}` : "—"} />
                      <PropRow label="Netmask" value={openVip.mask ?? "—"} />
                      <EditableRow
                        label="VLAN"
                        value={fields.vlan.replace("/Common/", "")}
                        dirty={dirty.vlan}
                        onChange={(v) => setFields((f) => ({ ...f, vlan: v.startsWith("/") ? v : `/Common/${v}` }))}
                      />
                      <PropRow label="VLAN Traffic" value={openVip.vlans_enabled ? "Enabled on" : "Disabled on"} />
                      <PropRow label="Source Port" value={entryToText(vipStanza["source-port"]) === "—" ? "Preserve" : entryToText(vipStanza["source-port"])} />
                      <PropRow label="Source Address Translation" value={openVip.snat_type ?? "None"} />
                      <PropRow label="Address Translation" value={entryToText(vipStanza["translate-address"]) === "—" ? "Enabled" : entryToText(vipStanza["translate-address"])} />
                      <PropRow label="Port Translation" value={entryToText(vipStanza["translate-port"]) === "—" ? "Enabled" : entryToText(vipStanza["translate-port"])} />
                      {vipStanza["serverssl-use-sni"] !== undefined && (
                        <PropRow label="SSL Server SNI" value={entryToText(vipStanza["serverssl-use-sni"])} />
                      )}
                      <PropRow label="Health Monitors" value={openVip.monitor_names.length ? openVip.monitor_names.map((m) => m.replace("/Common/", "")).join(", ") : "—"} />

                      <SectionHeader label="Configuration: Advanced" />
                      {profileFieldRows.map((r) => (
                        <PropRow key={r.label} label={r.label} value={r.value} />
                      ))}
                      <PropRow label="Access Policy" value="None" />
                      <PropRow label="Per-Request Policy" value="None" />
                      <PropRow label="HTTP Compression Profile" value="None" />
                      <PropRow label="Rate Class" value="Disabled" />
                      <PropRow label="Bandwidth Controller Policy" value="None" />
                      <PropRow label="DoS Protection Profile" value="Disabled" />
                      <PropRow label="IP Intelligence" value="Disabled" />
                      <PropRow label="Log Profile" value="None" />
                      <PropRow label="Request Logging Profile" value="None" />
                      <PropRow label="Connection Mirroring" value="Disabled" />
                      <PropRow label="Mirror Pool Member Connections" value="Disabled" />
                      <PropRow label="NAT64" value="Disabled" />
                      <PropRow label="Last Hop Pool" value="Auto" />
                      <tr>
                        <td colSpan={2} className="px-3 py-1.5 text-[11px]" style={{ color: UI.textMuted, background: UI.white }}>
                          The fields above with no attached object show TMOS's own default (not explicitly set
                          in this device's config) -- same as how the real GUI shows every field slot whether
                          or not it's configured.
                        </td>
                      </tr>

                      <SectionHeader label="Virtual Address Configuration" />
                      {virtualAddress ? (
                        <>
                          <PropRow label="ARP" value={entryToText(virtualAddress.arp)} />
                          <PropRow label="ICMP Echo" value={entryToText(virtualAddress["icmp-echo"])} />
                          <PropRow label="Route Advertisement" value={entryToText(virtualAddress["route-advertisement"])} />
                          <PropRow label="Traffic Group" value={entryToText(virtualAddress["traffic-group"]).replace("/Common/", "")} />
                        </>
                      ) : (
                        <PropRow label="Virtual Address" value="No matching ltm virtual-address object parsed for this destination." />
                      )}

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
                                    <th className="text-left px-3 py-1.5 border" style={{ borderColor: UI.border }}>Status</th>
                                    <th className="text-left px-3 py-1.5 border" style={{ borderColor: UI.border }}>Member</th>
                                    <th className="text-left px-3 py-1.5 border" style={{ borderColor: UI.border }}>Address</th>
                                    <th className="text-left px-3 py-1.5 border" style={{ borderColor: UI.border }}>Port</th>
                                    <th className="text-left px-3 py-1.5 border" style={{ borderColor: UI.border }}>Connection Limit</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {pool.members.map((m, i) => (
                                    <tr key={`${m.node_name}:${m.port}`} style={{ background: i % 2 ? UI.rowAlt : "white" }}>
                                      <td className="px-3 py-1.5 border" style={{ borderColor: UI.border }}>
                                        <StatusDot up={m.session_state !== "user-disabled"} />
                                        {m.session_state === "user-disabled" ? "Disabled" : "Available"}
                                      </td>
                                      <td className="px-3 py-1.5 border" style={{ borderColor: UI.border }}>{m.node_name.replace("/Common/", "")}</td>
                                      <td className="px-3 py-1.5 border font-mono" style={{ borderColor: UI.border }}>
                                        {nodesByName[m.node_name]?.address ?? "—"}
                                      </td>
                                      <td className="px-3 py-1.5 border" style={{ borderColor: UI.border }}>{m.port}</td>
                                      <td className="px-3 py-1.5 border" style={{ borderColor: UI.border }}>{m.connection_limit ?? "0 (unlimited)"}</td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </td>
                          </tr>
                          <tr>
                            <td colSpan={2} className="px-3 py-2" style={{ background: UI.white }}>
                              <RawStanzaBlock label="Raw parsed pool config (from bigip.conf)" json={pool.source_stanza_json} />
                            </td>
                          </tr>
                        </>
                      )}

                      <tr>
                        <td colSpan={2} className="px-3 py-2" style={{ background: UI.white, borderTop: `1px solid ${UI.border}` }}>
                          <RawStanzaBlock label="Raw parsed VIP config (from bigip.conf) — every field the archive had for this object" json={openVip.source_stanza_json} />
                        </td>
                      </tr>
                    </tbody>
                  </table>

                  <div className="mt-4 flex items-center gap-4 text-[12px]" style={{ color: UI.textLabel }}>
                    <label className="flex items-center gap-1.5 cursor-pointer">
                      <input
                        type="radio"
                        checked={outputMode === "changes_only"}
                        onChange={() => setOutputMode("changes_only")}
                      />
                      Apply changes only
                    </label>
                    <label className="flex items-center gap-1.5 cursor-pointer">
                      <input
                        type="radio"
                        checked={outputMode === "full_recreate"}
                        onChange={() => setOutputMode("full_recreate")}
                      />
                      Full recreate (whole TMSH for a new deployment)
                    </label>
                  </div>

                  <div className="mt-2 flex items-center gap-2">
                    <button
                      onClick={handlePreviewTmsh}
                      disabled={(outputMode === "changes_only" && !hasChanges) || busy}
                      className="px-4 py-1.5 text-[13px] text-white rounded disabled:opacity-40 disabled:cursor-not-allowed"
                      style={{ background: UI.navyActive }}
                    >
                      {busy ? "Computing…" : outputMode === "full_recreate" ? "Generate full TMSH" : "Update"}
                    </button>
                    <button
                      className="px-4 py-1.5 text-[13px] border rounded"
                      style={{ borderColor: UI.border, color: UI.textLabel }}
                    >
                      Delete
                    </button>
                    {!busy && outputMode === "changes_only" && hasChanges && (
                      <span className="text-[12px]" style={{ color: UI.textLabel }}>
                        Click Update to compute the real TMSH command for the field(s) you changed.
                      </span>
                    )}
                    {!busy && outputMode === "full_recreate" && (
                      <span className="text-[12px]" style={{ color: UI.textLabel }}>
                        Generates the complete tmsh create commands for this VIP (plus any edits above) — ready to run against a fresh device.
                      </span>
                    )}
                  </div>

                  {tmsh !== null && (
                    <div className="mt-4 rounded overflow-hidden" style={{ background: "#03050a" }}>
                      <div className="flex items-center gap-1.5 px-3 py-1.5" style={{ borderBottom: "1px solid rgba(255,255,255,0.08)" }}>
                        <span className="h-2 w-2 rounded-full" style={{ background: "#ff5c5c" }} />
                        <span className="h-2 w-2 rounded-full" style={{ background: "#ffbd2e" }} />
                        <span className="h-2 w-2 rounded-full" style={{ background: "#27c93f" }} />
                        <span className="ml-2 text-[10px]" style={{ color: UI.textDim }}>
                          tmsh — computed by the same engine as Step 5
                        </span>
                      </div>
                      <pre className="text-[12px] leading-relaxed p-3 overflow-auto max-h-40 whitespace-pre-wrap break-all font-mono" style={{ color: "#2bffb0" }}>
                        {tmsh}
                      </pre>
                    </div>
                  )}

                  {generated && (
                    <div className="mt-3 flex items-center gap-2">
                      <button
                        onClick={handleExportExcel}
                        disabled={exporting !== null}
                        className="px-3 py-1.5 text-[12px] border rounded disabled:opacity-40 disabled:cursor-not-allowed"
                        style={{ borderColor: UI.border, color: UI.textLabel }}
                      >
                        {exporting === "excel" ? "Exporting…" : "Export to Excel"}
                      </button>
                      <button
                        onClick={handleExportSop}
                        disabled={exporting !== null}
                        className="px-3 py-1.5 text-[12px] border rounded disabled:opacity-40 disabled:cursor-not-allowed"
                        style={{ borderColor: UI.border, color: UI.textLabel }}
                      >
                        {exporting === "sop" ? "Exporting…" : "Download SOP (.docx)"}
                      </button>
                      <span className="text-[11px]" style={{ color: UI.textDim }}>
                        Step-by-step, numbered TMSH — same export used by the Smart Migration wizard.
                      </span>
                    </div>
                  )}
                </>
              ))}
            </div>
          </div>
        </div>

        <div className="px-4 py-1.5 text-[11px] border-t" style={{ borderColor: UI.border, color: UI.textMuted }}>
          Preview only — recreates a device configuration console layout from parsed data; edits here compute real TMSH via the backend but are never applied to a live device.
        </div>
      </div>
    </div>,
    document.body,
  );
}
