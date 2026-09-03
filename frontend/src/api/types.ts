export type AddressFamily = "ipv4" | "ipv6";

export interface Profile {
  name: string;
  context: string | null;
}

export interface PoolMember {
  pool_name: string;
  node_name: string;
  port: number;
  session_state: string | null;
  connection_limit: number | null;
  source_stanza_json: string;
}

export interface Pool {
  name: string;
  partition: string;
  monitor_names: string[];
  members: PoolMember[];
  source_stanza_json: string;
}

export interface NodeObj {
  name: string;
  address: string;
  address_family: AddressFamily;
  partition: string;
  state: string | null;
  source_stanza_json: string;
  pool_count?: number;
  vip_count?: number;
}

export interface Vlan {
  name: string;
  tag: number | null;
  interfaces: string[];
  source_stanza_json: string;
}

export interface Vip {
  name: string;
  partition: string;
  destination_address: string;
  destination_port: number;
  address_family: AddressFamily;
  route_domain: number | null;
  ip_protocol: string | null;
  pool_name: string | null;
  vlans: string[];
  vlans_enabled: boolean;
  profiles: Profile[];
  persistence: string | null;
  snat_type: string | null;
  irules: string[];
  mask: string | null;
  monitor_names: string[];
  source_stanza_json: string;
}

export interface SessionOut {
  id: string;
  name: string;
  source_filename: string;
  status: "parsing" | "ready" | "failed";
  error_message: string | null;
  created_at: string;
  vip_count: number;
  pool_count: number;
  node_count: number;
  vlan_count: number;
}

export interface SelectionCounts {
  vips: number;
  pools: number;
  pool_members: number;
  nodes: number;
  vlan_refs: number;
}

export type ChangeType =
  | "vip_name"
  | "vip_ip_port"
  | "pool_name"
  | "pool_members"
  | "vlans"
  | "profiles"
  | "persistence"
  | "monitor";

export interface CommonChange {
  change_type: ChangeType;
  payload: Record<string, unknown>;
}

export interface MemberRef {
  node_name?: string | null;
  address?: string | null;
  new_node_name?: string | null;
  port: number;
}

export interface PoolMemberEdit {
  vip_name: string;
  action: "add" | "remove" | "replace_selected" | "replace_all";
  old_refs: MemberRef[];
  new_refs: MemberRef[];
}

export interface NodeChange {
  old_node_ref: string;
  new_ip: string;
  new_node_name?: string | null;
}

export interface VipException {
  vip_name: string;
  overrides: Partial<Record<ChangeType, Record<string, unknown>>>;
}

export type CsvImportType = "vip_changes" | "vlan_rules" | "pool_members" | "node_changes";

export interface CsvImportResult {
  exceptions: VipException[];
  node_changes: NodeChange[];
  pool_member_edits: PoolMemberEdit[];
  row_count: number;
}

export type OutputMode = "changes_only" | "full_recreate";

export interface MigrationPlan {
  session_id: string;
  selected_vips: string[];
  common_changes: CommonChange[];
  node_changes: NodeChange[];
  pool_member_edits: PoolMemberEdit[];
  exceptions: VipException[];
  create_network_objects: boolean;
  output_mode: OutputMode;
}

export type Severity = "pass" | "warn" | "blocked";

export interface ValidationCheck {
  id: string;
  label: string;
  severity: Severity;
  details: string;
  affected: string[];
}

export interface ValidationResult {
  checks: ValidationCheck[];
  overall: "READY" | "BLOCKED";
}

export interface RestCall {
  method: string;
  path: string;
  body: Record<string, unknown>;
}

export interface GenerateResult {
  tmsh: string;
  rest: RestCall[];
  as3: { declaration: Record<string, unknown>; "x-tmos-notes": Record<string, string>[] };
  validation: ValidationResult;
  output_mode: OutputMode;
}
