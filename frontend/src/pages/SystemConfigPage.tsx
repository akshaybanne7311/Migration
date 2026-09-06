import type { ReactNode } from "react";
import { api } from "../api/client";
import { useSystemObjects, useValidatedSession, useVlans } from "../api/queries";
import type { SystemObject } from "../api/types";
import { Card, EmptyState, PageHeader } from "../components/ui";

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

function ObjectTable({
  title,
  rows,
  columns,
}: {
  title: string;
  rows: SystemObject[];
  columns: { label: string; get: (entries: Record<string, unknown>, obj: SystemObject) => ReactNode }[];
}) {
  if (rows.length === 0) return null;
  return (
    <Card className="overflow-hidden mb-4">
      <div className="px-3 py-2 text-sm font-medium text-slate-800 border-b border-slate-100">
        {title} <span className="text-slate-400 font-normal">({rows.length})</span>
      </div>
      <table className="w-full text-sm">
        <thead className="bg-slate-50 text-slate-500 text-xs uppercase tracking-wide">
          <tr>
            {columns.map((c) => (
              <th key={c.label} className="text-left px-3 py-2 font-medium">
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const entries = parseEntries(r.entries_json);
            return (
              <tr key={r.name} className="border-t border-slate-100">
                {columns.map((c) => (
                  <td key={c.label} className="px-3 py-2 text-slate-700 break-words">
                    {c.get(entries, r)}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </Card>
  );
}

const stripCommon = (s: string) => s.replace("/Common/", "");

export function SystemConfigPage() {
  const { sessionId } = useValidatedSession();
  const { data: vlansData, isLoading: vlansLoading } = useVlans(sessionId);
  const { data: sysData, isLoading: sysLoading } = useSystemObjects(sessionId);

  if (!sessionId) {
    return (
      <div>
        <PageHeader title="System Config" />
        <EmptyState title="No session selected" />
      </div>
    );
  }

  const objects = sysData?.items ?? [];
  const isLoading = vlansLoading || sysLoading;
  const nothingParsed = !isLoading && (vlansData?.items.length ?? 0) === 0 && objects.length === 0;

  return (
    <div>
      <PageHeader
        title="System Config"
        subtitle="Network and system-layer configuration parsed from bigip_base.conf — device identity, HA, VLANs, self IPs, routing, and device settings."
      />
      {isLoading && <div className="text-sm text-slate-400">Loading…</div>}
      {nothingParsed && <EmptyState title="No network/system objects parsed" />}

      <ObjectTable
        title="SSL Certificates (real PEM files from the archive)"
        rows={objectsOfType(objects, "x509 certificate")}
        columns={[
          { label: "Common Name", get: (e, o) => entryToText(e.subject_cn ?? o.name) },
          { label: "Issuer", get: (e) => entryToText(e.issuer_cn) },
          { label: "Expires", get: (e) => entryToText(e.not_after).slice(0, 10) },
          {
            label: "Status",
            get: (e) => {
              const days = e.days_until_expiry as number | undefined;
              if (e.is_expired) return `expired ${Math.abs(days ?? 0)}d ago`;
              if (typeof days === "number" && days <= 60) return `expires in ${days}d`;
              return "OK";
            },
          },
          { label: "Self-signed", get: (e) => (e.is_self_signed ? "yes" : "no") },
          {
            label: "Source file(s)",
            get: (e) => (Array.isArray(e.source_paths) ? (e.source_paths as string[]).join(", ") : "—"),
          },
          {
            label: "Original file",
            get: (e) => {
              const fingerprint = typeof e.fingerprint_sha256 === "string" ? e.fingerprint_sha256 : "";
              if (!sessionId || !fingerprint) return "—";
              return (
                <a
                  href={api.certificateDownloadUrl(sessionId, fingerprint)}
                  className="text-sky-700 underline hover:text-sky-900"
                >
                  Download .crt
                </a>
              );
            },
          },
        ]}
      />

      <ObjectTable
        title="Software Version (config/ucs_version)"
        rows={objectsOfType(objects, "sys software-version")}
        columns={[
          { label: "Product", get: (e) => entryToText(e.product) },
          { label: "Version", get: (e) => entryToText(e.version) },
          { label: "Build", get: (e) => entryToText(e.build) },
          { label: "Edition", get: (e) => entryToText(e.edition) },
          { label: "Date", get: (e) => entryToText(e.date) },
        ]}
      />

      <ObjectTable
        title="Hardware / VE Platform (config/.ucs_platform)"
        rows={objectsOfType(objects, "sys platform")}
        columns={[
          { label: "Platform", get: (e) => entryToText(e.platform) },
          { label: "Family", get: (e) => entryToText(e.family) },
          { label: "Host", get: (e) => entryToText(e.host) },
          { label: "Systype", get: (e) => entryToText(e.systype) },
        ]}
      />

      <ObjectTable
        title="License (config/bigip.license -- not sys provision)"
        rows={objects.filter((o) => o.object_type === "sys license" && o.name === "current")}
        columns={[
          { label: "Usage", get: (e) => entryToText(e.usage) },
          { label: "Platform ID", get: (e) => entryToText(e.platform_id) },
          { label: "Licensed Date", get: (e) => entryToText(e.licensed_date) },
          { label: "Service Check Date", get: (e) => entryToText(e.service_check_date) },
          { label: "Registration Key", get: (e) => entryToText(e.registration_key) },
          { label: "Active Modules", get: (e) => entryToText(e.active_modules) },
        ]}
      />

      <ObjectTable
        title="License History (config/bigip.license.<date> backups)"
        rows={objectsOfType(objects, "sys license-history").sort((a, b) => a.name.localeCompare(b.name))}
        columns={[
          { label: "Date", get: (_e, o) => o.name },
          { label: "Usage", get: (e) => entryToText(e.usage) },
          { label: "Licensed Date", get: (e) => entryToText(e.licensed_date) },
          { label: "Service Check Date", get: (e) => entryToText(e.service_check_date) },
          { label: "Active Modules", get: (e) => entryToText(e.active_modules) },
        ]}
      />

      <ObjectTable
        title="Device Identity"
        rows={objectsOfType(objects, "cm device")}
        columns={[
          { label: "Hostname", get: (e) => entryToText(e.hostname) },
          { label: "Management IP", get: (e) => entryToText(e["management-ip"]) },
          { label: "Config Sync IP", get: (e) => entryToText(e["configsync-ip"]) },
          { label: "Build", get: (e) => entryToText(e.build) },
          { label: "Edition", get: (e) => entryToText(e.edition) },
        ]}
      />

      <ObjectTable
        title="Device Groups (HA / Sync)"
        rows={objectsOfType(objects, "cm device-group")}
        columns={[
          { label: "Name", get: (_e, o) => stripCommon(o.name) },
          { label: "Type", get: (e) => entryToText(e.type) },
          { label: "Auto Sync", get: (e) => entryToText(e["auto-sync"]) },
          { label: "Devices", get: (e) => entryToText(e.devices) },
        ]}
      />

      <ObjectTable
        title="Traffic Groups"
        rows={objectsOfType(objects, "cm traffic-group")}
        columns={[
          { label: "Name", get: (_e, o) => stripCommon(o.name) },
          { label: "Failover Method", get: (e) => entryToText(e["failover-method"]) },
          { label: "HA Order", get: (e) => entryToText(e["ha-order"]) },
        ]}
      />

      {vlansData && vlansData.items.length > 0 && (
        <Card className="overflow-hidden mb-4">
          <div className="px-3 py-2 text-sm font-medium text-slate-800 border-b border-slate-100">
            VLANs <span className="text-slate-400 font-normal">({vlansData.items.length})</span>
          </div>
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-slate-500 text-xs uppercase tracking-wide">
              <tr>
                <th className="text-left px-3 py-2 font-medium">VLAN</th>
                <th className="text-right px-3 py-2 font-medium">Tag</th>
                <th className="text-left px-3 py-2 font-medium">Interfaces</th>
              </tr>
            </thead>
            <tbody>
              {vlansData.items.map((v) => (
                <tr key={v.name} className="border-t border-slate-100">
                  <td className="px-3 py-2 font-medium text-slate-800">{v.name}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{v.tag ?? "—"}</td>
                  <td className="px-3 py-2 text-slate-600">{v.interfaces.join(", ") || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}

      <ObjectTable
        title="Self IPs"
        rows={objectsOfType(objects, "net self")}
        columns={[
          { label: "Name", get: (_e, o) => stripCommon(o.name) },
          { label: "Address", get: (e) => entryToText(e.address) },
          { label: "VLAN", get: (e) => stripCommon(entryToText(e.vlan)) },
          { label: "Traffic Group", get: (e) => stripCommon(entryToText(e["traffic-group"])) },
          { label: "Port Lockdown", get: (e) => entryToText(e["allow-service"]) },
        ]}
      />

      <ObjectTable
        title="Trunks"
        rows={objectsOfType(objects, "net trunk")}
        columns={[
          { label: "Name", get: (_e, o) => o.name },
          { label: "Interfaces", get: (e) => entryToText(e.interfaces) },
        ]}
      />

      <ObjectTable
        title="Route Domains"
        rows={objectsOfType(objects, "net route-domain")}
        columns={[
          { label: "Name", get: (_e, o) => stripCommon(o.name) },
          { label: "ID", get: (e) => entryToText(e.id) },
          { label: "VLANs", get: (e) => entryToText(e.vlans) },
        ]}
      />

      <ObjectTable
        title="Static Routes"
        rows={objectsOfType(objects, "net route")}
        columns={[
          { label: "Name", get: (_e, o) => stripCommon(o.name) },
          { label: "Network", get: (e) => entryToText(e.network) },
          { label: "Gateway", get: (e) => entryToText(e.gw) },
        ]}
      />

      <ObjectTable
        title="Management Routes"
        rows={objectsOfType(objects, "sys management-route")}
        columns={[
          { label: "Name", get: (_e, o) => stripCommon(o.name) },
          { label: "Network", get: (e) => entryToText(e.network) },
          { label: "Gateway", get: (e) => entryToText(e.gateway) },
        ]}
      />

      <ObjectTable
        title="DNS Resolvers"
        rows={objectsOfType(objects, "net dns-resolver")}
        columns={[
          { label: "Name", get: (_e, o) => stripCommon(o.name) },
          {
            label: "Forward Zones",
            get: (e) => {
              const zones = e["forward-zones"];
              return zones && typeof zones === "object" ? Object.keys(zones).join(", ") || "—" : "—";
            },
          },
        ]}
      />

      <ObjectTable
        title="Resource Provisioning"
        rows={objectsOfType(objects, "sys provision")}
        columns={[
          { label: "Module", get: (_e, o) => o.name },
          { label: "Level", get: (e) => entryToText(e.level) },
        ]}
      />

      <ObjectTable
        title="Device Configuration"
        rows={objectsOfType(objects, "sys global-settings").concat(objectsOfType(objects, "sys management-ip"))}
        columns={[
          { label: "Object", get: (_e, o) => (o.name ? `${o.object_type} ${o.name}` : o.object_type) },
          {
            label: "Fields",
            get: (e) =>
              Object.keys(e).length
                ? Object.entries(e)
                    .map(([k, v]) => {
                      const text = entryToText(v);
                      return `${k}=${text.length > 80 ? `${text.slice(0, 80)}…` : text}`;
                    })
                    .join("; ")
                : "—",
          },
        ]}
      />

      <ObjectTable
        title="NTP"
        rows={objectsOfType(objects, "sys ntp")}
        columns={[{ label: "Servers", get: (e) => entryToText(e.servers) }, { label: "Timezone", get: (e) => entryToText(e.timezone) }]}
      />

      <ObjectTable
        title="SNMP"
        rows={objectsOfType(objects, "sys snmp")}
        columns={[
          { label: "Allowed Addresses", get: (e) => entryToText(e["allowed-addresses"]) },
          { label: "Communities", get: (e) => entryToText(e.communities) },
        ]}
      />

      <ObjectTable
        title="Syslog"
        rows={objectsOfType(objects, "sys syslog")}
        columns={[{ label: "Remote Servers", get: (e) => entryToText(e["remote-servers"]) }]}
      />
    </div>
  );
}
