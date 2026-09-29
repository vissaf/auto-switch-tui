"""Location resolution, classification, and matching tests across all supported regions."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from auto_switch.locations import filter_jobs, matches, resolve, LocTargets  # noqa: E402
from auto_switch.models import Job  # noqa: E402


def _job(location: str, remote: bool = False) -> Job:
    return Job(
        id="test-1",
        title="Software Engineer",
        company="Acme",
        location=location,
        url="https://example.com",
        remote=remote,
    )


def test_resolve_regions_and_iso_codes():
    assert resolve(["India"]).india
    assert resolve(["IN"]).india
    assert resolve(["UAE"]).uae
    assert resolve(["AE"]).uae
    assert resolve(["USA"]).usa
    assert resolve(["US"]).usa
    assert resolve(["Canada"]).canada
    assert resolve(["UK"]).uk
    assert resolve(["GB"]).uk
    assert resolve(["EU"]).eu
    assert resolve(["Remote"]).remote


def test_matches_india_cities_and_states():
    targets = LocTargets(india=True)
    cities = [
        "Bengaluru", "Bangalore", "Gurugram", "Gurgaon", "Hyderabad",
        "Pune", "Mumbai", "Navi Mumbai", "Noida", "Chennai", "Kolkata",
        "Ahmedabad", "Kochi", "Jaipur", "Indore", "Surat", "Coimbatore",
        "Chandigarh", "Karnataka", "Maharashtra", "Tamil Nadu",
    ]
    for city in cities:
        assert matches(_job(city), targets), f"Failed to match India city: {city}"
        assert matches(_job(f"{city}, India"), targets)


def test_matches_india_board_formats():
    targets = LocTargets(india=True)
    board_locs = [
        "Remote, IN",
        "KA, IN",
        "MH, IN",
        "DL, IN",
        "TS, IN",
        "TN, IN",
        "KL, IN",
        "HR, IN",
        "UP, IN",
        "GJ, IN",
        "PB, IN",
        "IN",
    ]
    for loc in board_locs:
        assert matches(_job(loc), targets), f"Failed to match board location: {loc}"


def test_india_does_not_match_non_india():
    targets = LocTargets(india=True)
    non_india = [
        "San Francisco",
        "New York, NY",
        "Seattle, WA",
        "London, UK",
        "Berlin, Germany",
        "Toronto, Canada",
        "Paris, France",
        "Dubai, UAE",
        "Indianapolis, IN",
        "Bloomington, IN",
    ]
    for loc in non_india:
        assert not matches(_job(loc), targets), f"False positive for India: {loc}"


def test_matches_usa_state_abbreviations_and_hubs():
    targets = LocTargets(usa=True)
    us_locs = [
        "San Francisco, CA", "Palo Alto, CA", "Mountain View, CA", "Sunnyvale, CA",
        "San Jose, CA", "San Diego, CA", "Bellevue, WA", "Redmond, WA",
        "Seattle, WA", "Austin, TX", "Dallas, TX", "Houston, TX",
        "Cambridge, MA", "Boston, MA", "Boulder, CO", "Denver, CO",
        "Chicago, IL", "Miami, FL", "Raleigh, NC", "Pittsburgh, PA",
        "Salt Lake City, UT", "Portland, OR", "Arlington, VA",
        "Honolulu, HI", "Washington, DC", "Remote, US", "US - Remote",
        "United States", "Remote - USA",
    ]
    for loc in us_locs:
        assert matches(_job(loc), targets), f"Failed to match USA location: {loc}"


def test_usa_does_not_match_non_usa():
    targets = LocTargets(usa=True)
    non_usa = [
        "KA, IN", "MH, IN", "Remote, IN", "Bengaluru, India",
        "London, UK", "Berlin, Germany", "Toronto, Canada", "Waterloo, ON",
    ]
    for loc in non_usa:
        assert not matches(_job(loc), targets), f"False positive for USA: {loc}"


def test_matches_canada_provinces_and_hubs():
    targets = LocTargets(canada=True)
    canada_locs = [
        "Toronto, ON", "Vancouver, BC", "Montreal, QC", "Calgary, AB",
        "Ottawa, ON", "Waterloo, ON", "Victoria, BC", "Edmonton, AB",
        "Halifax, NS", "Quebec City, QC", "Remote, CA", "Canada",
    ]
    for loc in canada_locs:
        assert matches(_job(loc), targets), f"Failed to match Canada location: {loc}"


def test_matches_uk_formats_and_hubs():
    targets = LocTargets(uk=True)
    uk_locs = [
        "London, UK", "London, United Kingdom", "London, England", "Manchester",
        "Birmingham", "Edinburgh", "Bristol", "Cambridge, UK", "Oxford, UK",
        "Glasgow, Scotland", "Cardiff, Wales", "Belfast, Northern Ireland",
        "London, GB", "Remote, GB", "United Kingdom",
    ]
    for loc in uk_locs:
        assert matches(_job(loc), targets), f"Failed to match UK location: {loc}"


def test_matches_eu_countries_and_hubs():
    targets = LocTargets(eu=True)
    eu_locs = [
        "Berlin, Germany", "Munich, Germany", "Amsterdam, Netherlands", "Dublin, Ireland",
        "Paris, France", "Madrid, Spain", "Barcelona, Spain", "Warsaw, Poland",
        "Lisbon, Portugal", "Stockholm, Sweden", "Copenhagen, Denmark", "Helsinki, Finland",
        "Oslo, Norway", "Tallinn, Estonia", "Prague, Czech Republic", "Vienna, Austria",
        "Brussels, Belgium", "Zurich, Switzerland", "Remote, EU", "Europe",
    ]
    for loc in eu_locs:
        assert matches(_job(loc), targets), f"Failed to match EU location: {loc}"


def test_matches_uae_formats():
    targets = LocTargets(uae=True)
    uae_locs = [
        "Dubai",
        "Abu Dhabi",
        "Sharjah",
        "Ajman",
        "Dubai, DU, AE",
        "Abu Dhabi, AZ, AE",
        "Remote, AE",
        "UQ, AE",
        "AE",
    ]
    for loc in uae_locs:
        assert matches(_job(loc), targets), f"Failed to match UAE location: {loc}"


def test_filter_jobs():
    jobs = [
        _job("KA, IN"),
        _job("Remote, IN"),
        _job("Bengaluru, India"),
        _job("Palo Alto, CA"),
        _job("Waterloo, ON"),
        _job("London, UK"),
    ]
    filtered_india = filter_jobs(jobs, ["India"])
    assert len(filtered_india) == 3
    assert {j.location for j in filtered_india} == {"KA, IN", "Remote, IN", "Bengaluru, India"}

    filtered_usa = filter_jobs(jobs, ["USA"])
    assert len(filtered_usa) == 1
    assert filtered_usa[0].location == "Palo Alto, CA"

    filtered_canada = filter_jobs(jobs, ["Canada"])
    assert len(filtered_canada) == 1
    assert filtered_canada[0].location == "Waterloo, ON"
