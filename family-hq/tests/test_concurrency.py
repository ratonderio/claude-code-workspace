"""Real concurrent writers on a real SQLite file."""

from __future__ import annotations

import threading

from family_hq.application.task_service import NewTask
from family_hq.errors import ConflictError


def test_two_people_claiming_at_once_produce_exactly_one_winner(world):
    task = world.tasks.create(world.adult, NewTask(title="Clean garage"))
    barrier = threading.Barrier(2)
    outcomes: dict[str, str] = {}

    def claim(name: str, actor) -> None:
        barrier.wait()
        try:
            world.tasks.claim(actor, task.id)
            outcomes[name] = "won"
        except ConflictError:
            outcomes[name] = "lost"

    threads = [
        threading.Thread(target=claim, args=("kid", world.kid)),
        threading.Thread(target=claim, args=("kid2", world.kid2)),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=20)
    assert sorted(outcomes.values()) == ["lost", "won"]
    final = world.tasks.get(world.adult, task.id)
    winner = world.kid if outcomes["kid"] == "won" else world.kid2
    assert final.owner_id == winner.id
    claims = [
        e for e in world.tasks.history(world.adult, task.id) if e.event_type.value == "TASK_CLAIMED"
    ]
    assert len(claims) == 1


def test_many_parallel_creations_all_succeed(world):
    errors: list[Exception] = []

    def create(i: int) -> None:
        try:
            world.tasks.create(world.admin, NewTask(title=f"parallel {i}"))
        except Exception as exc:  # pragma: no cover - failure path
            errors.append(exc)

    threads = [threading.Thread(target=create, args=(i,)) for i in range(12)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert errors == []
    assert len(world.tasks.list_tasks(world.admin)) == 12
    seqs = [e.seq for e in world.tasks.recent_activity(world.admin, limit=100)]
    assert len(set(seqs)) == 12
