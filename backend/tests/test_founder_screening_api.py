import io

import crud
from tasks.founder_pool import dispatch_sourcing_jobs


def _create_founder(client, name: str, email: str):
    response = client.post(
        "/v1/founders",
        json={
            "name": name,
            "email": email,
            "enrichment_policy": "MANUAL",
        },
    )
    assert response.status_code == 200
    return response.json()


def _put_profile(client, founder_id: str, **overrides):
    payload = {
        "project_name": "Atlas",
        "project_summary": "Applied AI workflow tooling for finance teams.",
        "founder_role": "Founder",
        "source_type": "accelerator",
        "institution_or_program": "TreeHacks",
        "school_or_lab": "Stanford",
        "cohort_year": "2026",
        "city": "San Francisco",
        "city_basis": "program_location_not_verified_residence",
        "city_confidence": 0.33,
        "country": "United States",
        "primary_source_url": "https://example.com/source",
        "funding_status": "no_public_institutional_funding_found",
        "founder_score": 80,
        "founder_score_rationale": "Strong execution signal.",
        "vision_product_score": 40,
        "vision_product_rationale": "Early but coherent.",
        "differentiation_score": 45,
        "differentiation_rationale": "Some product wedge.",
        "traction_score": 30,
        "traction_rationale": "Very early traction.",
        "evidence_confidence": 0.7,
        "evidence_coverage": 0.6,
        "next_diligence_action": "Interview first design partner.",
        "evaluation_version": "associate_screen_v1",
        "imported_associate_call_recommended": False,
    }
    payload.update(overrides)
    response = client.put(f"/v1/founders/{founder_id}/screening-profile", json=payload)
    assert response.status_code == 200
    return response.json()


def test_put_screening_profile_recomputes_recommendation(client):
    founder = _create_founder(client, "Ava Screen", "ava.screen@test.example")
    profile = _put_profile(client, founder["id"], imported_associate_call_recommended=False)
    assert profile["recommended"] is True
    assert profile["recommendation_trigger"] == "ONE_SCORE_GT_75"
    assert profile["imported_associate_call_recommended"] is False


def test_discovery_and_recommended_filters_and_ordering(client):
    founder_a = _create_founder(client, "Ada Alpha", "ada.alpha@test.example")
    founder_b = _create_founder(client, "Bea Beta", "bea.beta@test.example")
    founder_c = _create_founder(client, "Cam Gamma", "cam.gamma@test.example")
    _create_founder(client, "Unaudited Founder", "unaudited@test.example")

    _put_profile(client, founder_a["id"], founder_score=88, founder_score_rationale="A", evidence_confidence=0.9)
    _put_profile(
        client,
        founder_b["id"],
        founder_score=55,
        founder_score_rationale="B",
        vision_product_score=55,
        vision_product_rationale="B",
        evidence_confidence=0.6,
        city=" san francisco ",
    )
    _put_profile(
        client,
        founder_c["id"],
        founder_score=50,
        founder_score_rationale="C",
        vision_product_score=50,
        vision_product_rationale="C",
        differentiation_score=40,
        differentiation_rationale="C",
        traction_score=40,
        traction_rationale="C",
        evidence_confidence=0.8,
    )

    discovery = client.get("/v1/founders/discovery?city=San%20Francisco")
    assert discovery.status_code == 200
    body = discovery.json()
    assert body["total"] == 3
    assert all(item["profile"]["city_basis"] == "program_location_not_verified_residence" for item in body["items"])

    discovery_with_unscreened = client.get("/v1/founders/discovery?include_unscreened=true")
    assert discovery_with_unscreened.status_code == 200
    assert discovery_with_unscreened.json()["total"] == 4

    recommended = client.get("/v1/founders/recommended")
    assert recommended.status_code == 200
    rec_body = recommended.json()
    assert rec_body["total"] == 2
    assert [item["founder"]["name"] for item in rec_body["items"]] == ["Ada Alpha", "Bea Beta"]


