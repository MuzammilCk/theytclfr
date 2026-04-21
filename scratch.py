
import sys

def append_to_file(path, content):
    with open(path, 'a', encoding='utf-8') as f:
        f.write(content)

test_code = """
def test_music_routes_correctly_despite_list_keyword():
    \"\"\"Music with superlatives in the title must still route
    as music-heavy. Regression for Rule 1 guard bug.
    audio.likely_music=True takes priority over list keywords.
    \"\"\"
    audio = _make_audio(
        has_audio=True, likely_music=True, bitrate=192.0
    )
    meta = _make_meta(
        title="Best of Taylor Swift Compilation",
        has_list=True,
        matched=["best of"],
    )
    decision = classify(uuid4(), audio, meta, 5, 240.0)
    assert decision.primary_route == "music-heavy"
    assert decision.confidence == HIGH_CONFIDENCE


def test_ringtone_routes_as_music_heavy():
    \"\"\"20-second ringtone with high bitrate must route as
    music-heavy. This is the end-to-end regression test
    for the original reported bug.
    \"\"\"
    audio = _make_audio(
        has_audio=True, likely_music=True, bitrate=192.0
    )
    meta = _make_meta(title="Best iPhone Ringtone 2024")
    decision = classify(uuid4(), audio, meta, 5, 20.0)
    assert decision.primary_route == "music-heavy"


def test_music_blocked_below_minimum_duration():
    \"\"\"A 5-second stub/test file must not route as music
    even with high bitrate audio.
    \"\"\"
    audio = _make_audio(
        has_audio=True, likely_music=True, bitrate=192.0
    )
    meta = _make_meta()
    decision = classify(uuid4(), audio, meta, 0, 5.0)
    # Below MUSIC_MIN_DURATION_SECONDS — should not be music
    assert decision.primary_route != "music-heavy"


def test_routing_notes_include_duration_for_music():
    \"\"\"Router notes for music-heavy must include duration
    so operators can debug misclassifications in logs.
    \"\"\"
    audio = _make_audio(
        has_audio=True, likely_music=True, bitrate=192.0
    )
    meta = _make_meta()
    decision = classify(uuid4(), audio, meta, 5, 180.0)
    assert decision.primary_route == "music-heavy"
    assert "180.0" in (decision.routing_notes or "")
"""

decisions_code = """
## DR-12 — Phase 4 router bug-fix: yt-dlp metadata format
Date: 2026-04-21
Status: ACCEPTED
Context: Session 10 implemented check_audio_from_metadata()
  expecting ffprobe JSON (streams[], format.duration).
  downloader.py stores the yt-dlp info dict which has no
  "streams" key and stores duration as a top-level float,
  not under "format". Audio detection returned False for
  100% of videos. Additionally, LIST_KEYWORDS contained
  single-word tokens ("best", "all", "top") matched with
  simple substring search, causing music videos with
  common English words in titles to misroute as list-edit.
  "tutorial" appeared in both RECIPE_KEYWORDS and
  SLIDE_KEYWORDS causing double-flagging. The duration
  gate (60-600s) in likely_music excluded ringtones and
  YouTube Shorts from music detection.
Decision:
  1. check_audio_from_metadata() reads yt-dlp fields:
     acodec, abr, subtitles. Duration gate moved to
     classifier (MUSIC_MIN_DURATION_SECONDS = 10.0s).
  2. LIST_KEYWORDS replaced with multi-word phrases only.
     Word-boundary regex (re.search with \\b) used for all
     keyword matching. Tags included in normalized text.
  3. "tutorial" removed from RECIPE_KEYWORDS. It remains
     in SLIDE_KEYWORDS only.
  4. Classifier Rule 1 guard changed from
     "NOT has_list_signal" to "NOT has_recipe_signal".
     Music with superlatives in the title now correctly
     routes as music-heavy.
  5. Unit tests rewritten to use yt-dlp format inputs.
Consequences: Router correctly classifies music content
  regardless of title wording. Ringtones, Shorts, and
  long recordings all route correctly. List-edit routing
  requires genuine multi-word list phrases.
Supersedes: NONE. Corrects implementation of DR-10.
"""

diff_code = """
## 2026-04-21 — Session 11 — Phase 4 Router Bug-Fix
Phase: Phase 4 — Preflight Router (bug-fix session)
Files changed:
  src/ytclfr/router/audio_checker.py,
  src/ytclfr/router/metadata_inspector.py,
  src/ytclfr/router/classifier.py,
  tests/unit/router/test_audio_checker.py,
  tests/unit/router/test_metadata_inspector.py,
  tests/unit/router/test_classifier.py,
  decisions.md,
  diff.md
Completed:
  - Fix 1: audio_checker.py rewritten to read yt-dlp info
    dict format (acodec, abr, subtitles, duration) instead
    of ffprobe format (streams, format.duration). Audio
    detection now works for all videos.
  - Fix 1: Duration gate (60-600s) removed from likely_music.
    Minimum duration moved to classifier as tunable constant
    MUSIC_MIN_DURATION_SECONDS = 10.0.
  - Fix 2: metadata_inspector.py updated — word-boundary
    regex matching replaces substring matching. LIST_KEYWORDS
    replaced with multi-word phrases to eliminate false
    positives on common English words. Tags included in
    normalized text. "tutorial" removed from RECIPE_KEYWORDS.
  - Fix 3: classifier.py Rule 1 guard changed from
    NOT has_list_signal to NOT has_recipe_signal. Music
    content with superlatives in the title now routes
    correctly as music-heavy.
  - Fix 4: test_audio_checker.py rewritten with yt-dlp
    format inputs. Includes regression test for 20-second
    ringtone (the original reported bug).
  - Fix 5: test_metadata_inspector.py — added regression
    tests for substring false positives, tag searching,
    tutorial double-flag fix, ringtone title non-regression.
  - Fix 6: test_classifier.py — added regression tests for
    Rule 1 priority fix, ringtone end-to-end path, duration
    gate, and routing notes content.
  - DR-12 appended to decisions.md.
Deferred:
  - NONE
Bugs found (not fixed):
  - extract_metadata() return value is discarded in
    ingest.py (MetadataError suppressed silently). The
    ffprobe VideoMetadata object is computed and thrown
    away. Fixing this requires a job schema addition and
    is deferred to Phase 9 hardening to avoid a migration
    during active Phase 5 development.
Scope creep rejected:
  - NONE
Next session must start by:
  - Reading all four control files
  - Beginning Phase 5: Worker Queue + Parallel
    Extractor Infrastructure
"""

append_to_file('tests/unit/router/test_classifier.py', test_code)
append_to_file('decisions.md', decisions_code)
append_to_file('diff.md', diff_code)
