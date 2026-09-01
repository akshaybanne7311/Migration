from dataclasses import dataclass
from typing import Dict

from app.generation.emit_order import MigrationContext
from app.models.change_set import ResolvedMigrationPlan
from app.models.domain import Node, Pool, Vip, Vlan


@dataclass
class ValidationInput:
    resolved: ResolvedMigrationPlan
    context: MigrationContext
    nodes_by_name: Dict[str, Node]
    pools_by_name: Dict[str, Pool]
    vips_by_name: Dict[str, Vip]
    vlans_by_name: Dict[str, Vlan]
