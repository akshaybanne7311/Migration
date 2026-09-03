"""CSV-driven bulk migration rule import.

Lets an operator prepare hundreds of VIP/pool/VLAN/node changes offline in
a spreadsheet and import them in one shot, instead of clicking "add
exception" one VIP at a time in the wizard. Every format here maps
directly onto an existing MigrationPlan field (VipException, NodeChange,
PoolMemberEdit) -- there is no new domain concept, so the existing,
already-tested change engine and generators handle the imported rows with
zero new code paths downstream of this module.
"""
import csv
import io
from typing import Dict, List

from app.models.change_set import ChangeType, MemberRef, NodeChange, PoolMemberEdit, VipException
from app.models.domain import Pool, Vip


class CsvImportError(Exception):
    pass


def _read_rows(content: str) -> List[Dict[str, str]]:
    reader = csv.DictReader(io.StringIO(content.strip()))
    if not reader.fieldnames:
        raise CsvImportError("empty CSV")
    rows = [row for row in reader if any((v or "").strip() for v in row.values())]
    if not rows:
        raise CsvImportError("CSV has a header but no data rows")
    return rows


def _cell(row: Dict[str, str], key: str) -> str:
    return (row.get(key) or "").strip()


def parse_vip_changes_csv(content: str, vips_by_name: Dict[str, Vip]) -> List[VipException]:
    """Columns: source_vip, target_vip_name, target_vip_ip, target_vip_port, target_pool_name
    Blank target_* columns leave that field unchanged for that VIP."""
    exceptions: List[VipException] = []
    for i, row in enumerate(_read_rows(content), start=2):
        source_vip = _cell(row, "source_vip")
        if not source_vip:
            raise CsvImportError("row %d: source_vip is required" % i)
        vip = vips_by_name.get(source_vip)
        if vip is None:
            raise CsvImportError("row %d: source_vip %r does not exist in this session" % (i, source_vip))

        overrides: Dict[ChangeType, Dict] = {}
        if target_name := _cell(row, "target_vip_name"):
            overrides[ChangeType.VIP_NAME] = {"find": source_vip, "replace": target_name}

        target_ip = _cell(row, "target_vip_ip")
        target_port_raw = _cell(row, "target_vip_port")
        if target_ip or target_port_raw:
            payload: Dict = {}
            if target_ip:
                payload["new_address"] = target_ip
            if target_port_raw:
                try:
                    payload["new_port"] = int(target_port_raw)
                except ValueError:
                    raise CsvImportError("row %d: target_vip_port %r is not a number" % (i, target_port_raw))
            overrides[ChangeType.VIP_IP_PORT] = payload

        if target_pool := _cell(row, "target_pool_name"):
            if not vip.pool_name:
                raise CsvImportError("row %d: %s has no current pool to rename" % (i, source_vip))
            overrides[ChangeType.POOL_NAME] = {"find": vip.pool_name, "replace": target_pool}

        if not overrides:
            raise CsvImportError("row %d: no target_* column had a value" % i)
        exceptions.append(VipException(vip_name=source_vip, overrides=overrides))
    return exceptions


def parse_vlan_rules_csv(content: str, selected_vips: List[str]) -> List[VipException]:
    """Columns: vip_name (blank = apply to every currently selected VIP),
    action (add|remove|replace), old_vlan, new_vlan."""
    if not selected_vips:
        raise CsvImportError("no VIPs are selected to apply blank-vip_name rows to")

    exceptions: List[VipException] = []
    for i, row in enumerate(_read_rows(content), start=2):
        action = _cell(row, "action").lower()
        old_vlan = _cell(row, "old_vlan")
        new_vlan = _cell(row, "new_vlan")
        if action not in ("add", "remove", "replace"):
            raise CsvImportError("row %d: action must be add, remove, or replace (got %r)" % (i, action))
        if action == "replace" and not (old_vlan and new_vlan):
            raise CsvImportError("row %d: action=replace requires both old_vlan and new_vlan" % i)
        if action == "remove" and not old_vlan:
            raise CsvImportError("row %d: action=remove requires old_vlan" % i)
        if action == "add" and not new_vlan:
            raise CsvImportError("row %d: action=add requires new_vlan" % i)

        payload = {"action": action}
        if old_vlan:
            payload["old_vlan"] = old_vlan
        if new_vlan:
            payload["new_vlan"] = new_vlan

        vip_name = _cell(row, "vip_name")
        targets = [vip_name] if vip_name else list(selected_vips)
        for target in targets:
            exceptions.append(VipException(vip_name=target, overrides={ChangeType.VLANS: payload}))
    return exceptions


