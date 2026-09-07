#!/usr/bin/env python3
"""Validate a UML/XMI interoperability export against the v0.2.1 contract.

This oracle is intentionally structural. It checks the tested model inventory,
selected mapping-critical association multiplicities, MappingStatus vocabulary,
and an optional GUI-created sentinel. It does not claim general UML/OCL semantic
conformance or byte identity across modeling tools.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

EXPECTED_COUNTS = {
    "packages": 2,
    "primitive_types": 4,
    "enumerations": 7,
    "classes": 28,
    "attributes": 79,
    "associations": 27,
    "association_ends": 54,
    "generalizations": 6,
}
EXPECTED_ASSOCIATION_ENDS = {
    ("StandardToMetric", "metrics"): ("0", "*"),
    ("QuestionToMetric", "metrics"): ("0", "*"),
    ("MetricToEvidenceRequirement", "metrics"): ("0", "*"),
    ("StandardToMeasurementConcept", "measurementConcept"): ("0", "1"),
}
EXPECTED_MAPPING_STATUS = [
    "notAssessed",
    "acceptable",
    "minorAdjustment",
    "majorAdjustment",
    "rejected",
    "deferred",
]


def local_name(name: str) -> str:
    if name.startswith("{") and "}" in name:
        return name.split("}", 1)[1]
    if ":" in name:
        return name.split(":", 1)[1]
    return name


def attr_local(element: ET.Element, wanted: str) -> str:
    for key, value in element.attrib.items():
        if local_name(key) == wanted:
            return str(value)
    return ""


def child_literal(element: ET.Element, child_name: str, default: str) -> str:
    for child in element:
        if local_name(child.tag) == child_name:
            value = attr_local(child, "value")
            return value if value != "" else default
    return default


def inspect(path: Path) -> dict[str, object]:
    tree = ET.parse(path)
    root = tree.getroot()
    counts = {key: 0 for key in EXPECTED_COUNTS}
    counts["constraints"] = 0
    names: set[str] = set()
    association_ends: dict[str, dict[str, dict[str, str]]] = {}
    enumerations: dict[str, list[str]] = {}

    for element in root.iter():
        tag = local_name(element.tag)
        metaclass = attr_local(element, "type")
        name = str(element.attrib.get("name", "")).strip()
        if name:
            names.add(name)

        if tag == "packagedElement" and metaclass.endswith("Package"):
            counts["packages"] += 1
        elif tag == "packagedElement" and metaclass.endswith("PrimitiveType"):
            counts["primitive_types"] += 1
        elif tag == "packagedElement" and metaclass.endswith("Enumeration"):
            counts["enumerations"] += 1
            literals = [
                str(c.attrib.get("name", "")).strip()
                for c in element
                if local_name(c.tag) == "ownedLiteral"
                and str(c.attrib.get("name", "")).strip()
            ]
            enumerations[name] = literals
        elif tag == "packagedElement" and metaclass.endswith("Class"):
            counts["classes"] += 1
        elif tag == "packagedElement" and metaclass.endswith("Association"):
            counts["associations"] += 1
            ends: dict[str, dict[str, str]] = {}
            for child in element:
                if local_name(child.tag) != "ownedEnd":
                    continue
                counts["association_ends"] += 1
                end_name = str(child.attrib.get("name", "")).strip()
                ends[end_name] = {
                    "lower": child_literal(child, "lowerValue", "1"),
                    "upper": child_literal(child, "upperValue", "1"),
                    "type": str(child.attrib.get("type", "")).strip(),
                }
            association_ends[name] = ends

        if tag == "ownedAttribute" and metaclass.endswith("Property"):
            counts["attributes"] += 1
        elif tag == "generalization":
            counts["generalizations"] += 1
        elif tag == "ownedRule" and metaclass.endswith("Constraint"):
            counts["constraints"] += 1

    return {
        "file": str(path),
        "root": local_name(root.tag),
        "xmi_version": attr_local(root, "version"),
        "counts": counts,
        "association_ends": association_ends,
        "enumerations": enumerations,
        "names": sorted(names),
    }


def validate(
    report: dict[str, object], expected_constraints: int, sentinel: str | None
) -> list[str]:
    failures: list[str] = []
    counts = report["counts"]
    assert isinstance(counts, dict)
    for key, expected in EXPECTED_COUNTS.items():
        found = int(counts.get(key, -1))
        if found != expected:
            failures.append(f"inventory {key}: expected {expected}, found {found}")
    found_constraints = int(counts.get("constraints", -1))
    if found_constraints != expected_constraints:
        failures.append(
            f"inventory constraints: expected {expected_constraints}, found {found_constraints}"
        )

    if report.get("root") != "XMI":
        failures.append(f"root: expected XMI, found {report.get('root')!r}")

    assoc = report["association_ends"]
    assert isinstance(assoc, dict)
    for (association, end_name), expected in EXPECTED_ASSOCIATION_ENDS.items():
        found = assoc.get(association, {}).get(end_name)
        if not found:
            failures.append(f"missing association end {association}.{end_name}")
            continue
        pair = (str(found.get("lower", "")), str(found.get("upper", "")))
        if pair != expected:
            failures.append(
                f"{association}.{end_name}: expected {expected[0]}..{expected[1]}, "
                f"found {pair[0]}..{pair[1]}"
            )

    enums = report["enumerations"]
    assert isinstance(enums, dict)
    mapping_status = enums.get("MappingStatus")
    if mapping_status != EXPECTED_MAPPING_STATUS:
        failures.append(
            "MappingStatus: expected "
            + ",".join(EXPECTED_MAPPING_STATUS)
            + "; found "
            + ",".join(mapping_status or [])
        )

    if sentinel:
        names = report["names"]
        assert isinstance(names, list)
        if sentinel not in names:
            failures.append(f"sentinel {sentinel!r} not found")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path, help="XMI file exported by the UML tool")
    parser.add_argument(
        "--expected-constraints",
        type=int,
        default=7,
        help="strict expected constraint count (default: 7)",
    )
    parser.add_argument(
        "--sentinel",
        help="optional GUI-created package/class name that must survive export",
    )
    parser.add_argument(
        "--json-out", type=Path, help="write the full structural inventory as JSON"
    )
    args = parser.parse_args()

    try:
        report = inspect(args.input)
    except (OSError, ET.ParseError, ValueError) as exc:
        print(
            f"FAIL: unable to inspect XMI ({type(exc).__name__}: {exc})",
            file=sys.stderr,
        )
        return 2

    failures = validate(report, args.expected_constraints, args.sentinel)
    report["expected_constraints"] = args.expected_constraints
    report["sentinel_required"] = args.sentinel
    report["failures"] = failures
    report["status"] = "PASS" if not failures else "FAIL"

    payload = json.dumps(report, indent=2, sort_keys=True)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(payload + "\n", encoding="utf-8")

    counts = report["counts"]
    print(
        "Inventory: "
        f"packages={counts['packages']}, primitives={counts['primitive_types']}, "
        f"enums={counts['enumerations']}, classes={counts['classes']}, "
        f"attributes={counts['attributes']}, associations={counts['associations']}/"
        f"{counts['association_ends']} ends, generalizations={counts['generalizations']}, "
        f"constraints={counts['constraints']}"
    )
    if failures:
        print("FAIL")
        for item in failures:
            print(f"- {item}")
        return 1
    print("PASS: structural inventory and selected v0.2.1 contract preserved")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
