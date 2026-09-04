import { useEffect, useRef, useState } from "react";
import { api } from "../../../api/client";
import { usePools, useValidatedSession, useVips } from "../../../api/queries";
import type { CsvImportType, MemberRef, NodeChange, Pool, PoolMemberEdit, Vip, VipException } from "../../../api/types";
import { toast } from "../../../components/toastStore";
import { Button, Card, Checkbox } from "../../../components/ui";
import { useWizardStore } from "../state/wizardStore";
import { INVALID_PORT_MESSAGE, isValidPortText } from "../utils/portValidation";

const CSV_TEMPLATES: Record<CsvImportType, { label: string; hint: string; header: string; example: string }> = {
  vip_changes: {
    label: "Bulk VIP changes",
    hint: "Rename VIPs, re-IP/re-port them, or rename their pool (renames the real pool object too) — one row per VIP.",
    header: "source_vip,target_vip_name,target_vip_ip,target_vip_port,target_pool_name",
    example: "/Common/VS-EXAMPLE,/Common/VS-EXAMPLE-NEW,203.0.113.50,443,/Common/POOL-EXAMPLE-NEW",
  },
  vlan_rules: {
    label: "VLAN rules",
    hint: "Leave vip_name blank to apply a rule to every currently selected VIP.",
    header: "vip_name,action,old_vlan,new_vlan",
    example: ",replace,/Common/VLAN-OLD,/Common/VLAN-NEW",
  },
  pool_members: {
    label: "Pool member rules",
    hint: "Applies to every currently selected VIP whose pool matches source_pool. remove_node=true also deletes the node object (blocked if another pool still needs it).",
    header:
      "source_pool,action,source_member_node,source_member_port,target_node,target_address,target_port,remove_node",
    example: "/Common/POOL-EXAMPLE,add,,,,203.0.113.60,80,",
  },
  node_changes: {
    label: "Node IP changes",
    hint: "Same effect as the Node IP Changes table below, in bulk.",
    header: "source_node,new_ip,new_node_name",
    example: "/Common/NODE-EXAMPLE,203.0.113.70,",
  },
};

function CsvBulkImportPanel() {
  const { sessionId } = useValidatedSession();
  const selectedVipNames = useWizardStore((s) => s.selectedVipNames);
  const exceptions = useWizardStore((s) => s.exceptions);
  const setExceptions = useWizardStore((s) => s.setExceptions);
  const nodeChanges = useWizardStore((s) => s.nodeChanges);
  const setNodeChanges = useWizardStore((s) => s.setNodeChanges);
  const poolMemberEdits = useWizardStore((s) => s.poolMemberEdits);
  const setPoolMemberEdits = useWizardStore((s) => s.setPoolMemberEdits);

  const [csvType, setCsvType] = useState<CsvImportType>("vip_changes");
  const [busy, setBusy] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  function downloadTemplate() {
    const t = CSV_TEMPLATES[csvType];
    const blob = new Blob([`${t.header}\n${t.example}\n`], { type: "text/csv;charset=utf-8" });
    import("file-saver").then(({ saveAs }) => saveAs(blob, `${csvType}-template.csv`));
  }

  async function handleFile(file: File) {
    setBusy(true);
    try {
      const result = await api.importCsv(
        sessionId as string,
        csvType,
        Array.from(selectedVipNames),
        file,
      );

      if (result.exceptions.length > 0) {
        // Later rows win for the same VIP+change-type, matching how
        // exceptions are merged everywhere else in the wizard.
        const byVip = new Map(exceptions.map((e) => [e.vip_name, e]));
        for (const incoming of result.exceptions) {
          const existing = byVip.get(incoming.vip_name);
          byVip.set(incoming.vip_name, {
            vip_name: incoming.vip_name,
            overrides: { ...existing?.overrides, ...incoming.overrides },
          });
        }
        setExceptions(Array.from(byVip.values()));
      }
      if (result.node_changes.length > 0) {
        setNodeChanges([...nodeChanges, ...result.node_changes]);
      }
      if (result.pool_member_edits.length > 0) {
        setPoolMemberEdits([...poolMemberEdits, ...result.pool_member_edits]);
      }

      toast("success", `Imported ${result.row_count} row${result.row_count === 1 ? "" : "s"} from CSV.`);
    } catch {
      // The axios interceptor already toasts the error message (including
      // the parser's row-level detail from the backend).
    } finally {
      setBusy(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  return (
    <Card className="p-4">
      <div className="text-sm font-medium text-slate-800 mb-1">Bulk import from CSV</div>
      <p className="text-xs text-slate-500 mb-3">
        Prepare changes offline in a spreadsheet and import them in one shot instead of adding
        exceptions one VIP at a time. Imported rows merge into the tables on this page — review
        them below before generating.
      </p>

      <div className="grid grid-cols-2 gap-2 mb-2">
        <select
          className="border border-slate-300 rounded-md px-2 py-1.5 text-xs col-span-2"
          value={csvType}
          onChange={(e) => setCsvType(e.target.value as CsvImportType)}
        >
          {(Object.keys(CSV_TEMPLATES) as CsvImportType[]).map((t) => (
            <option key={t} value={t}>
              {CSV_TEMPLATES[t].label}
            </option>
          ))}
        </select>
      </div>
      <p className="text-xs text-slate-400 mb-3">{CSV_TEMPLATES[csvType].hint}</p>

      <div className="flex items-center gap-2">
        <input
          ref={fileInputRef}
          type="file"
          accept=".csv,text/csv"
          disabled={busy}
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) handleFile(file);
          }}
          className="text-xs"
        />
        <Button variant="secondary" onClick={downloadTemplate}>
          Download template
        </Button>
      </div>
    </Card>
  );
}

