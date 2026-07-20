import csv
import io
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from crud import normalize_text_value, normalize_url_value
from models import CsvImportRowError, ScreeningFundingStatus
from screening import validate_screening_scores

MAX_IMPORT_BYTES = 10 * 1024 * 1024
MAX_IMPORT_ROWS = 5000
CANONICAL_EVALUATION_VERSION = "associate_screen_v1"
SUPPORTED_IMPORT_EVALUATION_VERSIONS = {
    "associate_screen_v1",
    "associate_screen_v1_2026-07-20",
}
REQUIRED_COLUMNS = {
    "record_id",
    "founder_name",
    "project_name",
    "primary_source_url",
    "funding_status",
    "founder_score",
    "founder_score_rationale",
    "vision_product_score",
    "vision_product_rationale",
    "differentiation_score",
    "differentiation_rationale",
    "traction_score",
    "traction_rationale",
    "evaluation_version",
}
CONFIDENCE_LABELS = {
    "low": 0.33,
    "medium": 0.66,
    "high": 0.9,
}


def escape_spreadsheet_formula(value: str) -> str:
    if value and value[0] in ("=", "+", "-", "@"):
        return f"'{value}"
    return value


def parse_bool_text(value: Optional[str]) -> Optional[bool]:
    if value is None:
        return None
    normalized = value.strip().lower()
    if not normalized:
        return None
    if normalized in {"true", "1", "yes"}:
        return True
    if normalized in {"false", "0", "no"}:
        return False
    raise ValueError("Expected a boolean value")


def parse_score(value: str) -> int:
    stripped = value.strip()
    if not stripped:
        raise ValueError("Score is required")
    if any(ch in stripped for ch in (".", "e", "E")):
        raise ValueError("Score must be an integer")
    score = int(stripped)
    validate_screening_scores(score, 0, 0, 0)
    return score


