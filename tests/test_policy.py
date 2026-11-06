import pytest

from stream_code_capture.domain import Rect, TextLine
from stream_code_capture.policy import DecisionPolicy, PolicyConfig, candidates


def lines(code="AB23CD45EF", confidence=0.99):
    return [
        TextLine(code, confidence, Rect(20, 10, 160, 25)),
        TextLine("100% off", 0.99, Rect(20, 50, 150, 65)),
    ]


def armed(config=None):
    policy = DecisionPolicy(config)
    policy.learn_baseline([])
    policy.arm()
    return policy


@pytest.mark.parametrize(
    "text",
    [
        "JORDY",
        "100",
        "19642.25",
        "CHATTER",
        "abcdefgh12",
        "AB23-CD45EF",
        "AB23 CD45EF",
        "АB23CD45EF",
        "AB23CD45EF!",
        "TOOLONG1234567890123",
    ],
)
def test_non_codes_are_rejected(text):
    assert candidates(lines(text), PolicyConfig()) == []


def test_context_and_confidence_are_required():
    assert candidates(lines()[:1], PolicyConfig()) == []
    assert candidates(lines(confidence=0.8), PolicyConfig()) == []
    assert candidates(lines(confidence=float("nan")), PolicyConfig()) == []
    far = lines()[:1] + [TextLine("100% off", 0.99, Rect(500, 400, 600, 420))]
    assert candidates(far, PolicyConfig()) == []


def test_exact_code_preserves_ambiguous_characters():
    assert candidates(lines("O0I1B8S5Z2"), PolicyConfig()) == ["O0I1B8S5Z2"]


def test_disarmed_and_requires_baseline():
    policy = DecisionPolicy()
    with pytest.raises(RuntimeError, match="baseline"):
        policy.arm()
    assert policy.observe(lines(), 1, 1, 1) == ("disarmed", None)


def test_confirmation_commit_and_duplicate_across_rearm():
    policy = armed()
    assert policy.observe(lines(), 1, 10, 10) == ("confirming", None)
    assert policy.observe(lines(), 2, 20, 20) == ("ready", "AB23CD45EF")
    policy.committed("AB23CD45EF")
    assert not policy.armed
    policy.arm()
    assert policy.observe(lines(), 3, 30, 30) == ("no_candidate", None)


def test_baseline_suppresses_existing_code_even_with_new_context():
    policy = DecisionPolicy()
    policy.learn_baseline(lines()[:1])
    policy.arm()
    assert policy.observe(lines(), 1, 10, 10) == ("no_candidate", None)
    with pytest.raises(RuntimeError, match="Disarm"):
        policy.learn_baseline([])


def test_ambiguity_does_not_pick_first_code():
    policy = armed()
    status, code = policy.observe(lines() + lines("ZX98YU76TR"), 1, 10, 10)
    assert (status, code) == ("ambiguous", None)


@pytest.mark.parametrize(
    "sequence,captured,now,status",
    [
        (1, 20, 20, "out_of_order"),
        (2, 10, 20, "out_of_order"),
        (2, 20, 2_000_000_000, "stale"),
        (2, 20, 19, "stale"),
    ],
)
def test_invalid_frames_break_confirmation(sequence, captured, now, status):
    policy = armed()
    policy.observe(lines(), 1, 10, 10)
    assert policy.observe(lines(), sequence, captured, now) == (status, None)
    assert policy.observe(lines(), 3, 3_000_000_000, 3_000_000_000)[0] == "confirming"


def test_gap_and_changed_code_reset_exact_agreement():
    policy = armed()
    policy.observe(lines(), 1, 10, 10)
    assert policy.observe(lines("AB23CD45E8"), 2, 20, 20)[0] == "confirming"
    assert policy.observe([], 3, 30, 30)[0] == "no_candidate"
    assert policy.observe(lines("AB23CD45E8"), 4, 40, 40)[0] == "confirming"
    assert policy.observe(lines("AB23CD45E8"), 5, 2_000_000_000, 2_000_000_000)[0] == "confirming"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"confirmations": 0},
        {"min_confidence": 1.1},
        {"max_frame_age_ms": -1},
        {"confirmation_window_ms": float("nan")},
    ],
)
def test_invalid_configuration(kwargs):
    with pytest.raises(ValueError):
        PolicyConfig(**kwargs)
