import { useState } from "react";
import { useValidatedSession, useVips } from "../../../api/queries";
import type { NodeChange, VipException } from "../../../api/types";
import { Button, Card, Checkbox } from "../../../components/ui";
import { useWizardStore } from "../state/wizardStore";

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

function ExceptionsAccordion() {
  const { sessionId } = useValidatedSession();
  const selectedVipNames = useWizardStore((s) => s.selectedVipNames);
  const { data: vipsData } = useVips(sessionId);
  const exceptions = useWizardStore((s) => s.exceptions);
  const setExceptions = useWizardStore((s) => s.setExceptions);

  const [open, setOpen] = useState(false);
  const [vipName, setVipName] = useState("");
  const [targetIp, setTargetIp] = useState("");
  const [targetPort, setTargetPort] = useState("");
  const [targetPool, setTargetPool] = useState("");

  const selectedVips = (vipsData?.items ?? []).filter((v) => selectedVipNames.has(v.name));

  function addException() {
    if (!vipName) return;
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
          <Button variant="secondary" onClick={addException}>
            Add exception
          </Button>
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
