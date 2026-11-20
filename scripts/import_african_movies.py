"""Import verified, authorized full-length movie records for 54 African countries.

Usage:
  python scripts/import_african_movies.py reviewed_movies.json --output data/african_movies.json

Input is a JSON list of objects with country, video_id, title, creator,
duration_seconds, full_length_verified, embed_allowed, rights_reviewed.
A source URL alone is NOT proof of rights or completeness.
"""
import argparse
import json
import re
from collections import Counter
from pathlib import Path

COUNTRIES = (
    "Algeria", "Angola", "Benin", "Botswana", "Burkina Faso", "Burundi",
    "Cabo Verde", "Cameroon", "Central African Republic", "Chad", "Comoros",
    "Democratic Republic of the Congo", "Republic of the Congo", "Côte d'Ivoire",
    "Djibouti", "Egypt", "Equatorial Guinea", "Eritrea", "Eswatini", "Ethiopia",
    "Gabon", "Gambia", "Ghana", "Guinea", "Guinea-Bissau", "Kenya",
    "Lesotho", "Liberia", "Libya", "Madagascar", "Malawi", "Mali",
    "Mauritania", "Mauritius", "Morocco", "Mozambique", "Namibia", "Niger",
    "Nigeria", "Rwanda", "São Tomé and Príncipe", "Senegal", "Seychelles",
    "Sierra Leone", "Somalia", "South Africa", "South Sudan", "Sudan",
    "Tanzania", "Togo", "Tunisia", "Uganda", "Zambia", "Zimbabwe",
)
assert len(COUNTRIES) == 54
ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
REQUIRED_TRUE = ("full_length_verified", "embed_allowed", "rights_reviewed")

def import_records(records):
    if not isinstance(records, list):
        raise ValueError("Expected a JSON array")
    accepted, rejected, seen = [], [], set()
    counts = Counter()
    for index, item in enumerate(records):
        if not isinstance(item, dict):
            rejected.append({"index": index, "reason": "not an object"})
            continue
        country, video_id = item.get("country"), item.get("video_id")
        reason = None
        if country not in COUNTRIES:
            reason = "unsupported country"
        elif not isinstance(video_id, str) or not ID.fullmatch(video_id):
            reason = "invalid video ID"
        elif any(item.get(k) is not True for k in REQUIRED_TRUE):
            reason = "full-length, embedding or rights verification missing"
        elif not all(isinstance(item.get(k), str) and item[k].strip() for k in ("title", "creator")):
            reason = "title or creator missing"
        elif type(item.get("duration_seconds")) is not int or item["duration_seconds"] < 2400:
            reason = "runtime not verified as feature length (40+ minutes)"
        elif (country, video_id) in seen:
            reason = "duplicate country/video"
        elif counts[country] >= 100:
            reason = "100-movie country cap reached"
        if reason:
            rejected.append({"index": index, "reason": reason})
            continue
        seen.add((country, video_id))
        counts[country] += 1
        accepted.append({k: item[k] for k in ("country", "video_id", "title", "creator", "duration_seconds", *REQUIRED_TRUE)})
    summary = {
        "target": 5400, "verified_movies": len(accepted),
        "remaining": 5400 - len(accepted),
        "by_country": {country: counts[country] for country in COUNTRIES},
        "rejected": rejected,
    }
    return accepted, summary

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, default=Path("data/african_movies.json"))
    args = parser.parse_args()
    accepted, summary = import_records(json.loads(args.input.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(accepted, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
