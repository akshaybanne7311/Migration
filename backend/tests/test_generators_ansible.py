import pytest

from app.generation.ansible_generator import generate_ansible_playbook
from app.generation.emit_order import build_migration_context
from app.generation.rest_generator import generate_rest
from app.migration.change_engine import resolve
from app.models.change_set import MigrationPlan, NodeChange


def test_empty_call_list_produces_a_valid_no_op_playbook():
    playbook = generate_ansible_playbook([])
    assert playbook.startswith("---\n")
    assert "hosts: f5_target" in playbook
    assert "No changes to apply" in playbook


def test_playbook_covers_every_rest_call_as_one_task(session_maps):
    plan = MigrationPlan(
        session_id=session_maps["session_id"],
        selected_vips=["/Common/VS-WEB-HTTP-80"],
        node_changes=[NodeChange(old_node_ref="/Common/WEB-Node-1", new_ip="10.20.30.200")],
    )
    resolved = resolve(
        plan,
        session_maps["nodes_by_name"],
        session_maps["pools_by_name"],
        session_maps["vips_by_name"],
        session_maps["graph"],
    )
    context = build_migration_context(
        resolved, session_maps["nodes_by_name"], session_maps["pools_by_name"], session_maps["vips_by_name"]
    )
    calls = generate_rest(context, session_maps["vips_by_name"])
    assert calls  # sanity: this plan actually produces REST calls

    playbook = generate_ansible_playbook(calls)

    assert playbook.count("ansible.builtin.uri:") == len(calls)
    for call in calls:
        assert call.path in playbook
        assert ("method: %s" % call.method) in playbook


def test_generated_playbook_is_valid_yaml_with_correct_task_bodies(session_maps):
    yaml = pytest.importorskip("yaml")

    plan = MigrationPlan(
        session_id=session_maps["session_id"],
        selected_vips=["/Common/VS-WEB-HTTP-80"],
        node_changes=[NodeChange(old_node_ref="/Common/WEB-Node-1", new_ip="10.20.30.200")],
    )
    resolved = resolve(
        plan,
        session_maps["nodes_by_name"],
        session_maps["pools_by_name"],
        session_maps["vips_by_name"],
        session_maps["graph"],
    )
    context = build_migration_context(
        resolved, session_maps["nodes_by_name"], session_maps["pools_by_name"], session_maps["vips_by_name"]
    )
    calls = generate_rest(context, session_maps["vips_by_name"])
    playbook = generate_ansible_playbook(calls)

    parsed = yaml.safe_load(playbook)
    assert isinstance(parsed, list)
    tasks = parsed[0]["tasks"]
    assert len(tasks) == len(calls)
    for task, call in zip(tasks, calls):
        uri = task["ansible.builtin.uri"]
        assert uri["method"] == call.method
        assert uri["body"] == call.body
        assert uri["url"].endswith(call.path)
