from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import xml.etree.ElementTree as ET


@dataclass(frozen=True)
class XMIInspection:
    class_names: frozenset[str]
    version: str
    root_local_name: str


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


def inspect_xmi(xmi_path: str | Path) -> XMIInspection:
    """Parse an XMI document without hard-coding one OMG XMI namespace URI.

    UML tools serialize equivalent XMI with different namespace URIs.  The R1
    validator therefore detects ``xmi:type`` and ``xmi:version`` by XML local
    name while still requiring the represented metaclass to end in ``Class``.
    XML parse failures intentionally propagate as ``ET.ParseError`` so callers
    can convert them into structured validator findings.
    """
    tree = ET.parse(Path(xmi_path))
    root = tree.getroot()
    class_names: set[str] = set()
    for element in root.iter():
        name = str(element.attrib.get("name", "")).strip()
        metaclass = _attribute_by_local_name(element, "type")
        if name and metaclass.endswith("Class"):
            class_names.add(name)
    return XMIInspection(
        class_names=frozenset(class_names),
        version=_attribute_by_local_name(root, "version"),
        root_local_name=_local_name(root.tag),
    )


def parse_uml_class_names(xmi_path: str | Path) -> set[str]:
    """Return UML class names from legacy or OMG-spec XMI namespace variants."""
    return set(inspect_xmi(xmi_path).class_names)
