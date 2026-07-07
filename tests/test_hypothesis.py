from server.hypothesis import HypothesisTracker, infer_transform
from server.transforms import Identity, Translate


def test_infer_transform_detects_identity() -> None:
    transform = infer_transform([[0, 1], [0, 0]], [[0, 1], [0, 0]])

    assert isinstance(transform, Identity)


def test_infer_transform_detects_largest_object_translation() -> None:
    before = [[0, 0, 0], [0, 7, 0], [0, 0, 0]]
    after = [[0, 0, 0], [0, 0, 7], [0, 0, 0]]

    transform = infer_transform(before, after)

    assert isinstance(transform, Translate)
    assert transform.dx == 1
    assert transform.dy == 0


def test_tracker_emits_audit_v3_fields_and_confidence() -> None:
    tracker = HypothesisTracker()
    before = [[0, 0, 0], [0, 7, 0], [0, 0, 0]]
    after = [[0, 0, 0], [0, 0, 7], [0, 0, 0]]

    audit = tracker.observe(action_id=1, before_frame=before, after_frame=after, step_index=1)

    assert audit["schema"] == "arc3-runner.audit.v3"
    assert audit["hypotheses"][0]["action_id"] == 1
    assert audit["hypotheses"][0]["transform"] == {"op": "translate", "dx": 1, "dy": 0}
    assert audit["imagination"]["mode"] == "exploit"
    assert audit["surprise"]["pixel_error"] >= 0
    assert audit["credibility"]["claimed"] > 0
