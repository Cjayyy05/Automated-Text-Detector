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
        "AB23-CD45EF",
        "AB23 CD45EF",
        "АB23CD45EF",
        "AB23CD45EF!",
        "TOOLONG1234567890123456789",
    ],
)
def test_non_codes_are_rejected(text):
    assert candidates(lines(text), PolicyConfig()) == []


def test_standalone_code_still_requires_confidence():
    assert candidates(lines()[:1], PolicyConfig()) == ["AB23CD45EF"]
    assert candidates(lines(confidence=0.8), PolicyConfig()) == []
    assert candidates(lines(confidence=float("nan")), PolicyConfig()) == []
    far = lines("trader2345")[:1] + [TextLine("100% off", 0.99, Rect(500, 400, 600, 420))]
    assert candidates(far, PolicyConfig()) == []


@pytest.mark.parametrize("glyph", ["O", "0"])
def test_policy_accepts_o0_verbatim(glyph):
    observed = lines(f"AB23CD45E{glyph}")
    assert candidates(observed, PolicyConfig()) == [f"AB23CD45E{glyph}"]
    assert observed[0].text == f"AB23CD45E{glyph}"


def test_accepted_code_preserves_other_lookalikes():
    assert candidates(lines("AI1B8S5Z2X"), PolicyConfig()) == ["AI1B8S5Z2X"]


def test_disarmed_and_requires_baseline():
    policy = DecisionPolicy()
    with pytest.raises(RuntimeError, match="baseline"):
        policy.arm()
    assert policy.observe(lines(), 1, 1, 1) == ("disarmed", None)


def test_confirmation_commit_and_duplicate_across_rearm():
    policy = armed()
    assert policy.observe(lines(), 1, 10, 10) == ("ready", "AB23CD45EF")
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
        (2, 20, 3_100_000_000, "stale"),
        (2, 20, 19, "stale"),
    ],
)
def test_invalid_frames_cannot_confirm(sequence, captured, now, status):
    policy = armed()
    policy.observe(lines(), 1, 10, 10)
    assert policy.observe(lines(), sequence, captured, now) == (status, None)
    assert policy.observe(lines(), 3, 4_000_000_000, 4_000_000_000)[0] == "ready"


@pytest.mark.parametrize("profile", ["discount", "game"])
@pytest.mark.parametrize("text", ["AbO0x7cD", "ab04xyz9", "AB23CD45EF", "aB23cD45eF"])
def test_standalone_codes_keep_exact_case_and_characters(profile, text):
    config = PolicyConfig(profile=profile)
    assert candidates(lines(text)[:1], config) == [text]


@pytest.mark.parametrize("text", ["trader2345", "@AB23CD45EF", "This is not a code", "USD 19.99"])
def test_standalone_unrelated_text_abstains(text):
    assert candidates(lines(text)[:1], PolicyConfig()) == []


def test_explicit_label_supports_short_and_long_codes():
    config = PolicyConfig()
    short = TextLine("Use code SaVe20", 0.99, Rect(0, 0, 160, 20))
    long = TextLine("CODE: aBC2defG34hijk5678lm90NP", 0.99, Rect(0, 28, 350, 51))
    assert candidates([short], config) == ["SaVe20"]
    assert candidates([long], config) == ["aBC2defG34hijk5678lm90NP"]
    assert candidates([TextLine("SaVe20", 0.99, short.box)], config) == []


def test_baseline_and_duplicate_comparisons_are_case_sensitive():
    policy = DecisionPolicy()
    policy.learn_baseline(lines("aB23CD45EF"))
    policy.arm()
    assert policy.observe(lines("aB23CD45EF"), 1, 10, 10) == ("no_candidate", None)
    assert policy.observe(lines("AB23CD45EF"), 2, 20, 20) == ("ready", "AB23CD45EF")
    policy.committed("AB23CD45EF")
    policy.arm()
    assert policy.observe(lines("AB23CD45EF"), 3, 30, 30) == ("no_candidate", None)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"min_confidence": 1.1},
        {"max_frame_age_ms": -1},
        {"max_frame_age_ms": float("nan")},
    ],
)
def test_invalid_configuration(kwargs):
    with pytest.raises(ValueError):
        PolicyConfig(**kwargs)
