import pytest
from ytclfr.probing.structural_detector import probe_structural, _probe_structural_inner

@pytest.fixture
def base_kwargs():
    return {
        "sampled_frames": [1, 2, 3], # Just needs to be non-empty for probe_structural_inner
        "visual_cut_count": 0,
        "visual_motion_density": 0.0,
        "has_speech": False,
        "has_music": False,
        "metadata_prior_confidence": 0.5
    }

@pytest.fixture(autouse=True)
def mock_cv2_hist(mocker):
    mocker.patch("cv2.calcHist", return_value=None)
    mocker.patch("cv2.normalize", return_value=None)
    mocker.patch("cv2.compareHist", return_value=0.0)

def test_extreme_text_density_triggers_ocr(mocker, base_kwargs):
    # Mock inner cv2 dependencies instead of creating real frames
    mocker.patch("cv2.MSER_create")
    mocker.patch("cv2.cvtColor")
    mocker.patch("cv2.boundingRect", return_value=(0, 0, 20, 20))
    
    # We want overlay_text_density > 15.0
    # The code estimates blocks as text_like_boxes // 5, and total is sum(estimated_blocks) / len(frames)
    # So if we have 3 frames, we need total_text_regions > 45, meaning each frame needs ~15 estimated blocks = ~75 text_like_boxes.
    # We can just mock the MSER return to yield 80 regions per frame.
    mock_mser = mocker.Mock()
    mock_mser.detectRegions.return_value = ([1] * 80, None)
    mocker.patch("cv2.MSER_create", return_value=mock_mser)
    
    # Run inner directly to avoid OpenCV crashes with fake frames
    result = _probe_structural_inner(**base_kwargs)
    
    # 80 regions -> 16 estimated blocks per frame -> density = 16.0 > 15.0
    assert result.structural_score >= 0.6
    assert result.ocr_required is True # 0.6 >= 0.55, so OCR is now triggered by extreme density alone

def test_extreme_text_with_metadata_crosses_threshold(mocker, base_kwargs):
    mock_mser = mocker.Mock()
    mock_mser.detectRegions.return_value = ([1] * 80, None)
    mocker.patch("cv2.MSER_create", return_value=mock_mser)
    mocker.patch("cv2.cvtColor")
    mocker.patch("cv2.boundingRect", return_value=(0, 0, 20, 20))
    
    kwargs = base_kwargs.copy()
    kwargs["metadata_prior_confidence"] = 0.7
    
    result = _probe_structural_inner(**kwargs)
    
    # Score should be 0.5 (extreme text) + 0.15 (metadata corroboration) = 0.65
    assert result.structural_score >= 0.55
    assert result.ocr_required is True

def test_moderate_text_alone_below_threshold(mocker, base_kwargs):
    mock_mser = mocker.Mock()
    # Moderate text density > 2.0 but < 15.0. Say 5.0.
    # 5 estimated blocks -> 25 regions
    mock_mser.detectRegions.return_value = ([1] * 25, None)
    mocker.patch("cv2.MSER_create", return_value=mock_mser)
    mocker.patch("cv2.cvtColor")
    mocker.patch("cv2.boundingRect", return_value=(0, 0, 20, 20))
    
    result = _probe_structural_inner(**base_kwargs)
    
    assert 2.0 < result.overlay_text_density < 15.0
    assert result.structural_score == 0.3
    assert result.ocr_required is False

def test_empty_frames_safe_default(base_kwargs):
    kwargs = base_kwargs.copy()
    kwargs["sampled_frames"] = []
    
    result = _probe_structural_inner(**kwargs)
    
    assert result.structural_score == 0.0
    assert result.ocr_required is False

def test_motion_density_used_not_cut_count(mocker, base_kwargs):
    mock_mser = mocker.Mock()
    mock_mser.detectRegions.return_value = ([], None)
    mocker.patch("cv2.MSER_create", return_value=mock_mser)
    mocker.patch("cv2.cvtColor")
    
    kwargs = base_kwargs.copy()
    kwargs["visual_cut_count"] = 0
    kwargs["visual_motion_density"] = 15.0 # > 10.0
    
    result = _probe_structural_inner(**kwargs)
    
    assert result.structural_score == 0.2

def test_podcast_no_text_zero_score(mocker, base_kwargs):
    mock_mser = mocker.Mock()
    mock_mser.detectRegions.return_value = ([], None)
    mocker.patch("cv2.MSER_create", return_value=mock_mser)
    mocker.patch("cv2.cvtColor")
    
    kwargs = base_kwargs.copy()
    kwargs["has_speech"] = True
    
    result = _probe_structural_inner(**kwargs)
    
    assert result.structural_score == 0.0
    assert result.ocr_required is False

