from flex.watch import line


def version(**doc):
    return {"ns": {"coll": "harness_versions"}, "fullDocument": doc}


def test_accepted_candidate_is_not_shown_as_promoted():
    out = line(version(_id="g7-abc123", status="candidate", acceptance="repair",
                       verdict={"reasons": ["repairs val-26-high; training energy -0.50%"]}))
    assert out == "g7-abc123    status=candidate accepted as repair   repairs val-26-high; training energy -0.50%"


def test_champion_and_retired_keep_their_acceptance():
    assert line(version(_id="g5-e942f4", status="champion", acceptance="cost", verdict={"reasons": ["cheaper"]})) == \
        "g5-e942f4    status=champion  accepted as cost     cheaper"
    assert line(version(_id="g1-289b1a", status="retired", acceptance="repair", verdict={"reasons": ["repairs"]})) == \
        "g1-289b1a    status=retired   accepted as repair   repairs"


def test_rejected_keeps_reason_verbatim():
    out = line(version(_id="g4-4a14cc", status="rejected",
                       verdict={"reasons": ["regression on val-26-high: late_job_hours 0 -> 1"]}))
    assert out == "g4-4a14cc    status=rejected  rejected             regression on val-26-high: late_job_hours 0 -> 1"


def test_champion_pointer_is_the_promotion_evidence():
    assert line({"ns": {"coll": "champion"}, "fullDocument": {"_id": "current", "version": "g7-abc123"}}) == \
        "PROMOTED  champion pointer -> g7-abc123 (committed in Atlas)"


def test_events_without_a_document_are_skipped():
    assert line({"ns": {"coll": "harness_versions"}}) is None
    assert line({"ns": {"coll": "champion"}, "fullDocument": None}) is None