def parse_confidence_value(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    stripped = value.strip().lower()
    if not stripped:
        return None
    if stripped in CONFIDENCE_LABELS:
        return CONFIDENCE_LABELS[stripped]
    parsed = float(stripped)
    if parsed < 0 or parsed > 1:
        raise ValueError("Confidence must be between 0 and 1")
    return parsed


def parse_list_cell(value: Optional[str], delimiter: str) -> List[str]:
    if value is None:
        return []
    stripped = value.strip()
    if not stripped:
        return []
    if stripped.startswith("[") and stripped.endswith("]"):
        import json

        loaded = json.loads(stripped)
        if not isinstance(loaded, list):
            raise ValueError("Expected a JSON array")
        return [str(item).strip() for item in loaded if str(item).strip()]
    return [item.strip() for item in stripped.split(delimiter) if item.strip()]


def validate_url(value: Optional[str], *, required: bool = False) -> Optional[str]:
    if value is None:
        if required:
            raise ValueError("URL is required")
        return None
    stripped = value.strip()
    if not stripped:
        if required:
            raise ValueError("URL is required")
        return None
    parsed = urlparse(stripped)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Invalid URL")
    return stripped


def parse_csv_import_bytes(
    file_bytes: bytes,
) -> Tuple[List[Dict[str, Any]], List[CsvImportRowError], List[str]]:
    if len(file_bytes) > MAX_IMPORT_BYTES:
        raise ValueError(f"CSV exceeds the {MAX_IMPORT_BYTES // (1024 * 1024)} MB limit")

    decoded = file_bytes.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(decoded))
    if reader.fieldnames is None:
        raise ValueError("CSV is missing a header row")

    missing_columns = sorted(REQUIRED_COLUMNS.difference(reader.fieldnames))
    if missing_columns:
        raise ValueError(f"CSV is missing required columns: {', '.join(missing_columns)}")

    rows: List[Dict[str, Any]] = []
    errors: List[CsvImportRowError] = []
    warnings: List[str] = []
    seen_record_ids: set[str] = set()
    saw_version_warning = False

    for row_number, raw_row in enumerate(reader, start=2):
        if len(rows) >= MAX_IMPORT_ROWS:
            raise ValueError(f"CSV exceeds the {MAX_IMPORT_ROWS} row limit")

        row = {key: (value.strip() if isinstance(value, str) else value) for key, value in raw_row.items()}
        record_id = row.get("record_id") or None
        try:
            if not record_id:
                raise ValueError("record_id is required")
            if record_id in seen_record_ids:
                raise ValueError("Duplicate record_id in upload")
            seen_record_ids.add(record_id)

            founder_name = (row.get("founder_name") or "").strip()
            project_name = (row.get("project_name") or "").strip()
            primary_source_url = validate_url(row.get("primary_source_url"), required=True)
            if not founder_name:
                raise ValueError("founder_name is required")
            if not project_name:
                raise ValueError("project_name is required")

            founder_score = parse_score(row.get("founder_score") or "")
            vision_product_score = parse_score(row.get("vision_product_score") or "")
            differentiation_score = parse_score(row.get("differentiation_score") or "")
            traction_score = parse_score(row.get("traction_score") or "")
            validate_screening_scores(
                founder_score,
                vision_product_score,
                differentiation_score,
                traction_score,
            )

            for rationale_field in (
                "founder_score_rationale",
                "vision_product_rationale",
                "differentiation_rationale",
                "traction_rationale",
            ):
                if not (row.get(rationale_field) or "").strip():
                    raise ValueError(f"{rationale_field} is required")

            evaluation_version = (row.get("evaluation_version") or "").strip()
            if evaluation_version not in SUPPORTED_IMPORT_EVALUATION_VERSIONS:
                raise ValueError("Unsupported evaluation_version")
            if evaluation_version != CANONICAL_EVALUATION_VERSION and not saw_version_warning:
                warnings.append(
                    f"Mapped import evaluation_version values to canonical {CANONICAL_EVALUATION_VERSION}."
                )
                saw_version_warning = True

            funding_status = (row.get("funding_status") or "").strip() or ScreeningFundingStatus.UNKNOWN.value
            if funding_status not in {status.value for status in ScreeningFundingStatus}:
                raise ValueError("Invalid funding_status")

            pedigree_used = parse_bool_text(row.get("pedigree_used_in_scoring"))
            if pedigree_used is True:
                raise ValueError("pedigree_used_in_scoring must be false")

            linkedin_url = validate_url(row.get("linkedin_url"), required=False)
            github_url = validate_url(row.get("github_url"), required=False)
            website_url = validate_url(row.get("website_url"), required=False)

            city = row.get("city") or None
            country = row.get("country") or None
            founder_location = ", ".join(part for part in [city, country] if part) or None

            rows.append(
                {
                    "row_number": row_number,
                    "external_record_id": record_id,
                    "founder_name": founder_name,
                    "founder_name_normalized": normalize_text_value(founder_name),
                    "founder_role": row.get("founder_role") or None,
                    "project_name": project_name,
                    "project_name_normalized": normalize_text_value(project_name),
                    "project_summary": row.get("project_summary") or None,
                    "city": city,
                    "country": country,
                    "founder_location": founder_location,
                    "cohort_year": row.get("cohort_year") or None,
                    "linkedin_url": linkedin_url,
                    "linkedin_url_normalized": normalize_url_value(linkedin_url),
                    "github_url": github_url,
                    "primary_source_url": primary_source_url,
                    "profile_data": {
                        "external_record_id": record_id,
                        "project_name": project_name,
                        "project_summary": row.get("project_summary") or None,
                        "founder_role": row.get("founder_role") or None,
                        "sector": row.get("sector") or None,
                        "stage": row.get("stage") or None,
                        "source_type": row.get("source_type") or None,
                        "institution_or_program": row.get("institution_or_program") or None,
                        "school_or_lab": row.get("school_or_lab") or None,
                        "cohort_year": row.get("cohort_year") or None,
                        "institution_affiliation_basis": row.get("institution_affiliation_basis") or None,
                        "city": city,
                        "country": country,
                        "city_basis": row.get("city_basis") or None,
                        "city_confidence": parse_confidence_value(row.get("city_confidence")),
                        "target_market_geography": row.get("target_market_geography") or None,
                        "website_url": website_url,
                        "primary_source_url": primary_source_url,
                        "source_locator": row.get("source_locator") or None,
                        "source_date": row.get("source_date") or None,
                        "funding_status": funding_status,
                        "funding_check_as_of": row.get("funding_check_as_of") or None,
                        "funding_check_confidence": parse_confidence_value(row.get("funding_check_confidence")),
                        "funding_notes": row.get("funding_notes") or None,
                        "founder_score": founder_score,
                        "founder_score_rationale": row.get("founder_score_rationale") or None,
                        "vision_product_score": vision_product_score,
                        "vision_product_rationale": row.get("vision_product_rationale") or None,
                        "differentiation_score": differentiation_score,
                        "differentiation_rationale": row.get("differentiation_rationale") or None,
                        "traction_score": traction_score,
                        "traction_rationale": row.get("traction_rationale") or None,
                        "evidence_confidence": parse_confidence_value(row.get("evidence_confidence")),
                        "evidence_coverage": parse_confidence_value(row.get("evidence_coverage")),
                        "individual_attribution_confidence": parse_confidence_value(row.get("individual_attribution_confidence")),
                        "evaluation_scope": row.get("evaluation_scope") or None,
                        "key_evidence": parse_list_cell(row.get("key_evidence"), ";"),
                        "counter_evidence": parse_list_cell(row.get("counter_evidence"), ";"),
                        "unknowns": parse_list_cell(row.get("unknowns"), ";"),
                        "next_diligence_action": row.get("next_diligence_action") or None,
                        "recommended_reason": row.get("recommended_reason") or None,
                        "evaluation_version": CANONICAL_EVALUATION_VERSION,
                        "pedigree_used_in_scoring": False,
                        "import_status": row.get("import_status") or None,
                        "research_priority": row.get("research_priority") or None,
                        "tags": parse_list_cell(row.get("tags"), "|"),
                        "imported_associate_call_recommended": parse_bool_text(row.get("associate_call_recommended")),
                        "imported_recommendation_trigger": row.get("recommendation_trigger") or None,
                        "imported_recommended_reason": row.get("recommended_reason") or None,
                    },
                }
            )
        except Exception as exc:
            errors.append(
                CsvImportRowError(
                    row_number=row_number,
                    external_record_id=record_id,
                    message=str(exc),
                )
            )

    return rows, errors, warnings