def parse_pool_member_rules_csv(
    content: str,
    selected_vips: List[str],
    vips_by_name: Dict[str, Vip],
    pools_by_name: Dict[str, Pool],
) -> List[PoolMemberEdit]:
    """Columns: source_pool, action (add|remove|remove_all|replace_all),
    source_member_node, source_member_port, target_node, target_address,
    target_port. One rule fans out to one PoolMemberEdit per currently
    selected VIP that actually uses source_pool -- identical edits for VIPs
    sharing a pool are fine (see change_engine's conflict check), so this
    never needs to know or care how many VIPs share the pool."""
    edits: List[PoolMemberEdit] = []
    for i, row in enumerate(_read_rows(content), start=2):
        source_pool = _cell(row, "source_pool")
        if not source_pool:
            raise CsvImportError("row %d: source_pool is required" % i)
        if source_pool not in pools_by_name:
            raise CsvImportError("row %d: source_pool %r does not exist in this session" % (i, source_pool))

        action = _cell(row, "action")
        if action not in ("add", "remove", "remove_all", "replace_all"):
            raise CsvImportError(
                "row %d: action must be add, remove, remove_all, or replace_all (got %r)" % (i, action)
            )

        old_refs: List[MemberRef] = []
        new_refs: List[MemberRef] = []
        if action == "remove":
            node = _cell(row, "source_member_node")
            port_raw = _cell(row, "source_member_port")
            if not (node and port_raw):
                raise CsvImportError("row %d: action=remove requires source_member_node and source_member_port" % i)
            old_refs.append(MemberRef(node_name=node, port=int(port_raw)))
        if action in ("add", "replace_all"):
            target_node = _cell(row, "target_node")
            target_address = _cell(row, "target_address")
            target_port_raw = _cell(row, "target_port")
            if not (target_address and target_port_raw):
                raise CsvImportError(
                    "row %d: action=%s requires target_address and target_port" % (i, action)
                )
            new_refs.append(
                MemberRef(
                    node_name=target_node or None,
                    address=target_address,
                    port=int(target_port_raw),
                )
            )

        matching_vips = [
            v.name for v in vips_by_name.values() if v.name in selected_vips and v.pool_name == source_pool
        ]
        if not matching_vips:
            raise CsvImportError(
                "row %d: source_pool %r is not used by any currently selected VIP" % (i, source_pool)
            )
        # PoolMemberEdit has no "remove_all" action -- an empty-member
        # replace_all is exactly the same operation and the engine already
        # supports it, so map it there rather than widening the domain model.
        edit_action = "replace_all" if action == "remove_all" else action
        for vip_name in matching_vips:
            edits.append(
                PoolMemberEdit(
                    vip_name=vip_name, action=edit_action, old_refs=old_refs, new_refs=list(new_refs)
                )
            )
    return edits


def parse_node_changes_csv(content: str) -> List[NodeChange]:
    """Columns: source_node, new_ip, new_node_name (optional)."""
    changes: List[NodeChange] = []
    for i, row in enumerate(_read_rows(content), start=2):
        source_node = _cell(row, "source_node")
        new_ip = _cell(row, "new_ip")
        if not (source_node and new_ip):
            raise CsvImportError("row %d: source_node and new_ip are both required" % i)
        changes.append(
            NodeChange(
                old_node_ref=source_node,
                new_ip=new_ip,
                new_node_name=_cell(row, "new_node_name") or None,
            )
        )
    return changes