def test_metadata_corroboration_requires_both(mocker, base_kwargs):
    mock_mser = mocker.Mock()
    mock_mser.detectRegions.return_value = ([], None)
    mocker.patch("cv2.MSER_create", return_value=mock_mser)
    mocker.patch("cv2.cvtColor")
    
    kwargs = base_kwargs.copy()
    kwargs["metadata_prior_confidence"] = 0.7
    
    result = _probe_structural_inner(**kwargs)
    
    # Metadata is high, but text density is 0, so no corroboration bonus
    assert result.structural_score == 0.0

def test_all_signals_compound(mocker, base_kwargs):
    mock_mser = mocker.Mock()
    mock_mser.detectRegions.return_value = ([1] * 80, None)
    mocker.patch("cv2.MSER_create", return_value=mock_mser)
    mocker.patch("cv2.cvtColor")
    mocker.patch("cv2.boundingRect", return_value=(0, 0, 20, 20))
    mocker.patch("cv2.compareHist", return_value=0.8) # Override to > 0.70
    
    kwargs = base_kwargs.copy()
    kwargs["visual_motion_density"] = 15.0
    kwargs["metadata_prior_confidence"] = 0.7
    
    result = _probe_structural_inner(**kwargs)
    
    # 0.5 (extreme text) + 0.2 (motion) + 0.2 (scene repeat) + 0.15 (metadata) = 1.05 -> clamped to 1.0
    assert result.structural_score == 1.0
    assert result.ocr_required is True


def test_ordinal_hits_trigger_ocr_even_with_thin_text_density(mocker, base_kwargs):
    """This is the real 'Top 25 Movies' scenario: clean title cards
    with minimal on-screen text (so MSER density stays low) but clear
    ordinal markers ('#1', 'Top 25'). Previously ordinal_pattern_score
    was a hardcoded 0.0 that was never even added to structural_score,
    so this case fell through and OCR never ran."""
    mock_mser = mocker.Mock()
    mock_mser.detectRegions.return_value = ([1] * 5, None)  # thin density
    mocker.patch("cv2.MSER_create", return_value=mock_mser)
    mocker.patch("cv2.cvtColor")
    mocker.patch("cv2.boundingRect", return_value=(0, 0, 20, 20))
    mocker.patch(
        "ytclfr.extractors.ocr_extractor.extract_text_from_frame_v2",
        return_value=("Top 25 Movies - #1", 0.9),
    )

    kwargs = base_kwargs.copy()
    kwargs["sampled_frames"] = [1, 2, 3, 4]  # >= ORDINAL_PATTERN_MIN_HITS

    result = _probe_structural_inner(**kwargs)

    assert result.ordinal_pattern_score == 1.0
    assert result.structural_score >= 0.55
    assert result.ocr_required is True
    assert result.structural_video_type in ("list", "ranking")


def test_single_ordinal_hit_contributes_partial_score(mocker, base_kwargs):
    """One ordinal hit (below ORDINAL_PATTERN_MIN_HITS) should nudge
    the score up without single-handedly crossing the threshold."""
    mock_mser = mocker.Mock()
    mock_mser.detectRegions.return_value = ([], None)
    mocker.patch("cv2.MSER_create", return_value=mock_mser)
    mocker.patch("cv2.cvtColor")

    call_count = {"n": 0}
    def one_hit(frame):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return ("No. 5 on our list", 0.9)
        return ("", 0.0)

    mocker.patch("ytclfr.extractors.ocr_extractor.extract_text_from_frame_v2", side_effect=one_hit)

    result = _probe_structural_inner(**base_kwargs)  # 3 sampled frames

    assert 0.0 < result.ordinal_pattern_score < 1.0
    assert result.structural_score == 0.20
    assert result.ocr_required is False


def test_ocr_failure_on_sampled_frame_does_not_crash(mocker, base_kwargs):
    """A single frame's OCR call raising must not take down the whole
    probe — this still needs to return a usable result."""
    mock_mser = mocker.Mock()
    mock_mser.detectRegions.return_value = ([], None)
    mocker.patch("cv2.MSER_create", return_value=mock_mser)
    mocker.patch("cv2.cvtColor")
    mocker.patch(
        "ytclfr.extractors.ocr_extractor.extract_text_from_frame_v2",
        side_effect=RuntimeError("OCR engine crashed"),
    )

    result = _probe_structural_inner(**base_kwargs)

    assert result.ordinal_pattern_score == 0.0
    assert result.structural_score == 0.0
