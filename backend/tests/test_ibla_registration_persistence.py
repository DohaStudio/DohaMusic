"""Physical v2 exact catalog, legacy byte preservation and uniqueness/CAS."""

import pytest
import rfc8785
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from backend.bootstrap_authority.ibla.codec import control_wire, parse_control, parse_event
from backend.bootstrap_authority.ibla.contracts import Head, IblaDenied
from backend.bootstrap_authority.lifecycle_verifier import digest
from backend.tests.ibla_support import BINDING, candidate, keeper, ledger, session, stores, uid
from backend.tests.test_ibla_registration_codec import codec_profiles, event  # noqa: F401


def insert(repo, e):
    repo._insert(
        (
            e.revision,
            e.event_id,
            e.operation_id,
            e.fingerprint,
            e.previous_digest,
            e.digest,
            e.kind,
            e.envelope,
        )
    )


def insert_control(repo, wire):
    p, _, e, d = parse_control(wire, BINDING, version=2)
    repo._insert(
        (p["sequence"], d, e.operation_id, e.fingerprint, p["previous_digest"], d, p["kind"], wire)
    )


def legacy_prefix(lp, h):
    wire = candidate()
    commission = parse_event(wire, BINDING)
    pending = control_wire(
        BINDING,
        sequence=1,
        previous=None,
        kind="COMMISSIONING_PENDING",
        confirmed=Head(),
        pending=wire,
        recorded_at="2026-10-01T00:00:00Z",
    )
    pd = parse_control(pending, BINDING)[3]
    confirmed = control_wire(
        BINDING,
        sequence=2,
        previous=pd,
        kind="CONFIRMED",
        confirmed=Head(1, commission.digest),
        pending=wire,
        recorded_at="2026-10-01T00:00:00Z",
    )
    with ledger(lp, version=2) as repo:
        repo.append(wire, expected=Head())
    with keeper(lp, h, version=2) as repo:
        insert_control(repo, pending)
        insert_control(repo, confirmed)
    return commission, pending, confirmed


def registration(lp, h, profiles):
    r, q, *_ = profiles
    with keeper(lp, h, version=2) as repo:
        hv = repo.read()
        r["expected_l_head"] = {"revision": 1, "digest": hv.confirmed.digest}
        r["expected_h_confirmed"] = dict(r["expected_l_head"])
        r["expected_h_head"] = {"revision": hv.head.revision, "digest": hv.head.digest}
        p = event(r, q)
        wire = rfc8785.dumps(p)
        # Explicit storage fixture insertion; generic registration prepare is unauthorized.
        prepared = control_wire(
            BINDING,
            sequence=hv.head.revision + 1,
            previous=hv.head.digest,
            kind="PREPARED",
            confirmed=hv.confirmed,
            pending=wire,
            recorded_at=r["recorded_at"],
            version=2,
        )
        insert_control(repo, prepared)
    e = parse_event(wire, BINDING, version=2)
    with ledger(lp, version=2) as repo:
        insert(repo, e)  # Explicit disposable storage fixture; not Writer authority.
    with keeper(lp, h, version=2) as repo:
        repo.confirm(e.operation_id, e.fingerprint)
    return e


def test_v2_extends_exact_v1_prefix_bytes_and_hashes(tmp_path, profiles):
    lp, h = stores(tmp_path, version=2)
    comm, pending, confirmed = legacy_prefix(lp, h)
    reg = registration(lp, h, profiles)
    with ledger(lp, readonly=True, version=2) as repo:
        lv = repo.read()
        assert lv.events == (comm, reg)
    with keeper(lp, h, version=2) as repo:
        hv = repo.read_correlated()
        assert hv.confirmed == Head(2, reg.digest)
        rows = repo._rows()
        assert rows[0].envelope == pending and rows[1].envelope == confirmed
        assert parse_control(rows[2].envelope, BINDING, version=2)[0]["schema"].endswith("/v2")
    with pytest.raises(IblaDenied), ledger(lp, readonly=True) as repo:
        repo.read()


def test_v1_suffix_after_v2_control_is_rejected(tmp_path, profiles):
    lp, h = stores(tmp_path, version=2)
    legacy_prefix(lp, h)
    registration(lp, h, profiles)
    with keeper(lp, h, version=2) as repo:
        hv = repo.read()
        p = candidate(hv.confirmed, number=9000)
        wire = control_wire(
            BINDING,
            sequence=hv.head.revision + 1,
            previous=hv.head.digest,
            kind="PREPARED",
            confirmed=hv.confirmed,
            pending=p,
            recorded_at="2026-10-01T00:00:00Z",
        )
        insert_control(repo, wire)
    with pytest.raises(IblaDenied), keeper(lp, h, version=2) as repo:
        repo.read()


def test_single_registration_constraint_and_query_indexes(tmp_path, profiles):
    lp, h = stores(tmp_path, version=2)
    legacy_prefix(lp, h)
    reg = registration(lp, h, profiles)
    with session(lp) as s, pytest.raises(IntegrityError):
        s.execute(
            text(
                "INSERT INTO ibla_events VALUES(3,:record,:operation,:fp,:previous,:digest,"
                "'REGISTRATION_COMMITTED',:wire)"
            ),
            dict(
                record=uid(9100),
                operation=uid(9101),
                fp=digest(b"second"),
                previous=reg.digest,
                digest=digest(b"second-event"),
                wire=reg.envelope,
            ),
        )
    with session(lp, readonly=True) as s:
        for sql in (
            "SELECT * FROM ibla_events ORDER BY revision",
            "SELECT * FROM ibla_events WHERE operation_id='fixture'",
            "SELECT * FROM ibla_events WHERE record_id='fixture'",
            "SELECT * FROM ibla_head WHERE singleton=1",
            "SELECT * FROM ibla_events WHERE kind='REGISTRATION_COMMITTED'",
        ):
            plan = s.execute(text("EXPLAIN QUERY PLAN " + sql)).all()
            assert not any("TEMP B-TREE" in row[3] for row in plan)
        plan = s.execute(
            text("EXPLAIN QUERY PLAN SELECT * FROM ibla_events WHERE operation_id='fixture'")
        ).all()
        assert "SEARCH" in plan[0][3]

    with session(h, readonly=True) as s:
        for sql in (
            "SELECT * FROM ibla_events ORDER BY revision",
            "SELECT * FROM ibla_events WHERE operation_id='fixture' ORDER BY revision",
            "SELECT * FROM ibla_head WHERE singleton=1",
        ):
            plan = s.execute(text("EXPLAIN QUERY PLAN " + sql)).all()
            assert not any("TEMP B-TREE" in row[3] for row in plan)
        plan = s.execute(
            text(
                "EXPLAIN QUERY PLAN SELECT * FROM ibla_events "
                "WHERE operation_id='fixture' ORDER BY revision"
            )
        ).all()
        assert "SEARCH" in plan[0][3]
