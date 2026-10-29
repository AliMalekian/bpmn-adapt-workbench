"""Strict, serialisable change contracts for the BPMN mutation boundary."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ChangeValidationError(ValueError):
    """Raised before XML mutation when a proposed operation is malformed."""


class ChangeAction(str, Enum):
    ADD = "ADD"
    MODIFY = "MODIFY"
    REMOVE = "REMOVE"
    RE_ADD = "RE_ADD"


class ElementSubject(str, Enum):
    NODE = "NODE"
    FLOW = "FLOW"


@dataclass(frozen=True)
class ChangeOperation:
    action: ChangeAction
    subject: ElementSubject
    target_id: str | None = None
    element_type: str | None = None
    attributes: dict[str, Any] = field(default_factory=dict)
    source_ref: str | None = None
    target_ref: str | None = None
    condition_expression: str | None = None
    clear_condition: bool = False
    parent_id: str | None = None
    xml_fragment: str | None = None

    _FIELDS = frozenset({
        "action", "subject", "target_id", "element_type", "attributes",
        "source_ref", "target_ref", "condition_expression", "clear_condition",
        "parent_id", "xml_fragment",
    })

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ChangeOperation":
        if not isinstance(value, dict):
            raise ChangeValidationError("Each change operation must be an object")
        unknown = set(value) - cls._FIELDS
        if unknown:
            raise ChangeValidationError(f"Unknown change fields: {sorted(unknown)}")
        try:
            action = ChangeAction(str(value["action"]).upper())
            subject = ElementSubject(str(value["subject"]).upper())
        except KeyError as exc:
            raise ChangeValidationError(f"Missing required change field: {exc.args[0]}") from exc
        except ValueError as exc:
            raise ChangeValidationError(str(exc)) from exc
        operation = cls(
            action=action,
            subject=subject,
            target_id=_optional_text(value.get("target_id")),
            element_type=_optional_text(value.get("element_type")),
            attributes=dict(value.get("attributes") or {}),
            source_ref=_optional_text(value.get("source_ref")),
            target_ref=_optional_text(value.get("target_ref")),
            condition_expression=(None if value.get("condition_expression") is None
                                  else str(value["condition_expression"])),
            clear_condition=bool(value.get("clear_condition", False)),
            parent_id=_optional_text(value.get("parent_id")),
            xml_fragment=_optional_text(value.get("xml_fragment")),
        )
        operation.validate()
        return operation

    def validate(self) -> None:
        if self.action in {ChangeAction.MODIFY, ChangeAction.REMOVE} and not self.target_id:
            raise ChangeValidationError(f"{self.action.value} requires target_id")
        if self.action is ChangeAction.ADD and self.subject is ElementSubject.NODE \
                and not self.element_type:
            raise ChangeValidationError("ADD NODE requires element_type")
        if self.action is ChangeAction.ADD and self.subject is ElementSubject.FLOW \
                and (not self.source_ref or not self.target_ref):
            raise ChangeValidationError("ADD FLOW requires source_ref and target_ref")
        if self.action is ChangeAction.RE_ADD and not self.xml_fragment:
            raise ChangeValidationError("RE_ADD requires xml_fragment")
        if self.subject is ElementSubject.FLOW and self.element_type not in {None, "sequenceFlow"}:
            raise ChangeValidationError("FLOW element_type must be sequenceFlow")

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "action": self.action.value,
            "subject": self.subject.value,
        }
        for name in ("target_id", "element_type", "source_ref", "target_ref",
                     "condition_expression", "parent_id", "xml_fragment"):
            value = getattr(self, name)
            if value is not None:
                result[name] = value
        if self.attributes:
            result["attributes"] = dict(self.attributes)
        if self.clear_condition:
            result["clear_condition"] = True
        return result


@dataclass(frozen=True)
class ChangeSet:
    operations: tuple[ChangeOperation, ...]
    schema_version: str = "1.0"

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ChangeSet":
        if not isinstance(value, dict):
            raise ChangeValidationError("ChangeSet must be an object")
        unknown = set(value) - {"operations", "schema_version"}
        if unknown:
            raise ChangeValidationError(f"Unknown ChangeSet fields: {sorted(unknown)}")
        raw = value.get("operations")
        if not isinstance(raw, list) or not raw:
            raise ChangeValidationError("ChangeSet.operations must be a non-empty list")
        return cls(tuple(ChangeOperation.from_dict(item) for item in raw),
                   str(value.get("schema_version", "1.0")))

    def to_dict(self) -> dict[str, Any]:
        return {"schema_version": self.schema_version,
                "operations": [item.to_dict() for item in self.operations]}


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