def test_import_csv_dry_run_commit_and_duplicate_checksum(client, db):
    csv_text = """record_id,founder_name,founder_role,project_name,project_summary,sector,stage,source_type,institution_or_program,school_or_lab,cohort_year,institution_affiliation_basis,city,country,city_basis,city_confidence,target_market_geography,website_url,linkedin_url,github_url,primary_source_url,source_locator,source_date,funding_status,funding_check_as_of,funding_check_confidence,funding_notes,founder_score,founder_score_rationale,vision_product_score,vision_product_rationale,differentiation_score,differentiation_rationale,traction_score,traction_rationale,evidence_confidence,evidence_coverage,individual_attribution_confidence,evaluation_scope,key_evidence,counter_evidence,unknowns,next_diligence_action,associate_call_recommended,recommendation_trigger,recommended_reason,evaluation_version,pedigree_used_in_scoring,import_status,research_priority,tags\nFOS-1,Row One,Founder,Atlas,Workflow AI,AI,Pre-seed,accelerator,TreeHacks,Stanford,2026,Official roster,San Francisco,United States,program_location_not_verified_residence,low,United States,https://atlas.example,https://linkedin.com/in/rowone,,https://example.com/atlas,PDF p. 1,2026,no_public_institutional_funding_found,2026-07-20,medium,Notes,80,Strong founder,60,Good product,40,Some wedge,20,Early traction,0.7,0.6,low,Team-level,Shipped prototype,Limited proof,Need customer proof,Call first design partner,false,NOT_RECOMMENDED,Imported false should not win,associate_screen_v1_2026-07-20,false,ready_with_caveats,high,ai|workflow\nFOS-2,Row Two,Founder,Beta,Ops AI,AI,Pre-seed,accelerator,TreeHacks,Stanford,2026,Official roster,San Francisco,United States,program_location_not_verified_residence,low,United States,https://beta.example,,https://github.com/rowtwo,https://example.com/beta,PDF p. 2,2026,no_public_institutional_funding_found,2026-07-20,medium,Notes,55,Good founder,55,Good product,45,Some wedge,35,Early traction,0.6,0.5,low,Team-level,Prototype,Limited proof,Need references,Verify pilots,true,ONE_SCORE_GT_75,Imported true should not win,associate_screen_v1_2026-07-20,false,ready_with_caveats,medium,ops|ai\n"""

    dry_run = client.post(
        "/v1/founders/import-csv",
        files={"file": ("test.csv", io.BytesIO(csv_text.encode("utf-8")), "text/csv")},
    )
    assert dry_run.status_code == 200
    dry_body = dry_run.json()
    assert dry_body["dry_run"] is True
    assert dry_body["rows_received"] == 2
    assert dry_body["founders_to_create"] == 2
    assert client.get("/v1/founders/discovery").json()["total"] == 0

    committed = client.post(
        "/v1/founders/import-csv?dry_run=false",
        files={"file": ("test.csv", io.BytesIO(csv_text.encode("utf-8")), "text/csv")},
    )
    assert committed.status_code == 200
    commit_body = committed.json()
    assert commit_body["dry_run"] is False
    assert commit_body["import_id"]
    assert client.get("/v1/founders/recommended").json()["total"] == 2

    founders = client.get("/v1/founders").json()
    assert len(founders) == 2
    assert all(founder["enrichment_policy"] == "MANUAL" for founder in founders)
    assert crud.count_founders_blocking_sourcing(db, threshold=0.3) == 0
    assert dispatch_sourcing_jobs.run().get("skipped_reason") != "enrichment_pending"

    discovery = client.get("/v1/founders/discovery").json()
    triggers = {item["profile"]["external_record_id"]: item["profile"]["recommendation_trigger"] for item in discovery["items"]}
    assert triggers["FOS-1"] == "ONE_SCORE_GT_75_AND_TWO_SCORES_GT_50"
    assert triggers["FOS-2"] == "TWO_SCORES_GT_50"

    duplicate = client.post(
        "/v1/founders/import-csv?dry_run=false",
        files={"file": ("test.csv", io.BytesIO(csv_text.encode("utf-8")), "text/csv")},
    )
    assert duplicate.status_code == 409
