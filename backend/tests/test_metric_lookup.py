import hashlib

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.cqrs import complete_run, find_runs_by_metric, record_metric, start_run
from app.database import Base


def sha(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # JSONB not available on SQLite — remap via create_all with JSON
    from sqlalchemy import JSON  # noqa: F401
    from sqlalchemy.dialects.postgresql import JSONB

    # For SQLite tests, compile JSONB as JSON
    from sqlalchemy.ext.compiler import compiles

    @compiles(JSONB, "sqlite")
    def _compile_jsonb_sqlite(_type, compiler, **kw):
        return "JSON"

    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


def _run_with_metrics(db, *, project, name, metrics):
    run = start_run(
        db,
        actor="researcher",
        project=project,
        name=name,
        dataset_content_sha256=sha(project + name),
        code_commit_sha="abc1234",
        description=None,
    )
    for metric_name, value, step in metrics:
        run = record_metric(
            db,
            run_id=run.id,
            actor="researcher",
            name=metric_name,
            value=value,
            step=step,
            expected_version=run.version,
        )
    return run


def test_lookup_returns_one_row_per_run_with_latest_value(db):
    run_a = _run_with_metrics(
        db,
        project="p1",
        name="run-a",
        metrics=[("loss", 1.8, 1), ("loss", 0.9, 2)],
    )
    run_b = _run_with_metrics(
        db,
        project="p2",
        name="run-b",
        metrics=[("loss", 0.4, 5)],
    )
    _run_with_metrics(db, project="p3", name="run-c", metrics=[("acc", 0.7, 1)])

    hits = find_runs_by_metric(db, "loss")

    assert len(hits) == 2
    by_run = {h["run_id"]: h for h in hits}

    hit_a = by_run[run_a.id]
    assert hit_a["project"] == "p1"
    assert hit_a["name"] == "run-a"
    assert hit_a["status"] == "running"
    # 最近值取该 Run 内最后一条同名指标
    assert hit_a["value"] == 0.9
    assert hit_a["step"] == 2
    assert hit_a["recorded_at"]

    hit_b = by_run[run_b.id]
    assert hit_b["value"] == 0.4
    assert hit_b["step"] == 5


def test_lookup_matches_completed_runs_and_exact_name_only(db):
    run = _run_with_metrics(db, project="p1", name="run-tm", metrics=[("tm_score", 0.81, 2)])
    complete_run(db, run_id=run.id, actor="researcher", result_summary="done", expected_version=run.version)
    _run_with_metrics(db, project="p1", name="run-tm2", metrics=[("tm_score_v2", 0.5, 1)])

    hits = find_runs_by_metric(db, "tm_score")
    assert len(hits) == 1
    assert hits[0]["run_id"] == run.id
    assert hits[0]["status"] == "completed"

    # 精确匹配：子串/前缀不应命中
    assert find_runs_by_metric(db, "tm") == []
    assert find_runs_by_metric(db, "score") == []


def test_lookup_unknown_metric_returns_empty(db):
    _run_with_metrics(db, project="p1", name="run-x", metrics=[("loss", 1.0, 1)])
    assert find_runs_by_metric(db, "no_such_metric") == []
