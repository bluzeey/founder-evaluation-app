import pytest
from models import Dimension, EvidenceStatus, EvidenceType, SocialMediaBackground
from research.extractor import create_social_background
from research.social_agent import SocialAgent


SAMPLE_AGENT_RESULT = {
    "summary": "Jane Doe is a repeat founder with two shipped GitHub projects and LinkedIn posts describing customer discovery interviews.",
    "footprints": [
        {
            "platform": "github",
            "url": "https://github.com/janedoe/project-a",
            "snippet": "Open-source CLI tool with 50 commits over 6 months",
            "source_trust": 0.8,
        },
        {
            "platform": "linkedin",
            "url": "https://linkedin.com/in/janedoe",
            "snippet": "Shared learnings from 30 customer interviews",
            "source_trust": 0.6,
        },
    ],
    "evidence": [
        {
            "dimension": "execution",
            "observation": "Shipped and maintained an open-source CLI tool on GitHub with regular commits",
            "source_type": "github",
            "source_locator": "https://github.com/janedoe/project-a",
            "evidence_type": "inspected_artifact",
            "rubric_level": 3,
            "source_trust": 0.8,
            "task_relevance": 0.9,
            "recency_factor": 1.0,
            "independence_group": "github",
            "polarity": "positive",
            "status": "positive",
            "counter_evidence": None,
            "unknowns": "Commercial traction of the tool is unclear.",
        },
        {
            "dimension": "customer_selling",
            "observation": "Conducted 30 customer discovery interviews and shared learnings publicly",
            "source_type": "linkedin",
            "source_locator": "https://linkedin.com/in/janedoe",
            "evidence_type": "self_reported",
            "rubric_level": 3,
            "source_trust": 0.6,
            "task_relevance": 0.8,
            "recency_factor": 0.8,
            "independence_group": "linkedin",
            "polarity": "positive",
            "status": "positive",
            "counter_evidence": None,
            "unknowns": "Number is self-reported and not independently verified.",
        },
    ],
}


def test_create_social_background_extracts_footprints_and_evidence():
    bg = create_social_background(
        founder_id="fnd_test",
        result=SAMPLE_AGENT_RESULT,
        linkedin_url="https://linkedin.com/in/janedoe",
        github_url="https://github.com/janedoe",
    )

    assert isinstance(bg, SocialMediaBackground)
    assert bg.founder_id == "fnd_test"
    assert bg.linkedin_url == "https://linkedin.com/in/janedoe"
    assert bg.github_url == "https://github.com/janedoe"
    assert len(bg.footprints) == 2
    assert bg.footprints[0].platform == "github"
    assert bg.footprints[0].source_trust == 0.8
    assert len(bg.evidence_items) == 2

    execution = next(e for e in bg.evidence_items if e.dimension == Dimension.EXECUTION)
    assert execution.evidence_type == EvidenceType.INSPECTED_ARTIFACT
    assert execution.status == EvidenceStatus.POSITIVE


def test_social_agent_parse_response_strips_markdown_fences():
    agent = SocialAgent(api_key="dummy")
    data = {
        "choices": [
            {
                "message": {
                    "content": "```json\n" + str(SAMPLE_AGENT_RESULT).replace("'", '"') + "\n```"
                }
            }
        ]
    }
    # Note: str(SAMPLE_AGENT_RESULT).replace("'", '"') is a fragile hack for the test;
    # in practice we use json.dumps. This test just ensures fences are stripped.
    parsed = agent._parse_response(
        {
            "choices": [
                {
                    "message": {
                        "content": '```json\n{"summary": "test", "footprints": [], "evidence": []}\n```'
                    }
                }
            ]
        }
    )
    assert parsed["summary"] == "test"
