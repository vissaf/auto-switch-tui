"""Tests for InstahyreProvider."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock


from auto_switch.models import Job
from auto_switch.providers import REGISTRY
from auto_switch.providers.instahyre import (
    InstahyreProvider,
    _clean_html_description,
    _extract_job_id,
    _format_salary,
    _format_workex,
    enrich_instahyre_job_sync,
)


def test_instahyre_registered():
    assert "instahyre" in REGISTRY
    assert REGISTRY["instahyre"] is InstahyreProvider


def test_target_locations_empty_cfg():
    p = InstahyreProvider({"locations": []})
    assert p._target_locations() == ["Anywhere in India"]


def test_target_locations_india():
    p = InstahyreProvider({"locations": ["India"]})
    assert p._target_locations() == ["Anywhere in India"]


def test_target_locations_specific_cities():
    p = InstahyreProvider({"locations": ["Bengaluru", "Gurugram"]})
    assert p._target_locations() == ["Bangalore", "Gurgaon"]


def test_target_locations_remote():
    p = InstahyreProvider({"locations": ["Remote"]})
    assert p._target_locations() == ["Work From Home"]


def test_target_locations_india_and_remote():
    p = InstahyreProvider({"locations": ["India", "Remote"]})
    locs = p._target_locations()
    assert "Anywhere in India" in locs
    assert "Work From Home" in locs


def test_target_locations_non_india_pruned():
    p = InstahyreProvider({"locations": ["London", "Dubai", "San Francisco"]})
    assert p._target_locations() == []


def test_parse_jobs():
    p = InstahyreProvider({})
    raw = [
        {
            "id": 12345,
            "title": "Senior Frontend Engineer",
            "employer": {
                "company_name": "Acme Corp",
                "instahyre_note": "Fast growing tech startup.",
            },
            "locations": "Bangalore",
            "public_url": "https://www.instahyre.com/job-12345-senior-frontend-engineer-at-acme-bangalore/",
            "keywords": ["React", "TypeScript", "Next.js"],
        },
        {
            "id": 67890,
            "title": "Full Stack Developer",
            "employer": {"company_name": "Beta AI"},
            "locations": "Work From Home",
            "public_url": "https://www.instahyre.com/job-67890-fullstack-beta-wfh/",
            "keywords": ["Python", "React"],
        },
        {"id": 99999, "title": ""},  # Should be skipped (empty title)
        {"title": "No ID"},          # Should be skipped (no ID)
    ]
    jobs = p._parse_jobs(raw)
    assert len(jobs) == 2

    j1 = jobs[0]
    assert j1.id == "instahyre-12345"
    assert j1.title == "Senior Frontend Engineer"
    assert j1.company == "Acme Corp"
    assert j1.location == "Bangalore"
    assert not j1.remote
    assert "Fast growing tech startup" in j1.description
    assert "Required Skills: React, TypeScript, Next.js" in j1.description
    assert j1.source == "instahyre"

    j2 = jobs[1]
    assert j2.id == "instahyre-67890"
    assert j2.remote is True


def test_fetch_with_mock_client():
    p = InstahyreProvider({
        "locations": ["India"],
        "search_terms": ["frontend engineer"],
    })
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "objects": [
            {
                "id": 101,
                "title": "Staff Frontend Engineer",
                "employer": {"company_name": "InnoTech"},
                "locations": "Bangalore",
                "public_url": "https://www.instahyre.com/job-101-staff-frontend/",
                "keywords": ["React", "Architecture"],
            }
        ]
    }
    client = AsyncMock()
    client.get.return_value = mock_resp

    jobs = asyncio.run(p.fetch(client))
    assert len(jobs) == 1
    assert jobs[0].id == "instahyre-101"
    assert jobs[0].company == "InnoTech"


def test_fill_detail_json_ld():
    p = InstahyreProvider({})
    job = Job(
        id="instahyre-202",
        title="Frontend Lead",
        company="TechCo",
        location="Hyderabad",
        url="https://www.instahyre.com/job-202/",
        description="initial summary",
    )
    html_content = """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "JobPosting",
          "title": "Frontend Lead",
          "description": "<p>We are seeking a <strong>Frontend Lead</strong> with deep Next.js experience.</p>",
          "datePosted": "2026-09-08",
          "baseSalary": {
            "@type": "MonetaryAmount",
            "currency": "INR",
            "value": {
              "minValue": 3000000,
              "maxValue": 4500000
            }
          }
        }
        </script>
      </head>
      <body></body>
    </html>
    """
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = html_content

    client = AsyncMock()
    client.get.return_value = mock_resp

    sem = asyncio.Semaphore(1)
    asyncio.run(p._fill_detail(job, client, sem))

    assert "deep Next.js experience" in job.description
    assert job.posted_at == "2026-09-08"
    assert job.salary_text == "INR 3,000,000 – 4,500,000"

def test_format_salary():
    assert _format_salary(None) is None
    assert _format_salary({}) is None
    data = {
        "currency": "INR",
        "value": {"minValue": 2000000, "maxValue": 3500000},
    }
    assert _format_salary(data) == "INR 2,000,000 – 3,500,000"


def test_extract_job_id():
    j1 = Job(id="instahyre-433144", title="Dev", company="Disney", location="Bangalore", url="")
    assert _extract_job_id(j1) == "433144"

    j2 = Job(
        id="",
        title="Dev",
        company="Disney",
        location="Bangalore",
        url="https://www.instahyre.com/job-433144-front-end-developer-at-the-walt-disney-company-bangalore/",
    )
    assert _extract_job_id(j2) == "433144"

    j3 = Job(id="", title="Dev", company="Disney", location="Bangalore", url="https://www.instahyre.com/job-123/")
    assert _extract_job_id(j3) == "123"

    j4 = Job(id="other-123", title="Dev", company="X", location="Y", url="https://example.com")
    assert _extract_job_id(j4) is None


def test_clean_html_description():
    html = """<html><body><p><strong>Responsibilities:</strong></p><ul>
    <li>Build responsive web apps using React.</li>
    <li>Optimise frontend performance.</li>
    </ul></body></html>"""
    cleaned = _clean_html_description(html)
    assert "Responsibilities:" in cleaned
    assert "• Build responsive web apps using React." in cleaned
    assert "• Optimise frontend performance." in cleaned


def test_format_workex():
    assert _format_workex(2, 5) == "2 – 5 Years"
    assert _format_workex(3, 3) == "3 Years"
    assert _format_workex(1, 1) == "1 Year"
    assert _format_workex(4, None) == "4+ Years"
    assert _format_workex(None, 6) == "Up to 6 Years"
    assert _format_workex(None, None) is None


def test_fill_detail_rest_api():
    p = InstahyreProvider({})
    job = Job(
        id="instahyre-433144",
        title="Front End Developer",
        company="The Walt Disney Company",
        location="Bangalore",
        url="https://www.instahyre.com/job-433144-front-end-developer-at-the-walt-disney-company-bangalore/",
        description=(
            "The Walt Disney Company is a leading global entertainment and media enterprise.\n\n"
            "Required Skills: React.js, JavaScript, Next.js"
        ),
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "id": 433144,
        "title": "Front End Developer",
        "hiring_company_name": "The Walt Disney Company",
        "description": (
            "<html><body><p><strong>Responsibilities: </strong></p><ul>"
            "<li>Feature Development: Build responsive web apps with React.js.</li>"
            "<li>Performance Optimisation: Monitor and optimise performance.</li>"
            "</ul></body></html>"
        ),
        "workex_min": 2,
        "workex_max": 5,
        "keywords": ["React.js", "JavaScript", "Next.js", "Vue.js", "Angular"],
    }

    client = AsyncMock()
    client.get.return_value = mock_resp

    sem = asyncio.Semaphore(1)
    asyncio.run(p._fill_detail(job, client, sem))

    assert "Responsibilities:" in job.description
    assert "• Feature Development: Build responsive web apps with React.js." in job.description
    assert "Experience Required: 2 – 5 Years" in job.description
    assert "Required Skills: React.js, JavaScript, Next.js, Vue.js, Angular" in job.description
    assert "About The Walt Disney Company:" in job.description
    assert "The Walt Disney Company is a leading global entertainment and media enterprise." in job.description


def test_enrich_instahyre_job_sync_skipped_for_non_instahyre():
    job = Job(id="remotive-1", title="Dev", company="X", location="Remote", url="", source="remotive")
    assert enrich_instahyre_job_sync(job) is False
