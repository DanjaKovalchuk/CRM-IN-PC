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
    get_section,
    load_state,
    remove_field,
    remove_record,
    save_state,
    upsert_record,
)
from src.excel_io import export_section_to_xlsx, import_values_for_section

COLORS = {
    "bg": "#dbeafe",
    "glass": "#f8fafc",
    "card": "#ffffff",
    "primary": "#2563eb",
    "primary_dark": "#1d4ed8",
    "accent": "#7c3aed",
    "text": "#172033",
    "muted": "#64748b",
    "danger": "#dc2626",
    "border": "#cbd5e1",
}


class ModernFrame(tk.Frame):
    def __init__(self, master, **kwargs):
        super().__init__(master, bg=kwargs.pop("bg", COLORS["glass"]), highlightbackground="#ffffff", highlightthickness=1, **kwargs)


class FieldDialog(simpledialog.Dialog):
    def body(self, master):
        self.title("Нове поле")
        self.name_var = tk.StringVar()
        self.type_var = tk.StringVar(value="text")
        self.required_var = tk.BooleanVar(value=False)

        ttk.Label(master, text="Назва поля").grid(row=0, column=0, sticky="w", pady=6, padx=(0, 8))
        ttk.Entry(master, textvariable=self.name_var, width=34).grid(row=0, column=1, sticky="ew", pady=6)
        ttk.Label(master, text="Тип поля").grid(row=1, column=0, sticky="w", pady=6, padx=(0, 8))
        ttk.Combobox(
            master,
            textvariable=self.type_var,
            values=[f"{key} — {label}" for key, label in FIELD_TYPES.items()],
            state="readonly",
        ).grid(row=1, column=1, sticky="ew", pady=6)
        ttk.Checkbutton(master, text="Обовʼязкове", variable=self.required_var).grid(row=2, column=1, sticky="w", pady=6)
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
            "type": self.type_var.get().split(" — ", 1)[0],
            "required": self.required_var.get(),
        }


class SectionDialog(simpledialog.Dialog):
    def body(self, master):
        self.title("Новий розділ")
        self.name_var = tk.StringVar()
        self.description = tk.Text(master, width=38, height=4, relief="flat", highlightthickness=1, highlightbackground=COLORS["border"])
        ttk.Label(master, text="Назва розділу").grid(row=0, column=0, sticky="w", pady=6, padx=(0, 8))
        ttk.Entry(master, textvariable=self.name_var, width=38).grid(row=0, column=1, sticky="ew", pady=6)
        ttk.Label(master, text="Опис").grid(row=1, column=0, sticky="nw", pady=6, padx=(0, 8))
        self.description.grid(row=1, column=1, sticky="ew", pady=6)
        master.columnconfigure(1, weight=1)
        return master

    def validate(self):
        if not self.name_var.get().strip():
            messagebox.showerror("Помилка", "Вкажіть назву розділу")
            return False
        return True

    def apply(self):
        self.result = {"name": self.name_var.get(), "description": self.description.get("1.0", "end").strip()}


class ColumnsDialog(simpledialog.Dialog):
    def __init__(self, parent, section):
        self.section = section
        self.vars = {}
        super().__init__(parent, "Колонки реєстру")

    def body(self, master):
        ttk.Label(master, text="Оберіть поля, які показувати в реєстрі записів").grid(row=0, column=0, sticky="w", pady=(0, 8))
        visible = set(self.section.get("visibleFieldIds") or [field["id"] for field in self.section["fields"]])
        for index, field in enumerate(self.section["fields"], start=1):
            var = tk.BooleanVar(value=field["id"] in visible)
            self.vars[field["id"]] = var
            ttk.Checkbutton(master, text=field["name"], variable=var).grid(row=index, column=0, sticky="w", pady=3)
        return master

    def apply(self):
        self.result = [field_id for field_id, var in self.vars.items() if var.get()]


class CRMDesktopApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("CRM in PC")
        self.geometry("1280x780")
        self.minsize(1040, 660)
        self.configure(bg=COLORS["bg"])
        self.attributes("-alpha", 0.98)
        self.state_data = save_state(load_state())
        self.editing_record_id = None
        self.record_widgets = {}
        self._configure_style()
        self._build_layout()
        self.refresh_all(open_registry=True)

    def _configure_style(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background=COLORS["glass"])
        style.configure("Card.TFrame", background=COLORS["card"], relief="flat")
        style.configure("TLabel", background=COLORS["glass"], foreground=COLORS["text"], font=("Segoe UI", 10))
        style.configure("Muted.TLabel", foreground=COLORS["muted"], background=COLORS["glass"])
        style.configure("Title.TLabel", font=("Segoe UI", 23, "bold"), background=COLORS["glass"], foreground=COLORS["text"])
        style.configure("TButton", font=("Segoe UI", 10, "bold"), padding=(14, 9), borderwidth=0)
        style.map("TButton", background=[("active", "#e0e7ff")])
        style.configure("Primary.TButton", background=COLORS["primary"], foreground="white")
        style.map("Primary.TButton", background=[("active", COLORS["primary_dark"])] )
        style.configure("Danger.TButton", background="#fee2e2", foreground=COLORS["danger"])
        style.configure("Treeview", rowheight=32, font=("Segoe UI", 10), background="white", fieldbackground="white", bordercolor=COLORS["border"])
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"), background="#e0e7ff", foreground=COLORS["text"])
        style.configure("TNotebook", background=COLORS["glass"], borderwidth=0)
        style.configure("TNotebook.Tab", font=("Segoe UI", 10, "bold"), padding=(18, 10), background="#e2e8f0")
        style.map("TNotebook.Tab", background=[("selected", "white")], foreground=[("selected", COLORS["primary"])] )

    def _build_layout(self):
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        sidebar = ModernFrame(self, bg="#eff6ff", padx=18, pady=18)
        sidebar.grid(row=0, column=0, sticky="ns", padx=(18, 8), pady=18)
        sidebar.rowconfigure(3, weight=1)

        tk.Label(sidebar, text="CRM", bg=COLORS["primary"], fg="white", font=("Segoe UI", 18, "bold"), width=5, pady=8).grid(
            row=0, column=0, sticky="w", pady=(0, 10)
        )
        tk.Label(sidebar, text="CRM in PC", bg="#eff6ff", fg=COLORS["text"], font=("Segoe UI", 18, "bold")).grid(row=1, column=0, sticky="w")
        tk.Label(sidebar, text="локальна база на вашому ПК", bg="#eff6ff", fg=COLORS["muted"], font=("Segoe UI", 9)).grid(
            row=2, column=0, sticky="nw", pady=(0, 10)
        )

        self.sections_list = tk.Listbox(
            sidebar,
            width=28,
            borderwidth=0,
            highlightthickness=0,
            activestyle="none",
            exportselection=False,
            bg="#eff6ff",
            fg=COLORS["text"],
            selectbackground=COLORS["primary"],
            selectforeground="white",
            font=("Segoe UI", 11, "bold"),
        )
        self.sections_list.grid(row=3, column=0, sticky="nsew", pady=12)
        self.sections_list.bind("<<ListboxSelect>>", self.on_section_select)

        ttk.Button(sidebar, text="+ Новий розділ", style="Primary.TButton", command=self.create_section).grid(row=4, column=0, sticky="ew", pady=(8, 5))
        ttk.Button(sidebar, text="⬇ Експорт Excel", command=self.export_excel).grid(row=5, column=0, sticky="ew", pady=5)
        ttk.Button(sidebar, text="⬆ Імпорт Excel", command=self.import_excel).grid(row=6, column=0, sticky="ew", pady=5)
        ttk.Button(sidebar, text="Експорт JSON", command=self.export_json).grid(row=7, column=0, sticky="ew", pady=5)
        ttk.Button(sidebar, text="Імпорт JSON", command=self.import_json).grid(row=8, column=0, sticky="ew", pady=5)
        tk.Label(sidebar, text=f"Файл даних:\n{DATA_FILE}", bg="#eff6ff", fg=COLORS["muted"], wraplength=240, justify="left").grid(
            row=9, column=0, sticky="w", pady=(14, 0)
        )

        main = ModernFrame(self, bg=COLORS["glass"], padx=18, pady=18)
        main.grid(row=0, column=1, sticky="nsew", padx=(8, 18), pady=18)
        main.columnconfigure(0, weight=1)
        main.rowconfigure(2, weight=1)

        self.header_title = ttk.Label(main, style="Title.TLabel")
        self.header_title.grid(row=0, column=0, sticky="w")
        self.header_description = ttk.Label(main, style="Muted.TLabel")
        self.header_description.grid(row=1, column=0, sticky="w", pady=(4, 14))

        self.notebook = ttk.Notebook(main)
        self.notebook.grid(row=2, column=0, sticky="nsew")

        self.registry_tab = ttk.Frame(self.notebook, padding=14, style="Card.TFrame")
        self.card_tab = ttk.Frame(self.notebook, padding=14, style="Card.TFrame")
        self.schema_tab = ttk.Frame(self.notebook, padding=14, style="Card.TFrame")
        self.notebook.add(self.registry_tab, text="Реєстр записів")
        self.notebook.add(self.card_tab, text="Картка запису")
        self.notebook.add(self.schema_tab, text="Поля розділу")

        self._build_registry_tab()
        self._build_card_tab()
        self._build_schema_tab()

        self.status_var = tk.StringVar(value="Готово")
        ttk.Label(main, textvariable=self.status_var, style="Muted.TLabel").grid(row=3, column=0, sticky="w", pady=(10, 0))

    def _build_registry_tab(self):
        self.registry_tab.columnconfigure(0, weight=1)
        self.registry_tab.rowconfigure(1, weight=1)
        actions = ttk.Frame(self.registry_tab, style="Card.TFrame")
        actions.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        ttk.Button(actions, text="+ Новий запис", style="Primary.TButton", command=self.new_record).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="Відкрити", command=self.open_selected_record).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="Копіювати", command=self.copy_selected_record).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="Видалити", style="Danger.TButton", command=self.delete_selected_record).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="Колонки реєстру", command=self.configure_columns).pack(side="left")

        self.records_tree = ttk.Treeview(self.registry_tab, show="headings", selectmode="browse")
        self.records_tree.grid(row=1, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(self.registry_tab, orient="vertical", command=self.records_tree.yview)
        scrollbar.grid(row=1, column=1, sticky="ns")
        self.records_tree.configure(yscrollcommand=scrollbar.set)
        self.records_tree.bind("<Double-1>", lambda _event: self.open_selected_record())
        self.records_tree.bind("<Button-3>", self.show_record_context_menu)

        self.record_menu = tk.Menu(self, tearoff=0)
        self.record_menu.add_command(label="Відкрити", command=self.open_selected_record)
        self.record_menu.add_command(label="Копіювати", command=self.copy_selected_record)
        self.record_menu.add_separator()
        self.record_menu.add_command(label="Видалити", command=self.delete_selected_record)

    def _build_card_tab(self):
        self.card_tab.columnconfigure(0, weight=1)
        self.record_form = ttk.Frame(self.card_tab, style="Card.TFrame")
        self.record_form.grid(row=0, column=0, sticky="ew")

    def _build_schema_tab(self):
        self.schema_tab.columnconfigure(0, weight=1)
        self.schema_tab.rowconfigure(0, weight=1)
        self.fields_tree = ttk.Treeview(self.schema_tab, columns=("name", "type", "required"), show="headings")
        self.fields_tree.heading("name", text="Назва")
        self.fields_tree.heading("type", text="Тип")
        self.fields_tree.heading("required", text="Обовʼязкове")
        self.fields_tree.grid(row=0, column=0, sticky="nsew")
        buttons = ttk.Frame(self.schema_tab, style="Card.TFrame")
        buttons.grid(row=1, column=0, sticky="w", pady=(12, 0))
        ttk.Button(buttons, text="+ Додати поле", style="Primary.TButton", command=self.create_field).pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="Видалити вибране поле", style="Danger.TButton", command=self.delete_selected_field).pack(side="left")

    def persist(self, next_state, message="Зміни збережено", open_registry=False):
        self.state_data = save_state(next_state)
        self.refresh_all(open_registry=open_registry)
        self.status_var.set(message)

    def active_section(self):
        return get_section(self.state_data)

    def refresh_all(self, open_registry=False):
        self.refresh_sections()
        self.refresh_header()
        self.refresh_record_form()
        self.refresh_records_table()
        self.refresh_fields_table()
        if open_registry:
            self.notebook.select(self.registry_tab)

    def refresh_sections(self):
        active_id = self.state_data.get("activeSectionId")
        self.sections_list.delete(0, "end")
        active_index = 0
        for index, section in enumerate(self.state_data["sections"]):
            self.sections_list.insert("end", f"  {section['name']}   ·   {len(section['records'])}")
            if section["id"] == active_id:
                active_index = index
        self.sections_list.selection_set(active_index)

    def refresh_header(self):
        section = self.active_section()
        self.header_title.configure(text=section["name"])
        self.header_description.configure(text=section.get("description") or "Реєстр відкривається першим. Даблклік по запису відкриває картку.")

    def visible_fields(self):
        section = self.active_section()
        ids = section.get("visibleFieldIds") or [field["id"] for field in section["fields"]]
        fields = [field for field in section["fields"] if field["id"] in ids]
        return fields or section["fields"][:1]

    def refresh_records_table(self):
        section = self.active_section()
        fields = self.visible_fields()
        columns = [field["id"] for field in fields] + ["updatedAt"]
        self.records_tree.configure(columns=columns)
        for column in columns:
            field = next((item for item in fields if item["id"] == column), None)
            self.records_tree.heading(column, text=field["name"] if field else "Оновлено")
            self.records_tree.column(column, width=170, minwidth=110)
        self.records_tree.delete(*self.records_tree.get_children())
        for record in section["records"]:
            values = [self.format_value(record.get("values", {}).get(field["id"]), field["type"]) for field in fields]
            values.append(record.get("updatedAt", ""))
            self.records_tree.insert("", "end", iid=record["id"], values=values)

    def refresh_record_form(self):
        for child in self.record_form.winfo_children():
            child.destroy()
        self.record_widgets = {}
        section = self.active_section()
        record = self.find_record(self.editing_record_id)
        title = "Картка запису" if record else "Нова картка запису"
        tk.Label(self.record_form, text=title, bg="white", fg=COLORS["text"], font=("Segoe UI", 18, "bold")).grid(row=0, column=0, columnspan=2, sticky="w")
        tk.Label(
            self.record_form,
            text="Тут заповнюється запис. Нові поля можна додати прямо з картки.",
            bg="white",
            fg=COLORS["muted"],
            font=("Segoe UI", 10),
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(2, 14))
        self.record_form.columnconfigure(1, weight=1)

        for index, field in enumerate(section["fields"], start=2):
            label = f"{field['name']}{' *' if field.get('required') else ''}"
            tk.Label(self.record_form, text=label, bg="white", fg=COLORS["text"], font=("Segoe UI", 10, "bold")).grid(
                row=index, column=0, sticky="w", padx=(0, 12), pady=6
            )
            value = record.get("values", {}).get(field["id"], "") if record else ""
            widget = self.create_value_widget(self.record_form, field, value)
            widget.grid(row=index, column=1, sticky="ew", pady=6)
            self.record_widgets[field["id"]] = (field, widget)

        button_row = len(section["fields"]) + 3
        buttons = ttk.Frame(self.record_form, style="Card.TFrame")
        buttons.grid(row=button_row, column=0, columnspan=2, sticky="ew", pady=(16, 0))
        ttk.Button(buttons, text="Зберегти картку", style="Primary.TButton", command=self.save_record).pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="+ Додати поле", command=self.create_field).pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="Повернутися до реєстру", command=lambda: self.notebook.select(self.registry_tab)).pack(side="left", padx=(0, 8))
        if record:
            ttk.Button(buttons, text="Скасувати редагування", command=self.cancel_edit).pack(side="left")

    def refresh_fields_table(self):
        self.fields_tree.delete(*self.fields_tree.get_children())
        for field in self.active_section()["fields"]:
            self.fields_tree.insert(
                "",
                "end",
                iid=field["id"],
                values=(field["name"], FIELD_TYPES.get(field["type"], field["type"]), "Так" if field.get("required") else "Ні"),
            )

    def create_value_widget(self, parent, field, value):
        common = {"font": ("Segoe UI", 10), "relief": "flat", "highlightthickness": 1, "highlightbackground": COLORS["border"]}
        if field["type"] == "textarea":
            text = tk.Text(parent, height=4, width=48, **common)
            text.insert("1.0", str(value or ""))
            return text
        if field["type"] == "checkbox":
            variable = tk.BooleanVar(value=bool(value))
            checkbox = ttk.Checkbutton(parent, variable=variable)
            checkbox.variable = variable
            return checkbox
        entry = tk.Entry(parent, **common)
        entry.insert(0, str(value or ""))
        return entry

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

    def selected_record_id(self):
        selection = self.records_tree.selection()
        if not selection:
            return None
        return selection[0]

    def on_section_select(self, _event=None):
        selection = self.sections_list.curselection()
        if not selection:
            return
        selected = self.state_data["sections"][selection[0]]
        if selected["id"] != self.state_data.get("activeSectionId"):
            self.state_data["activeSectionId"] = selected["id"]
            self.editing_record_id = None
            self.persist(self.state_data, "Розділ відкрито", open_registry=True)

    def show_record_context_menu(self, event):
        row_id = self.records_tree.identify_row(event.y)
        if row_id:
            self.records_tree.selection_set(row_id)
            self.record_menu.tk_popup(event.x_root, event.y_root)

    def new_record(self):
        self.editing_record_id = None
        self.refresh_record_form()
        self.notebook.select(self.card_tab)

    def open_selected_record(self):
        record_id = self.selected_record_id()
        if not record_id:
            messagebox.showinfo("Запис", "Виберіть запис для відкриття")
            return
        self.editing_record_id = record_id
        self.refresh_record_form()
        self.notebook.select(self.card_tab)

    def copy_selected_record(self):
        record_id = self.selected_record_id()
        record = self.find_record(record_id)
        if not record:
            messagebox.showinfo("Запис", "Виберіть запис для копіювання")
            return
        self.editing_record_id = None
        self.persist(upsert_record(self.state_data, self.active_section()["id"], None, record.get("values", {})), "Запис скопійовано", open_registry=True)

    def delete_selected_record(self):
        record_id = self.selected_record_id()
        if not record_id:
            messagebox.showinfo("Запис", "Виберіть запис для видалення")
            return
        if messagebox.askyesno("Підтвердження", "Видалити вибраний запис?"):
            self.persist(remove_record(self.state_data, self.active_section()["id"], record_id), "Запис видалено", open_registry=True)

    def create_section(self):
        dialog = SectionDialog(self)
        if dialog.result:
            try:
                self.editing_record_id = None
                self.persist(add_section(self.state_data, dialog.result["name"], dialog.result["description"]), "Розділ створено", open_registry=True)
            except ValueError as error:
                messagebox.showerror("Помилка", str(error))

    def create_field(self):
        dialog = FieldDialog(self)
        if dialog.result:
            section = self.active_section()
            try:
                self.persist(add_field(self.state_data, section["id"], dialog.result["name"], dialog.result["type"], dialog.result["required"]), "Поле додано")
            except ValueError as error:
                messagebox.showerror("Помилка", str(error))

    def delete_selected_field(self):
        selection = self.fields_tree.selection()
        if not selection:
            messagebox.showinfo("Поле", "Виберіть поле для видалення")
            return
        if messagebox.askyesno("Підтвердження", "Видалити поле та його значення у всіх записах?"):
            self.persist(remove_field(self.state_data, self.active_section()["id"], selection[0]), "Поле видалено")

    def configure_columns(self):
        dialog = ColumnsDialog(self, self.active_section())
        if dialog.result is None:
            return
        self.active_section()["visibleFieldIds"] = dialog.result
        self.persist(self.state_data, "Колонки реєстру оновлено", open_registry=True)

    def save_record(self):
        try:
            was_editing = bool(self.editing_record_id)
            self.persist(
                upsert_record(self.state_data, self.active_section()["id"], self.editing_record_id, self.collect_record_values()),
                "Запис оновлено" if was_editing else "Запис створено",
                open_registry=True,
            )
            self.editing_record_id = None
        except ValueError as error:
            messagebox.showerror("Помилка", str(error))

    def cancel_edit(self):
        self.editing_record_id = None
        self.refresh_record_form()

    def export_json(self):
        path = filedialog.asksaveasfilename(title="Експорт CRM", defaultextension=".json", filetypes=(("JSON", "*.json"), ("Усі файли", "*.*")), initialfile="crm-in-pc-backup.json")
        if not path:
            return
        Path(path).write_text(json.dumps(self.state_data, ensure_ascii=False, indent=2), encoding="utf-8")
        self.status_var.set(f"Експортовано JSON: {path}")

    def import_json(self):
        path = filedialog.askopenfilename(title="Імпорт CRM", filetypes=(("JSON", "*.json"), ("Усі файли", "*.*")))
        if not path:
            return
        try:
            imported = json.loads(Path(path).read_text(encoding="utf-8"))
            self.editing_record_id = None
            self.persist(imported, "Дані імпортовано", open_registry=True)
        except (json.JSONDecodeError, OSError) as error:
            messagebox.showerror("Помилка імпорту", str(error))

    def export_excel(self):
        section = self.active_section()
        path = filedialog.asksaveasfilename(
            title="Експорт в Excel",
            defaultextension=".xlsx",
            filetypes=(("Excel workbook", "*.xlsx"), ("Усі файли", "*.*")),
            initialfile=f"{section['name']}.xlsx",
        )
        if not path:
            return
        export_section_to_xlsx(section, path)
        self.status_var.set(f"Експортовано Excel: {path}")

    def import_excel(self):
        path = filedialog.askopenfilename(title="Імпорт з Excel", filetypes=(("Excel workbook", "*.xlsx"), ("Усі файли", "*.*")))
        if not path:
            return
        try:
            values_rows = import_values_for_section(self.active_section(), path)
            next_state = self.state_data
            for values in values_rows:
                next_state = upsert_record(next_state, self.active_section()["id"], None, values)
            self.persist(next_state, f"Імпортовано записів з Excel: {len(values_rows)}", open_registry=True)
        except Exception as error:  # XLSX files can fail for many ZIP/XML reasons; show user-friendly error.
            messagebox.showerror("Помилка Excel", str(error))


def main():
    app = CRMDesktopApp()
    app.mainloop()


if __name__ == "__main__":
    main()
