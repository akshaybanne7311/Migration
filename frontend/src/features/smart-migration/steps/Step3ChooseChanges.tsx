import { useMemo, useState } from "react";
import { useValidatedSession, useVips } from "../../../api/queries";
import type { ChangeType, PoolMemberEdit } from "../../../api/types";
import { ChangeTypeCheckboxCard, TextField } from "../components/ChangeTypeCheckboxCard";
import { useWizardStore } from "../state/wizardStore";
import { INVALID_PORT_MESSAGE, isValidPortText } from "../utils/portValidation";

const CARD_ORDER: { type: ChangeType; label: string }[] = [
  { type: "vip_name", label: "VIP Name" },
  { type: "vip_ip_port", label: "VIP IP / Port" },
  { type: "pool_name", label: "Pool Name" },
  { type: "pool_members", label: "Pool Members" },
  { type: "vlans", label: "VLANs" },
  { type: "profiles", label: "Profiles" },
  { type: "persistence", label: "Persistence" },
  { type: "monitor", label: "Monitor" },
];

export function Step3ChooseChanges() {
  const chosenChangeTypes = useWizardStore((s) => s.chosenChangeTypes);
  const toggleChangeType = useWizardStore((s) => s.toggleChangeType);
  const commonChanges = useWizardStore((s) => s.commonChanges);
  const setCommonChange = useWizardStore((s) => s.setCommonChange);
  const selectedVipNames = useWizardStore((s) => s.selectedVipNames);
  const poolMemberEdits = useWizardStore((s) => s.poolMemberEdits);
  const setPoolMemberEdits = useWizardStore((s) => s.setPoolMemberEdits);

  const { sessionId } = useValidatedSession();
  const { data: vipsData } = useVips(sessionId);
  const selectedVips = useMemo(
    () => (vipsData?.items ?? []).filter((v) => selectedVipNames.has(v.name)),
    [vipsData, selectedVipNames],
  );

  const [poolMemberAddress, setPoolMemberAddress] = useState("");
  const [poolMemberPort, setPoolMemberPort] = useState("");
  const [vipIpPortText, setVipIpPortText] = useState(
    String(commonChanges.vip_ip_port?.payload.new_port ?? ""),
  );

  function applyPoolMemberReplaceAll() {
    if (!poolMemberAddress || !poolMemberPort || !isValidPortText(poolMemberPort)) return;
    const edits: PoolMemberEdit[] = Array.from(selectedVipNames).map((vipName) => ({
      vip_name: vipName,
      action: "replace_all",
      old_refs: [],
      new_refs: [{ address: poolMemberAddress, port: Number(poolMemberPort) }],
    }));
    setPoolMemberEdits(edits);
  }

  return (
    <div>
      <p className="text-sm text-slate-500 mb-4">
        Select the kinds of change you want to make. Detailed fields only appear once you check a
        card — this common change applies to all {selectedVipNames.size} selected VIP
        {selectedVipNames.size === 1 ? "" : "s"} unless overridden per VIP in the next step.
      </p>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {CARD_ORDER.map(({ type, label }) => (
          <ChangeTypeCheckboxCard
            key={type}
            label={label}
            checked={chosenChangeTypes.has(type)}
            onToggle={() => toggleChangeType(type)}
          >
            {type === "vip_name" && (
              <>
                <TextField
                  label="Find (in current VIP name)"
                  value={(commonChanges.vip_name?.payload.find as string) ?? ""}
                  onChange={(v) =>
                    setCommonChange("vip_name", {
                      ...commonChanges.vip_name?.payload,
                      find: v,
                    })
                  }
                />
                <TextField
                  label="Replace with"
                  value={(commonChanges.vip_name?.payload.replace as string) ?? ""}
                  onChange={(v) =>
                    setCommonChange("vip_name", {
                      ...commonChanges.vip_name?.payload,
                      replace: v,
                    })
                  }
                />
                {(() => {
                  const find = (commonChanges.vip_name?.payload.find as string) ?? "";
                  const replace = (commonChanges.vip_name?.payload.replace as string) ?? "";
                  if (!find) {
                    if (!replace) return null;
                    return (
                      <p className="text-xs text-amber-600">
                        Replace is set but Find is empty — nothing will be renamed. Fill in Find to
                        match the text you want to change.
                      </p>
                    );
                  }
                  const matches = selectedVips.filter((v) => v.name.includes(find));
                  return (
                    <p className="text-xs text-slate-400">
                      {matches.length} of {selectedVips.length} selected VIP
                      {selectedVips.length === 1 ? "" : "s"} affected
                      {matches.length > 0 && replace && (
                        <>
                          {" "}
                          — e.g.{" "}
                          <span className="font-mono">
                            {matches[0].name} → {matches[0].name.replace(find, replace)}
                          </span>
                        </>
                      )}
                    </p>
                  );
                })()}
              </>
            )}

            {type === "vip_ip_port" && (
              <>
                <TextField
                  label="New port (leave blank to keep current)"
                  value={vipIpPortText}
                  onChange={(v) => {
                    setVipIpPortText(v);
                    setCommonChange("vip_ip_port", {
                      ...commonChanges.vip_ip_port?.payload,
                      new_port: isValidPortText(v) && v.trim() ? Number(v) : undefined,
                    });
                  }}
                  placeholder="e.g. 5070"
                />
                {!isValidPortText(vipIpPortText) && (
                  <p className="text-xs text-amber-600">{INVALID_PORT_MESSAGE}</p>
                )}
              </>
            )}

            {type === "pool_name" && (
              <>
                <TextField
                  label="Find (in current pool name)"
                  value={(commonChanges.pool_name?.payload.find as string) ?? ""}
                  onChange={(v) =>
                    setCommonChange("pool_name", { ...commonChanges.pool_name?.payload, find: v })
                  }
                />
                <TextField
                  label="Replace with"
                  value={(commonChanges.pool_name?.payload.replace as string) ?? ""}
                  onChange={(v) =>
                    setCommonChange("pool_name", {
                      ...commonChanges.pool_name?.payload,
                      replace: v,
                    })
                  }
                />
                {!(commonChanges.pool_name?.payload.find as string) &&
                  (commonChanges.pool_name?.payload.replace as string) && (
                    <p className="text-xs text-amber-600">
                      Replace is set but Find is empty — nothing will be renamed. Fill in Find to
                      match the text you want to change.
                    </p>
                  )}
              </>
            )}

            {type === "pool_members" && (
              <div className="space-y-2">
                <p className="text-xs text-slate-400">
                  Replaces all members of each selected VIP's pool with a single new member. For
                  per-node control, use Node IP Changes in the next step instead.
                </p>
                <TextField
                  label="New member address"
                  value={poolMemberAddress}
                  onChange={setPoolMemberAddress}
                  placeholder="10.20.30.99 or 2001:db8::1"
                />
                <TextField
                  label="Port"
                  value={poolMemberPort}
                  onChange={setPoolMemberPort}
                  placeholder="80"
                />
                {!isValidPortText(poolMemberPort) && (
                  <p className="text-xs text-amber-600">{INVALID_PORT_MESSAGE}</p>
                )}
                <button
                  onClick={applyPoolMemberReplaceAll}
                  className="text-xs font-medium text-blue-700 hover:underline"
                >
                  Apply to selected VIPs ({poolMemberEdits.length} configured)
                </button>
              </div>
            )}

            {type === "vlans" && (
              <>
                <p className="text-xs text-slate-400 -mt-1 mb-1">
                  Fill both to replace. Old VLAN only removes it. New VLAN only adds it.
                </p>
                <TextField
                  label="Old VLAN"
                  value={(commonChanges.vlans?.payload.old_vlan as string) ?? ""}
                  onChange={(v) =>
                    setCommonChange("vlans", { ...commonChanges.vlans?.payload, old_vlan: v })
                  }
                  placeholder="/Common/MNP-VLAN-1699"
                />
                <TextField
                  label="New VLAN"
                  value={(commonChanges.vlans?.payload.new_vlan as string) ?? ""}
                  onChange={(v) =>
                    setCommonChange("vlans", { ...commonChanges.vlans?.payload, new_vlan: v })
                  }
                  placeholder="/Common/MNP-VLAN-1700"
                />
              </>
            )}

            {type === "profiles" && (
              <>
                <TextField
                  label="Add profiles (comma-separated)"
                  value={((commonChanges.profiles?.payload.add as string[]) ?? []).join(", ")}
                  onChange={(v) =>
                    setCommonChange("profiles", {
                      ...commonChanges.profiles?.payload,
                      add: v.split(",").map((s) => s.trim()).filter(Boolean),
                    })
                  }
                />
                <TextField
                  label="Remove profiles (comma-separated)"
                  value={((commonChanges.profiles?.payload.remove as string[]) ?? []).join(", ")}
                  onChange={(v) =>
                    setCommonChange("profiles", {
                      ...commonChanges.profiles?.payload,
                      remove: v.split(",").map((s) => s.trim()).filter(Boolean),
                    })
                  }
                />
              </>
            )}

            {type === "persistence" && (
              <TextField
                label="New persistence profile"
                value={(commonChanges.persistence?.payload.new_persistence as string) ?? ""}
                onChange={(v) => setCommonChange("persistence", { new_persistence: v })}
                placeholder="/Common/source_addr"
              />
            )}

            {type === "monitor" && (
              <TextField
                label="New monitor"
                value={(commonChanges.monitor?.payload.new_monitor as string) ?? ""}
                onChange={(v) => setCommonChange("monitor", { new_monitor: v })}
                placeholder="/Common/http-monitor"
              />
            )}
          </ChangeTypeCheckboxCard>
        ))}
      </div>
    </div>
  );
}
