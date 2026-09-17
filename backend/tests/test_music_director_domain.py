import pytest

from backend.contracts.music_director import MusicIntent


def test_music_intent_defaults_are_canonical_and_deterministic() -> None:
    first = MusicIntent(instruction="  make the chorus brighter  ")
    second = MusicIntent(instruction="make the chorus brighter")
    assert first.instruction == "make the chorus brighter"
    assert first.candidate_count == 2
    assert first.request_fingerprint() == second.request_fingerprint()
    assert len(first.request_fingerprint()) == 64


@pytest.mark.parametrize("candidate_count", [1, 4])
def test_music_intent_accepts_candidate_count_boundaries(candidate_count: int) -> None:
    assert (
        MusicIntent(instruction="variation", candidate_count=candidate_count).candidate_count
        == candidate_count
    )


@pytest.mark.parametrize("candidate_count", [0, 5])
def test_music_intent_rejects_candidate_count_outside_authority(candidate_count: int) -> None:
    with pytest.raises(ValueError, match="candidate_count"):
        MusicIntent(instruction="variation", candidate_count=candidate_count)


def test_music_intent_rejects_blank_or_oversized_instruction() -> None:
    with pytest.raises(ValueError, match="instruction"):
        MusicIntent(instruction=" ")
    with pytest.raises(ValueError, match="instruction"):
        MusicIntent(instruction="x" * 2001)
