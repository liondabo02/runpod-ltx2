"""public-apis katalogu: ayristirma, filtreleme, bos katalog davranisi."""

from __future__ import annotations

import json

from ahos.api_catalog import load, parse_readme, search, stats

SAMPLE = """
## Index

### Animals

API | Description | Auth | HTTPS | CORS |
|---|---|---|---|---|
| [Cat Facts](https://alexwohlbruck.github.io/cat-facts/) | Daily cat facts | No | Yes | No |
| [Dogs](https://dog.ceo/dog-api/) | Based on the Stanford Dogs Dataset | No | Yes | Yes |

### Weather

API | Description | Auth | HTTPS | CORS |
|---|---|---|---|---|
| [OpenWeatherMap](https://openweathermap.org/api) | Weather forecasts | `apiKey` | Yes | Yes |
| [Legacy Weather](http://example.invalid/weather) | Old http only endpoint | No | No | Unknown |
"""


def test_parse_readme_extracts_entries_and_categories() -> None:
    entries = parse_readme(SAMPLE)
    assert len(entries) == 4
    cat = next(e for e in entries if e["name"] == "Cat Facts")
    assert cat["category"] == "Animals"
    assert cat["auth"] == "No"
    assert cat["https"] is True
    legacy = next(e for e in entries if e["name"] == "Legacy Weather")
    assert legacy["https"] is False


def test_search_defaults_to_https_only(tmp_path) -> None:
    catalog = tmp_path / "public-apis.json"
    catalog.write_text(json.dumps({"entries": parse_readme(SAMPLE)}), encoding="utf-8")

    result = search("weather", path=catalog)
    assert result["ok"] is True
    assert result["total"] == 1                      # http'li uç elenir
    assert result["results"][0]["name"] == "OpenWeatherMap"

    everything = search("weather", https_only=False, path=catalog)
    assert everything["total"] == 2


def test_no_auth_filter_and_category_filter(tmp_path) -> None:
    catalog = tmp_path / "public-apis.json"
    catalog.write_text(json.dumps({"entries": parse_readme(SAMPLE)}), encoding="utf-8")

    free = search("", no_auth_only=True, path=catalog)
    assert {e["name"] for e in free["results"]} == {"Cat Facts", "Dogs"}

    animals = search("", category="Animals", path=catalog)
    assert animals["total"] == 2


def test_missing_catalog_returns_reason_not_fake_results(tmp_path) -> None:
    result = search("weather", path=tmp_path / "yok.json")
    assert result["ok"] is False
    assert result["results"] == []
    assert "katalog yok" in result["reason"]

    assert load(tmp_path / "yok.json") == []
    assert stats(tmp_path / "yok.json")["available"] is False


def test_stats_counts_authentication_and_https(tmp_path) -> None:
    catalog = tmp_path / "public-apis.json"
    catalog.write_text(json.dumps({"entries": parse_readme(SAMPLE)}), encoding="utf-8")

    report = stats(catalog)
    assert report == {
        "available": True,
        "entries": 4,
        "categories": 2,
        "no_auth": 3,
        "https": 3,
    }
