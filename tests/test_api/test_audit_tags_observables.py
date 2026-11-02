"""Audit coverage for tags and observable TLP/tag policy changes."""

from __future__ import annotations

import json
import uuid

from sqlalchemy import select

from cti.models.audit import AuditEvent
from tests.policy_helpers import add_observable


async def _events(db, action: str) -> list[AuditEvent]:
    db.expunge_all()
    rows = await db.scalars(
        select(AuditEvent)
        .where(AuditEvent.action == action)
        .order_by(AuditEvent.occurred_at, AuditEvent.id)
    )
    return list(rows.all())


async def test_tag_create_delete_audits_success_and_failure(client, db_session) -> None:
    created = await client.post("/api/v1/tags", json={"name": "Threat Intel"})
    assert created.status_code == 201
    tag_id = created.json()["id"]
    assert (await client.post("/api/v1/tags", json={"name": "bad tag?"})).status_code == 422
    assert (await client.delete(f"/api/v1/tags/{tag_id}")).status_code == 204
    assert (await client.delete(f"/api/v1/tags/{tag_id}")).status_code == 404

    create_ok, create_failed = await _events(db_session, "tag.create")
    delete_ok, delete_failed = await _events(db_session, "tag.delete")
    assert (create_ok.resource_id, create_ok.resource_label, create_ok.outcome) == (
        tag_id,
        "threat-intel",
        "succeeded",
    )
    assert create_ok.summary == {"created": True}
    assert create_failed.summary == {"reason": "invalid_name", "status": 422}
    assert (delete_ok.resource_id, delete_ok.resource_label) == (tag_id, "threat-intel")
    assert delete_failed.summary == {"reason": "not_found", "status": 404}


async def test_observable_tlp_set_clear_audits_markings_and_reason_metadata(
    client, db_session
) -> None:
    obs = await add_observable(db_session, "192.0.2.44")
    obs_id = obs.id
    reason = "named recipients only"
    set_response = await client.put(
        f"/api/v1/observables/{obs_id}/tlp-override",
        json={"tlp": "amber", "reason": reason},
    )
    assert set_response.status_code == 200
    missing_set = uuid.uuid4()
    assert (
        await client.put(
            f"/api/v1/observables/{missing_set}/tlp-override",
            json={"tlp": "green", "reason": "missing"},
        )
    ).status_code == 404
    clear_response = await client.delete(f"/api/v1/observables/{obs_id}/tlp-override")
    assert clear_response.status_code == 200
    missing_clear = uuid.uuid4()
    assert (
        await client.delete(f"/api/v1/observables/{missing_clear}/tlp-override")
    ).status_code == 404

    set_ok, set_failed = await _events(db_session, "observable.tlp_override_set")
    clear_ok, clear_failed = await _events(db_session, "observable.tlp_override_clear")
    assert (set_ok.resource_id, set_ok.resource_label, set_ok.outcome) == (
        str(obs_id),
        "192.0.2.44",
        "succeeded",
    )
    assert set_ok.summary == {
        "before": None,
        "after": "amber",
        "reason_present": True,
        "reason_length": len(reason),
    }
    assert reason not in json.dumps(set_ok.summary)
    assert (set_failed.resource_id, set_failed.outcome, set_failed.summary) == (
        str(missing_set),
        "failed",
        {"reason": "not_found", "status": 404},
    )
    assert (clear_ok.resource_id, clear_ok.resource_label, clear_ok.summary) == (
        str(obs_id),
        "192.0.2.44",
        {"before": "amber", "after": None},
    )
    assert (clear_failed.resource_id, clear_failed.outcome) == (str(missing_clear), "failed")


async def test_observable_tags_update_audits_added_removed_and_failure(client, db_session) -> None:
    obs = await add_observable(db_session, "192.0.2.45")
    obs_id = obs.id
    first = await client.put(
        f"/api/v1/observables/{obs_id}/tags", json={"tags": ["alpha", "beta"]}
    )
    assert first.status_code == 200
    second = await client.put(
        f"/api/v1/observables/{obs_id}/tags", json={"tags": ["beta", "gamma"]}
    )
    assert second.status_code == 200
    failed = await client.put(
        f"/api/v1/observables/{obs_id}/tags", json={"tags": ["invalid tag?"]}
    )
    assert failed.status_code == 422

    first_event, second_event, failed_event = await _events(
        db_session, "observable.tags_update"
    )
    assert (first_event.resource_id, first_event.resource_label, first_event.outcome) == (
        str(obs_id),
        "192.0.2.45",
        "succeeded",
    )
    assert first_event.summary == {"added": ["alpha", "beta"], "removed": []}
    assert second_event.summary == {"added": ["gamma"], "removed": ["alpha"]}
    assert failed_event.outcome == "failed"
    assert failed_event.summary == {"reason": "invalid_tags", "status": 422}
