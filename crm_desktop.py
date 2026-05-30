"""Desktop entry point for CRM in PC.

Run with: python crm_desktop.py
"""

from __future__ import annotations

from pathlib import Path
import json
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from src.crm_core import (
    DATA_FILE,
    FIELD_TYPES,
    add_field,
    add_section,
    create_initial_state,
    get_section,
    load_state,
    remove_field,
    remove_record,
    save_state,
    upsert_record,
)


class FieldDialog(simpledialog.Dialog):
    def body(self, master):
        self.title("Нове поле")
        ttk.Label(master, text="Назва поля").grid(row=0, column=0, sticky="w", pady=4)
        self.name_var = tk.StringVar()
        ttk.Entry(master, textvariable=self.name_var, width=34).grid(row=0, column=1, sticky="ew", pady=4)

        ttk.Label(master, text="Тип поля").grid(row=1, column=0, sticky="w", pady=4)
        self.type_var = tk.StringVar(value="text")
        ttk.Combobox(master, textvariable=self.type_var, values=list(FIELD_TYPES.keys()), state="readonly").grid(
            row=1, column=1, sticky="ew", pady=4
        )

        self.required_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(master, text="Обовʼязкове", variable=self.required_var).grid(row=2, column=1, sticky="w", pady=4)
        master.columnconfigure(1, weight=1)
        return master

    def validate(self):
        if not self.name_var.get().strip():
            messagebox.showerror("Помилка", "Вкажіть назву поля")
            return False
        return True

    def apply(self):
        self.result = {
            "name": self.name_var.get(),
            "type": self.type_var.get(),
            "required": self.required_var.get(),
        }


class SectionDialog(simpledialog.Dialog):
    def body(self, master):
        self.title("Новий розділ")
        self.name_var = tk.StringVar()
        self.description = tk.Text(master, width=36, height=4)

        ttk.Label(master, text="Назва розділу").grid(row=0, column=0, sticky="w", pady=4)
        ttk.Entry(master, textvariable=self.name_var, width=36).grid(row=0, column=1, sticky="ew", pady=4)
        ttk.Label(master, text="Опис").grid(row=1, column=0, sticky="nw", pady=4)
        self.description.grid(row=1, column=1, sticky="ew", pady=4)
        master.columnconfigure(1, weight=1)
        return master

    def validate(self):
        if not self.name_var.get().strip():
            messagebox.showerror("Помилка", "Вкажіть назву розділу")
            return False
        return True

    def apply(self):
        self.result = {
            "name": self.name_var.get(),
            "description": self.description.get("1.0", "end").strip(),
        }


class CRMDesktopApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("CRM in PC")
        self.geometry("1180x760")
        self.minsize(980, 620)
        self.state_data = save_state(load_state())
        self.editing_record_id = None
        self.record_widgets = {}
        self._build_layout()
        self.refresh_all()

    def _build_layout(self):
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        sidebar = ttk.Frame(self, padding=14)
        sidebar.grid(row=0, column=0, sticky="ns")
        sidebar.rowconfigure(2, weight=1)

        ttk.Label(sidebar, text="CRM in PC", font=("Arial", 18, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 4))
        ttk.Label(sidebar, text="Локальна база на вашому ПК").grid(row=1, column=0, sticky="w", pady=(0, 12))

        self.sections_list = tk.Listbox(sidebar, width=28, exportselection=False)
        self.sections_list.grid(row=2, column=0, sticky="ns", pady=6)
        self.sections_list.bind("<<ListboxSelect>>", self.on_section_select)

        ttk.Button(sidebar, text="+ Новий розділ", command=self.create_section).grid(row=3, column=0, sticky="ew", pady=(12, 4))
        ttk.Button(sidebar, text="Експорт JSON", command=self.export_json).grid(row=4, column=0, sticky="ew", pady=4)
        ttk.Button(sidebar, text="Імпорт JSON", command=self.import_json).grid(row=5, column=0, sticky="ew", pady=4)
        ttk.Label(sidebar, text=f"Файл даних:\n{DATA_FILE}", wraplength=220, foreground="#64748b").grid(
            row=6, column=0, sticky="w", pady=(16, 0)
        )

        main = ttk.Frame(self, padding=14)
        main.grid(row=0, column=1, sticky="nsew")
        main.columnconfigure(0, weight=1)
        main.rowconfigure(2, weight=1)

        self.header_title = ttk.Label(main, font=("Arial", 20, "bold"))
        self.header_title.grid(row=0, column=0, sticky="w")
        self.header_description = ttk.Label(main, foreground="#64748b")
        self.header_description.grid(row=1, column=0, sticky="w", pady=(2, 12))

        notebook = ttk.Notebook(main)
        notebook.grid(row=2, column=0, sticky="nsew")

        records_tab = ttk.Frame(notebook, padding=12)
        schema_tab = ttk.Frame(notebook, padding=12)
        notebook.add(records_tab, text="Записи")
        notebook.add(schema_tab, text="Поля розділу")

        self._build_records_tab(records_tab)
        self._build_schema_tab(schema_tab)

        self.status_var = tk.StringVar(value="Готово")
        ttk.Label(main, textvariable=self.status_var, foreground="#64748b").grid(row=3, column=0, sticky="w", pady=(10, 0))

    def _build_records_tab(self, tab):
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(1, weight=1)

        self.record_form = ttk.LabelFrame(tab, text="Новий запис", padding=12)
        self.record_form.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        self.record_form.columnconfigure(1, weight=1)

        actions = ttk.Frame(tab)
        actions.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        ttk.Button(actions, text="Редагувати вибраний", command=self.edit_selected_record).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="Видалити вибраний", command=self.delete_selected_record).pack(side="left")

        self.records_tree = ttk.Treeview(tab, show="headings")
        self.records_tree.grid(row=1, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(tab, orient="vertical", command=self.records_tree.yview)
        scrollbar.grid(row=1, column=1, sticky="ns")
        self.records_tree.configure(yscrollcommand=scrollbar.set)

    def _build_schema_tab(self, tab):
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(0, weight=1)

        self.fields_tree = ttk.Treeview(tab, columns=("name", "type", "required"), show="headings")
        self.fields_tree.heading("name", text="Назва")
        self.fields_tree.heading("type", text="Тип")
        self.fields_tree.heading("required", text="Обовʼязкове")
        self.fields_tree.grid(row=0, column=0, sticky="nsew")

        buttons = ttk.Frame(tab)
        buttons.grid(row=1, column=0, sticky="w", pady=(12, 0))
        ttk.Button(buttons, text="+ Додати поле", command=self.create_field).pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="Видалити вибране поле", command=self.delete_selected_field).pack(side="left")

    def persist(self, next_state, message="Зміни збережено"):
        self.state_data = save_state(next_state)
        self.refresh_all()
        self.status_var.set(message)

    def active_section(self):
        return get_section(self.state_data)

    def refresh_all(self):
        self.refresh_sections()
        self.refresh_header()
        self.refresh_record_form()
        self.refresh_records_table()
        self.refresh_fields_table()

    def refresh_sections(self):
        active_id = self.state_data.get("activeSectionId")
        self.sections_list.delete(0, "end")
        active_index = 0
        for index, section in enumerate(self.state_data["sections"]):
            self.sections_list.insert("end", f"{section['name']} ({len(section['records'])})")
            if section["id"] == active_id:
                active_index = index
        self.sections_list.selection_set(active_index)

    def refresh_header(self):
        section = self.active_section()
        self.header_title.configure(text=section["name"])
        self.header_description.configure(text=section.get("description") or "Створюйте поля та записи в цьому розділі.")

    def refresh_record_form(self):
        for child in self.record_form.winfo_children():
            child.destroy()
        self.record_widgets = {}
        section = self.active_section()
        record = self.find_record(self.editing_record_id)
        self.record_form.configure(text="Редагувати запис" if record else "Новий запис")

        for row, field in enumerate(section["fields"]):
            label = f"{field['name']}{' *' if field.get('required') else ''}"
            ttk.Label(self.record_form, text=label).grid(row=row, column=0, sticky="w", padx=(0, 8), pady=4)
            value = record.get("values", {}).get(field["id"], "") if record else ""
            widget = self.create_value_widget(self.record_form, field, value)
            widget.grid(row=row, column=1, sticky="ew", pady=4)
            self.record_widgets[field["id"]] = (field, widget)

        button_row = len(section["fields"])
        ttk.Button(self.record_form, text="Оновити" if record else "Зберегти", command=self.save_record).grid(
            row=button_row, column=1, sticky="e", pady=(10, 0)
        )
        if record:
            ttk.Button(self.record_form, text="Скасувати", command=self.cancel_edit).grid(
                row=button_row, column=0, sticky="w", pady=(10, 0)
            )

    def create_value_widget(self, parent, field, value):
        if field["type"] == "textarea":
            text = tk.Text(parent, height=4, width=40)
            text.insert("1.0", str(value or ""))
            return text
        if field["type"] == "checkbox":
            variable = tk.BooleanVar(value=bool(value))
            checkbox = ttk.Checkbutton(parent, variable=variable)
            checkbox.variable = variable
            return checkbox
        entry = ttk.Entry(parent)
        entry.insert(0, str(value or ""))
        return entry

    def refresh_records_table(self):
        section = self.active_section()
        columns = [field["id"] for field in section["fields"]] + ["updatedAt"]
        self.records_tree.configure(columns=columns)
        for column in columns:
            field = next((item for item in section["fields"] if item["id"] == column), None)
            self.records_tree.heading(column, text=field["name"] if field else "Оновлено")
            self.records_tree.column(column, width=150, minwidth=100)
        self.records_tree.delete(*self.records_tree.get_children())
        for record in section["records"]:
            values = [self.format_value(record.get("values", {}).get(field["id"]), field["type"]) for field in section["fields"]]
            values.append(record.get("updatedAt", ""))
            self.records_tree.insert("", "end", iid=record["id"], values=values)

    def refresh_fields_table(self):
        self.fields_tree.delete(*self.fields_tree.get_children())
        for field in self.active_section()["fields"]:
            self.fields_tree.insert(
                "",
                "end",
                iid=field["id"],
                values=(field["name"], FIELD_TYPES.get(field["type"], field["type"]), "Так" if field.get("required") else "Ні"),
            )

    def format_value(self, value, field_type):
        if field_type == "checkbox":
            return "Так" if value else "Ні"
        return value or "—"

    def find_record(self, record_id):
        if not record_id:
            return None
        return next((record for record in self.active_section()["records"] if record["id"] == record_id), None)

    def collect_record_values(self):
        values = {}
        for field_id, (field, widget) in self.record_widgets.items():
            if field["type"] == "textarea":
                values[field_id] = widget.get("1.0", "end").strip()
            elif field["type"] == "checkbox":
                values[field_id] = widget.variable.get()
            else:
                values[field_id] = widget.get().strip()
        return values

    def on_section_select(self, _event=None):
        selection = self.sections_list.curselection()
        if not selection:
            return
        selected = self.state_data["sections"][selection[0]]
        if selected["id"] != self.state_data.get("activeSectionId"):
            self.state_data["activeSectionId"] = selected["id"]
            self.editing_record_id = None
            self.persist(self.state_data, "Розділ відкрито")

    def create_section(self):
        dialog = SectionDialog(self)
        if dialog.result:
            try:
                self.editing_record_id = None
                self.persist(add_section(self.state_data, dialog.result["name"], dialog.result["description"]), "Розділ створено")
            except ValueError as error:
                messagebox.showerror("Помилка", str(error))

    def create_field(self):
        dialog = FieldDialog(self)
        if dialog.result:
            section = self.active_section()
            try:
                self.persist(
                    add_field(
                        self.state_data,
                        section["id"],
                        dialog.result["name"],
                        dialog.result["type"],
                        dialog.result["required"],
                    ),
                    "Поле додано",
                )
            except ValueError as error:
                messagebox.showerror("Помилка", str(error))

    def delete_selected_field(self):
        selection = self.fields_tree.selection()
        if not selection:
            messagebox.showinfo("Поле", "Виберіть поле для видалення")
            return
        if not messagebox.askyesno("Підтвердження", "Видалити поле та його значення у всіх записах?"):
            return
        self.persist(remove_field(self.state_data, self.active_section()["id"], selection[0]), "Поле видалено")

    def save_record(self):
        try:
            self.persist(
                upsert_record(self.state_data, self.active_section()["id"], self.editing_record_id, self.collect_record_values()),
                "Запис оновлено" if self.editing_record_id else "Запис створено",
            )
            self.editing_record_id = None
            self.refresh_record_form()
        except ValueError as error:
            messagebox.showerror("Помилка", str(error))

    def edit_selected_record(self):
        selection = self.records_tree.selection()
        if not selection:
            messagebox.showinfo("Запис", "Виберіть запис для редагування")
            return
        self.editing_record_id = selection[0]
        self.refresh_record_form()

    def delete_selected_record(self):
        selection = self.records_tree.selection()
        if not selection:
            messagebox.showinfo("Запис", "Виберіть запис для видалення")
            return
        if messagebox.askyesno("Підтвердження", "Видалити вибраний запис?"):
            self.persist(remove_record(self.state_data, self.active_section()["id"], selection[0]), "Запис видалено")

    def cancel_edit(self):
        self.editing_record_id = None
        self.refresh_record_form()

    def export_json(self):
        path = filedialog.asksaveasfilename(
            title="Експорт CRM",
            defaultextension=".json",
            filetypes=(("JSON", "*.json"), ("Усі файли", "*.*")),
            initialfile="crm-in-pc-backup.json",
        )
        if not path:
            return
        Path(path).write_text(json.dumps(self.state_data, ensure_ascii=False, indent=2), encoding="utf-8")
        self.status_var.set(f"Експортовано: {path}")

    def import_json(self):
        path = filedialog.askopenfilename(title="Імпорт CRM", filetypes=(("JSON", "*.json"), ("Усі файли", "*.*")))
        if not path:
            return
        try:
            imported = json.loads(Path(path).read_text(encoding="utf-8"))
            self.editing_record_id = None
            self.persist(imported, "Дані імпортовано")
        except (json.JSONDecodeError, OSError) as error:
            messagebox.showerror("Помилка імпорту", str(error))


def main():
    app = CRMDesktopApp()
    app.mainloop()


if __name__ == "__main__":
    main()