function NodeChangesPanel() {
  const nodeChanges = useWizardStore((s) => s.nodeChanges);
  const setNodeChanges = useWizardStore((s) => s.setNodeChanges);
  const [draft, setDraft] = useState<NodeChange>({ old_node_ref: "", new_ip: "", new_node_name: "" });

  function addRow() {
    if (!draft.old_node_ref || !draft.new_ip) return;
    setNodeChanges([...nodeChanges, { ...draft, new_node_name: draft.new_node_name || undefined }]);
    setDraft({ old_node_ref: "", new_ip: "", new_node_name: "" });
  }

  function removeRow(idx: number) {
    setNodeChanges(nodeChanges.filter((_, i) => i !== idx));
  }

  return (
    <Card className="p-4">
      <div className="text-sm font-medium text-slate-800 mb-1">Node IP Changes</div>
      <p className="text-xs text-slate-500 mb-3">
        Dependency-level: if the same node is used by multiple pools or VIPs, it is created once
        and every pool member referencing it is updated automatically — you don't manage this per
        VIP.
      </p>

      {nodeChanges.length > 0 && (
        <table className="w-full text-xs mb-3">
          <thead className="text-slate-400 uppercase tracking-wide">
            <tr>
              <th className="text-left py-1">Old node / IP</th>
              <th className="text-left py-1">New IP</th>
              <th className="text-left py-1">New node name</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {nodeChanges.map((nc, idx) => (
              <tr key={idx} className="border-t border-slate-100">
                <td className="py-1.5">{nc.old_node_ref}</td>
                <td className="py-1.5">{nc.new_ip}</td>
                <td className="py-1.5">{nc.new_node_name || "—"}</td>
                <td className="py-1.5 text-right">
                  <button onClick={() => removeRow(idx)} className="text-slate-400 hover:text-red-600">
                    ×
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <div className="grid grid-cols-3 gap-2">
        <input
          className="border border-slate-300 rounded-md px-2 py-1.5 text-xs"
          placeholder="Old node name or IP"
          value={draft.old_node_ref}
          onChange={(e) => setDraft({ ...draft, old_node_ref: e.target.value })}
        />
        <input
          className="border border-slate-300 rounded-md px-2 py-1.5 text-xs"
          placeholder="New IP"
          value={draft.new_ip}
          onChange={(e) => setDraft({ ...draft, new_ip: e.target.value })}
        />
        <input
          className="border border-slate-300 rounded-md px-2 py-1.5 text-xs"
          placeholder="New node name (optional)"
          value={draft.new_node_name ?? ""}
          onChange={(e) => setDraft({ ...draft, new_node_name: e.target.value })}
        />
      </div>
      <div className="mt-2">
        <Button variant="secondary" onClick={addRow}>
          Add node change
        </Button>
      </div>
    </Card>
  );
}

function PoolMemberExceptionEditor({ vip, pool }: { vip: Vip; pool: Pool | undefined }) {
  const poolMemberEdits = useWizardStore((s) => s.poolMemberEdits);
  const setPoolMemberEdits = useWizardStore((s) => s.setPoolMemberEdits);
  const [removeKeys, setRemoveKeys] = useState<Set<string>>(new Set());
  const [pendingAdds, setPendingAdds] = useState<MemberRef[]>([]);
  const [addAddress, setAddAddress] = useState("");
  const [addPort, setAddPort] = useState("");
  const [addNodeName, setAddNodeName] = useState("");

  useEffect(() => {
    setRemoveKeys(new Set());
    setPendingAdds([]);
  }, [vip.name]);

  function toggleRemove(key: string) {
    setRemoveKeys((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  function addPendingMember() {
    if (!addAddress || !addPort || !isValidPortText(addPort)) return;
    setPendingAdds((prev) => [
      ...prev,
      { address: addAddress, port: Number(addPort), node_name: addNodeName || undefined },
    ]);
    setAddAddress("");
    setAddPort("");
    setAddNodeName("");
  }

  function apply() {
    const old_refs: MemberRef[] = (pool?.members ?? [])
      .filter((m) => removeKeys.has(`${m.node_name}:${m.port}`))
      .map((m) => ({ node_name: m.node_name, port: m.port }));
    if (old_refs.length === 0 && pendingAdds.length === 0) return;
    const edit: PoolMemberEdit = {
      vip_name: vip.name,
      action: "replace_selected",
      old_refs,
      new_refs: pendingAdds,
    };
    setPoolMemberEdits([...poolMemberEdits.filter((e) => e.vip_name !== vip.name), edit]);
    setRemoveKeys(new Set());
    setPendingAdds([]);
  }

  if (!pool || pool.members.length === 0) {
    return (
      <p className="text-xs text-slate-400 mt-2">
        {vip.pool_name ? "No members parsed for this VIP's pool." : "This VIP has no pool."}
      </p>
    );
  }

  const existingEdit = poolMemberEdits.find((e) => e.vip_name === vip.name);

  return (
    <div className="mt-2 border border-slate-200 rounded-md p-3">
      <div className="text-xs font-medium text-slate-700 mb-2">Pool members — {pool.name}</div>
      {existingEdit && (
        <p className="text-xs text-emerald-700 mb-2">
          A pool member change is already queued for this VIP ({existingEdit.old_refs.length} removed,{" "}
          {existingEdit.new_refs.length} added). Applying below replaces it.
        </p>
      )}
      <div className="space-y-1 mb-2">
        {pool.members.map((m) => {
          const key = `${m.node_name}:${m.port}`;
          const checked = removeKeys.has(key);
          return (
            <label key={key} className="flex items-center gap-2 text-xs cursor-pointer">
              <input type="checkbox" checked={checked} onChange={() => toggleRemove(key)} />
              <span className="font-mono">
                {m.node_name}:{m.port}
              </span>
              {checked && <span className="text-red-600">remove</span>}
            </label>
          );
        })}
      </div>

      {pendingAdds.length > 0 && (
        <div className="space-y-1 mb-2">
          {pendingAdds.map((r, i) => (
            <div
              key={i}
              className="flex items-center justify-between text-xs bg-emerald-50 rounded px-2 py-1"
            >
              <span className="font-mono">
                {r.node_name ? `${r.node_name} ` : ""}
                {r.address}:{r.port} (add)
              </span>
              <button
                onClick={() => setPendingAdds(pendingAdds.filter((_, idx) => idx !== i))}
                className="text-slate-400 hover:text-red-600"
              >
                ×
              </button>
            </div>
          ))}
        </div>
      )}

      <div className="grid grid-cols-3 gap-2 mb-2">
        <input
          className="border border-slate-300 rounded-md px-2 py-1.5 text-xs"
          placeholder="New member address"
          value={addAddress}
          onChange={(e) => setAddAddress(e.target.value)}
        />
        <input
          className="border border-slate-300 rounded-md px-2 py-1.5 text-xs"
          placeholder="Port"
          value={addPort}
          onChange={(e) => setAddPort(e.target.value)}
        />
        <input
          className="border border-slate-300 rounded-md px-2 py-1.5 text-xs"
          placeholder="Node name (optional)"
          value={addNodeName}
          onChange={(e) => setAddNodeName(e.target.value)}
        />
      </div>
      {!isValidPortText(addPort) && <p className="text-xs text-amber-600 mb-2">{INVALID_PORT_MESSAGE}</p>}
      <div className="flex items-center gap-3">
        <button onClick={addPendingMember} className="text-xs font-medium text-blue-700 hover:underline">
          + Add to list
        </button>
        <Button variant="secondary" onClick={apply}>
          Apply pool member changes
        </Button>
      </div>
    </div>
  );
}

function ExceptionsAccordion() {
  const { sessionId } = useValidatedSession();
  const selectedVipNames = useWizardStore((s) => s.selectedVipNames);
  const { data: vipsData } = useVips(sessionId);
  const { data: poolsData } = usePools(sessionId);
  const exceptions = useWizardStore((s) => s.exceptions);
  const setExceptions = useWizardStore((s) => s.setExceptions);

  const [open, setOpen] = useState(false);
  const [vipName, setVipName] = useState("");
  const [targetIp, setTargetIp] = useState("");
  const [targetPort, setTargetPort] = useState("");
  const [targetPool, setTargetPool] = useState("");

  const selectedVips = (vipsData?.items ?? []).filter((v) => selectedVipNames.has(v.name));
  const poolsByName = Object.fromEntries((poolsData?.items ?? []).map((p) => [p.name, p]));
  const selectedVip = selectedVips.find((v) => v.name === vipName);

  function addException() {
    if (!vipName || !isValidPortText(targetPort)) return;
    const vip = selectedVips.find((v) => v.name === vipName);
    const overrides: VipException["overrides"] = {};
    if (targetIp || targetPort) {
      overrides.vip_ip_port = {
        new_address: targetIp || undefined,
        new_port: targetPort ? Number(targetPort) : undefined,
      };
    }
    if (targetPool && vip?.pool_name) {
      overrides.pool_name = { find: vip.pool_name, replace: targetPool };
    }
    if (Object.keys(overrides).length === 0) return;

    setExceptions([...exceptions.filter((e) => e.vip_name !== vipName), { vip_name: vipName, overrides }]);
    setVipName("");
    setTargetIp("");
    setTargetPort("");
    setTargetPool("");
  }

  function removeException(name: string) {
    setExceptions(exceptions.filter((e) => e.vip_name !== name));
  }

  return (
    <Card className="p-4">
      <button
        onClick={() => setOpen((v) => !v)}
        className="text-sm font-medium text-slate-800 flex items-center gap-2"
      >
        {open ? "▾" : "▸"} Individual Exceptions ({exceptions.length})
      </button>

      {open && (
        <div className="mt-3">
          <p className="text-xs text-slate-500 mb-3">
            Only the VIPs listed here differ from the common changes. Most operators won't need
            this.
          </p>

          {exceptions.length > 0 && (
            <div className="space-y-1.5 mb-3">
              {exceptions.map((e) => (
                <div
                  key={e.vip_name}
                  className="flex items-center justify-between bg-slate-50 rounded-md px-3 py-1.5 text-xs"
                >
                  <div>
                    <span className="font-medium text-slate-700">{e.vip_name}</span>
                    <span className="text-slate-400 ml-2">
                      {Object.keys(e.overrides).join(", ")}
                    </span>
                  </div>
                  <button
                    onClick={() => removeException(e.vip_name)}
                    className="text-slate-400 hover:text-red-600"
                  >
                    ×
                  </button>
                </div>
              ))}
            </div>
          )}

          <div className="grid grid-cols-2 gap-2 mb-2">
            <select
              className="border border-slate-300 rounded-md px-2 py-1.5 text-xs col-span-2"
              value={vipName}
              onChange={(e) => setVipName(e.target.value)}
            >
              <option value="">Choose a selected VIP…</option>
              {selectedVips.map((v) => (
                <option key={v.name} value={v.name}>
                  {v.name}
                </option>
              ))}
            </select>
            <input
              className="border border-slate-300 rounded-md px-2 py-1.5 text-xs"
              placeholder="Target IP"
              value={targetIp}
              onChange={(e) => setTargetIp(e.target.value)}
            />
            <input
              className="border border-slate-300 rounded-md px-2 py-1.5 text-xs"
              placeholder="Target Port"
              value={targetPort}
              onChange={(e) => setTargetPort(e.target.value)}
            />
            <input
              className="border border-slate-300 rounded-md px-2 py-1.5 text-xs col-span-2"
              placeholder="Target Pool"
              value={targetPool}
              onChange={(e) => setTargetPool(e.target.value)}
            />
          </div>
          {!isValidPortText(targetPort) && (
            <p className="text-xs text-amber-600 mb-2">{INVALID_PORT_MESSAGE}</p>
          )}
          <Button variant="secondary" onClick={addException}>
            Add exception
          </Button>

          {selectedVip && (
            <PoolMemberExceptionEditor
              vip={selectedVip}
              pool={selectedVip.pool_name ? poolsByName[selectedVip.pool_name] : undefined}
            />
          )}
        </div>
      )}
    </Card>
  );
}

export function Step4CommonAndExceptions() {
  const createNetworkObjects = useWizardStore((s) => s.createNetworkObjects);
  const setCreateNetworkObjects = useWizardStore((s) => s.setCreateNetworkObjects);

  return (
    <div className="space-y-4">
      <CsvBulkImportPanel />
      <NodeChangesPanel />
      <ExceptionsAccordion />
      <Card className="p-4">
        <Checkbox
          checked={createNetworkObjects}
          onChange={setCreateNetworkObjects}
          label="Create device network objects (net vlan) for new VLANs"
        />
        <p className="text-xs text-slate-500 mt-2 pl-6">
          VLAN object creation is OFF by default for platforms where VLANs are typically managed
          externally. When off, only the VIP's VLAN binding is changed.
        </p>
      </Card>
    </div>
  );
}
