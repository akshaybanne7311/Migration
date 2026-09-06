import type { CsvImportType } from "../api/types";

export const CSV_TEMPLATES: Record<CsvImportType, { label: string; hint: string; header: string; example: string }> = {
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

export function downloadCsvTemplate(csvType: CsvImportType) {
  const t = CSV_TEMPLATES[csvType];
  const blob = new Blob([`${t.header}\n${t.example}\n`], { type: "text/csv;charset=utf-8" });
  return import("file-saver").then(({ saveAs }) => saveAs(blob, `${csvType}-template.csv`));
}
