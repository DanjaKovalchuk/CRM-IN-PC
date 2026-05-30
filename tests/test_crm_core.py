import tempfile
import unittest
from pathlib import Path

from src.crm_core import (
    StoragePaths,
    add_field,
    add_section,
    create_initial_state,
    load_state,
    remove_field,
    save_state,
    upsert_record,
)


class CRMCoreTest(unittest.TestCase):
    def test_desktop_state_is_saved_to_json_file(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = StoragePaths(app_dir=Path(directory), data_file=Path(directory) / "data.json")
            state = add_section(create_initial_state(), "Заявки", "Вхідні звернення")
            save_state(state, paths)

            loaded = load_state(paths)
            self.assertEqual(loaded["sections"][-1]["name"], "Заявки")
            self.assertTrue(paths.data_file.exists())

    def test_field_is_added_and_existing_records_are_backfilled(self):
        state = create_initial_state()
        next_state = add_field(state, "contacts", "VIP", "checkbox", False)
        contacts = next(section for section in next_state["sections"] if section["id"] == "contacts")
        field = contacts["fields"][-1]

        self.assertEqual(field["name"], "VIP")
        self.assertIs(contacts["records"][0]["values"][field["id"]], False)

    def test_record_can_be_created_and_required_fields_are_validated(self):
        state = create_initial_state()
        with self.assertRaisesRegex(ValueError, "Заповніть обовʼязкові поля"):
            upsert_record(state, "deals", None, {"title": "", "amount": "", "stage": "", "closeDate": ""})

        state = upsert_record(
            state,
            "deals",
            None,
            {"title": "Впровадження CRM", "amount": "15000", "stage": "Нова", "closeDate": "2026-06-30"},
        )
        deals = next(section for section in state["sections"] if section["id"] == "deals")
        self.assertEqual(deals["records"][0]["values"]["title"], "Впровадження CRM")

    def test_removing_field_removes_values_from_records(self):
        state = remove_field(create_initial_state(), "contacts", "phone")
        contacts = next(section for section in state["sections"] if section["id"] == "contacts")

        self.assertFalse(any(field["id"] == "phone" for field in contacts["fields"]))
        self.assertNotIn("phone", contacts["records"][0]["values"])


if __name__ == "__main__":
    unittest.main()
