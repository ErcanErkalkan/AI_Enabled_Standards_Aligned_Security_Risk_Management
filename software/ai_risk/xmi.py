from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import xml.etree.ElementTree as ET


@dataclass(frozen=True)
class XMIAssociationEnd:
    association_name: str
    end_name: str
    type_id: str
    lower: str
    upper: str


@dataclass(frozen=True)
class XMIInspection:
    class_names: frozenset[str]
    version: str
    root_local_name: str
    association_ends: tuple[XMIAssociationEnd, ...]
    enumerations: tuple[tuple[str, tuple[str, ...]], ...]


def _local_name(name: str) -> str:
    """Return the namespace-independent local component of an XML name."""
    if name.startswith("{") and "}" in name:
        return name.split("}", 1)[1]
    if ":" in name:
        return name.split(":", 1)[1]
    return name


def _attribute_by_local_name(element: ET.Element, local_name: str) -> str:
    for key, value in element.attrib.items():
        if _local_name(key) == local_name:
            return str(value)
    return ""


def _child_value(element: ET.Element, child_local_name: str, default: str) -> str:
    """Read a UML literal child value while honoring UML's 1..1 default."""
    for child in element:
        if _local_name(child.tag) == child_local_name:
            value = _attribute_by_local_name(child, "value")
            return value if value != "" else default
    return default


def inspect_xmi(xmi_path: str | Path) -> XMIInspection:
    """Inspect the structural UML/XMI contract without hard-coding namespace URIs.

    UML tools may serialize equivalent XMI with different namespace URIs and may
    omit multiplicity literals when the UML default 1..1 applies.  The inspector
    therefore resolves XML names by local name, normalizes absent lower/upper
    multiplicities to ``1``, records UML class names, association ends and
    enumeration literals, and leaves XML parse failures to callers.
    """
    tree = ET.parse(Path(xmi_path))
    root = tree.getroot()
    class_names: set[str] = set()
    association_ends: list[XMIAssociationEnd] = []
    enumerations: list[tuple[str, tuple[str, ...]]] = []

    for element in root.iter():
        name = str(element.attrib.get("name", "")).strip()
        metaclass = _attribute_by_local_name(element, "type")

        if name and metaclass.endswith("Class"):
            class_names.add(name)

        if name and metaclass.endswith("Enumeration"):
            literals = tuple(
                str(child.attrib.get("name", "")).strip()
                for child in element
                if _local_name(child.tag) == "ownedLiteral"
                and str(child.attrib.get("name", "")).strip()
            )
            enumerations.append((name, literals))

        if name and metaclass.endswith("Association"):
            for child in element:
                if _local_name(child.tag) != "ownedEnd":
                    continue
                association_ends.append(
                    XMIAssociationEnd(
                        association_name=name,
                        end_name=str(child.attrib.get("name", "")).strip(),
                        type_id=str(child.attrib.get("type", "")).strip(),
                        lower=_child_value(child, "lowerValue", "1"),
                        upper=_child_value(child, "upperValue", "1"),
                    )
                )

    return XMIInspection(
        class_names=frozenset(class_names),
        version=_attribute_by_local_name(root, "version"),
        root_local_name=_local_name(root.tag),
        association_ends=tuple(association_ends),
        enumerations=tuple(enumerations),
    )


def parse_uml_class_names(xmi_path: str | Path) -> set[str]:
    """Return UML class names from legacy or OMG-spec XMI namespace variants."""
    return set(inspect_xmi(xmi_path).class_names)
