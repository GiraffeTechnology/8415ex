"""Verified published section metadata; never complete current acceptance."""
from .current_prd import report


def build(root="."):
    result = report("sections", root)
    numbers = result["sections"]
    identifiers = [row["id"] for row in result["requirements"]]
    missing = sorted(set(range(1, 22)) - set(numbers))
    unexpected = sorted(set(numbers) - set(range(1, 22)))
    duplicated = sorted({number for number in numbers if numbers.count(number) > 1})
    findings = []
    if missing:
        findings.append({"finding": "published section number missing", "detail": missing})
    if unexpected:
        findings.append({"finding": "unexpected published section number", "detail": unexpected})
    if duplicated:
        findings.append({"finding": "duplicated published section number", "detail": duplicated})
    if len(identifiers) != len(set(identifiers)):
        findings.append({"finding": "duplicated published requirement identifier"})
    if not identifiers:
        findings.append({"finding": "published requirements are empty"})
    result.update(sectionCount=len(numbers), missingSectionNumbers=missing,
                  unexpectedSectionNumbers=unexpected, duplicatedSectionNumbers=duplicated,
                  findings=findings, consistent=not findings)
    return result
