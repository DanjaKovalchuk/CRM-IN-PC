"""Core data operations for the local desktop CRM.

The module is intentionally dependency-free so it can be used by the Tkinter
application, tests, and future packaging scripts.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import json
import uuid

APP_DIR = Path.home() / ".crm_in_pc"
DATA_FILE = APP_DIR / "data.json"
FIELD_TYPES = {
    "text": "Текст",
    "number": "Число",
    "date": "Дата",
    "textarea": "Багаторядковий текст",
    "checkbox": "Так / Ні",
}


@dataclass(frozen=True)
class StoragePaths:
    app_dir: Path = APP_DIR
    data_file: Path = DATA_FILE


def create_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_value_for_type(field_type: str):
    return False if field_type == "checkbox" else ""


def create_initial_state() -> dict:
    now = utc_now()
    return {
        "version": 1,
        "activeSectionId": "contacts",
        "sections": [
            {
                "id": "contacts",
                "name": "Контакти",
                "description": "Клієнти, партнери та відповідальні особи",
                "fields": [
                    {"id": "fullName", "name": "ПІБ", "type": "text", "required": True},
                    {"id": "phone", "name": "Телефон", "type": "text", "required": False},
                    {"id": "email", "name": "Email", "type": "text", "required": False},
                    {"id": "nextContact", "name": "Наступний контакт", "type": "date", "required": False},
                ],
                "records": [
                    {
                        "id": "contact_demo",
                        "createdAt": now,
                        "updatedAt": now,
                        "values": {
                            "fullName": "Іван Петренко",
                            "phone": "+38 067 000 00 00",
                            "email": "ivan@example.com",
                            "nextContact": "",
                        },
                    }
                ],
            },
            {
                "id": "deals",
                "name": "Угоди",
                "description": "Продажі, статуси та суми потенційних контрактів",
                "fields": [
                    {"id": "title", "name": "Назва", "type": "text", "required": True},
                    {"id": "amount", "name": "Сума", "type": "number", "required": False},
                    {"id": "stage", "name": "Етап", "type": "text", "required": False},
                    {"id": "closeDate", "name": "Дата закриття", "type": "date", "required": False},
                ],
                "records": [],
            },
        ],
    }


def ensure_state_shape(state: dict | None) -> dict:
    if not isinstance(state, dict) or not isinstance(state.get("sections"), list):
        return create_initial_state()

    sections = []
    for section in state["sections"]:
        if not isinstance(section, dict):
            continue
        fields = [field for field in section.get("fields", []) if isinstance(field, dict)]
        records = [record for record in section.get("records", []) if isinstance(record, dict)]
        sections.append(
            {
                "id": section.get("id") or create_id("section"),
                "name": section.get("name") or "Новий розділ",
                "description": section.get("description") or "",
                "fields": fields,
                "records": records,
            }
        )

    if not sections:
        return create_initial_state()

    active_id = state.get("activeSectionId")
    if not any(section["id"] == active_id for section in sections):
        active_id = sections[0]["id"]

    return {"version": 1, "activeSectionId": active_id, "sections": sections}


def load_state(paths: StoragePaths = StoragePaths()) -> dict:
    if not paths.data_file.exists():
        return create_initial_state()
    try:
        return ensure_state_shape(json.loads(paths.data_file.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, OSError):
        return create_initial_state()


def save_state(state: dict, paths: StoragePaths = StoragePaths()) -> dict:
    paths.app_dir.mkdir(parents=True, exist_ok=True)
    normalized = ensure_state_shape(state)
    paths.data_file.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")
    return normalized


def get_section(state: dict, section_id: str | None = None) -> dict:
    target_id = section_id or state.get("activeSectionId")
    for section in state.get("sections", []):
        if section["id"] == target_id:
            return section
    raise ValueError("Розділ не знайдено")


def add_section(state: dict, name: str, description: str = "") -> dict:
    trimmed_name = name.strip()
    if not trimmed_name:
        raise ValueError("Назва розділу обовʼязкова")

    next_state = deepcopy(state)
    section = {
        "id": create_id("section"),
        "name": trimmed_name,
        "description": description.strip(),
        "fields": [{"id": create_id("field"), "name": "Назва", "type": "text", "required": True}],
        "records": [],
    }
    next_state["sections"].append(section)
    next_state["activeSectionId"] = section["id"]
    return next_state


def add_field(state: dict, section_id: str, name: str, field_type: str, required: bool = False) -> dict:
    trimmed_name = name.strip()
    if not trimmed_name:
        raise ValueError("Назва поля обовʼязкова")
    if field_type not in FIELD_TYPES:
        raise ValueError("Невідомий тип поля")

    next_state = deepcopy(state)
    section = get_section(next_state, section_id)
    field = {"id": create_id("field"), "name": trimmed_name, "type": field_type, "required": bool(required)}
    section["fields"].append(field)
    for record in section["records"]:
        record.setdefault("values", {})[field["id"]] = default_value_for_type(field_type)
    return next_state


def remove_field(state: dict, section_id: str, field_id: str) -> dict:
    next_state = deepcopy(state)
    section = get_section(next_state, section_id)
    section["fields"] = [field for field in section["fields"] if field["id"] != field_id]
    for record in section["records"]:
        record.setdefault("values", {}).pop(field_id, None)
    return next_state


def validate_record(section: dict, values: dict) -> None:
    missing = []
    for field in section.get("fields", []):
        value = values.get(field["id"])
        is_empty = value is None or (not isinstance(value, bool) and str(value).strip() == "")
        if field.get("required") and is_empty:
            missing.append(field["name"])
    if missing:
        raise ValueError("Заповніть обовʼязкові поля: " + ", ".join(missing))


def normalize_values(section: dict, values: dict) -> dict:
    normalized = {}
    for field in section.get("fields", []):
        value = values.get(field["id"], default_value_for_type(field["type"]))
        if field["type"] == "checkbox":
            value = bool(value)
        normalized[field["id"]] = value
    return normalized


def upsert_record(state: dict, section_id: str, record_id: str | None, values: dict) -> dict:
    next_state = deepcopy(state)
    section = get_section(next_state, section_id)
    normalized = normalize_values(section, values)
    validate_record(section, normalized)

    now = utc_now()
    if record_id:
        for record in section["records"]:
            if record["id"] == record_id:
                record["values"] = normalized
                record["updatedAt"] = now
                return next_state
        raise ValueError("Запис не знайдено")

    section["records"].insert(0, {"id": create_id("record"), "createdAt": now, "updatedAt": now, "values": normalized})
    return next_state


def remove_record(state: dict, section_id: str, record_id: str) -> dict:
    next_state = deepcopy(state)
    section = get_section(next_state, section_id)
    section["records"] = [record for record in section["records"] if record["id"] != record_id]
    return next_state
