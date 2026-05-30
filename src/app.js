import {
  FIELD_TYPES,
  STORAGE_KEY,
  addField,
  addSection,
  defaultValueForType,
  loadState,
  removeField,
  removeRecord,
  saveState,
  upsertRecord,
} from './storage.js';

let state = loadState();
let editingRecordId = null;
let toastTimer = null;

const app = document.querySelector('#app');

const activeSection = () => state.sections.find((section) => section.id === state.activeSectionId) || state.sections[0];

const persist = (nextState, message = 'Зміни збережено') => {
  state = saveState(nextState);
  render();
  showToast(message);
};

const escapeHtml = (value) =>
  String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');

const showToast = (message, type = 'success') => {
  const toast = document.querySelector('[data-toast]');
  if (!toast) return;
  toast.textContent = message;
  toast.dataset.type = type;
  toast.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    toast.hidden = true;
  }, 3200);
};

const render = () => {
  const section = activeSection();

  app.innerHTML = `
    <aside class="sidebar">
      <div class="brand">
        <span class="brand__mark">CRM</span>
        <div>
          <strong>CRM in PC</strong>
          <small>Локальна база клієнтів</small>
        </div>
      </div>

      <button class="button button--primary button--full" data-action="open-section-modal">+ Новий розділ</button>

      <nav class="section-list" aria-label="Розділи CRM">
        ${state.sections
          .map(
            (item) => `
              <button class="section-list__item ${item.id === section?.id ? 'is-active' : ''}" data-action="select-section" data-section-id="${item.id}">
                <span>${escapeHtml(item.name)}</span>
                <small>${item.records.length} записів</small>
              </button>
            `,
          )
          .join('')}
      </nav>

      <div class="sidebar__footer">
        <button class="button button--ghost button--full" data-action="export-json">Експорт JSON</button>
        <label class="button button--ghost button--full file-input">
          Імпорт JSON
          <input type="file" accept="application/json" data-action="import-json" />
        </label>
      </div>
    </aside>

    <main class="workspace">
      <header class="hero">
        <div>
          <p class="eyebrow">Перший реліз</p>
          <h1>${escapeHtml(section?.name || 'Створіть перший розділ')}</h1>
          <p>${escapeHtml(section?.description || 'Створюйте розділи, додавайте власні поля та зберігайте записи прямо у браузері на цьому ПК.')}</p>
        </div>
        <div class="stats">
          <span><strong>${state.sections.length}</strong> розділів</span>
          <span><strong>${section?.fields.length || 0}</strong> полів</span>
          <span><strong>${section?.records.length || 0}</strong> записів</span>
        </div>
      </header>

      ${section ? renderSection(section) : renderEmptyState()}
    </main>

    <div class="toast" data-toast hidden></div>
    ${renderSectionModal()}
  `;

  bindEvents();
};

const renderEmptyState = () => `
  <section class="card empty-state">
    <h2>Почніть зі створення розділу</h2>
    <p>Наприклад: Контакти, Угоди, Товари, Заявки або будь-яка інша сутність вашого бізнесу.</p>
    <button class="button button--primary" data-action="open-section-modal">Створити розділ</button>
  </section>
`;

const renderSection = (section) => `
  <section class="grid">
    <form class="card form-card" data-record-form>
      <div class="card__header">
        <div>
          <h2>${editingRecordId ? 'Редагувати запис' : 'Новий запис'}</h2>
          <p>Дані автоматично зберігаються у localStorage цього браузера.</p>
        </div>
        ${editingRecordId ? '<button class="button button--ghost" type="button" data-action="cancel-edit">Скасувати</button>' : ''}
      </div>
      <div class="form-grid">
        ${section.fields.map((field) => renderFieldInput(field, getEditingValue(section, field))).join('')}
      </div>
      <button class="button button--primary" type="submit">${editingRecordId ? 'Оновити запис' : 'Зберегти запис'}</button>
    </form>

    <section class="card schema-card">
      <div class="card__header">
        <div>
          <h2>Поля розділу</h2>
          <p>Додавайте поля як у BAS/1C або Creatio: текст, числа, дати та прапорці.</p>
        </div>
      </div>
      <form class="field-form" data-field-form>
        <input name="name" placeholder="Назва поля" required />
        <select name="type">
          ${FIELD_TYPES.map((type) => `<option value="${type.value}">${type.label}</option>`).join('')}
        </select>
        <label class="checkbox"><input type="checkbox" name="required" /> Обовʼязкове</label>
        <button class="button" type="submit">Додати поле</button>
      </form>
      <ul class="field-list">
        ${section.fields
          .map(
            (field) => `
              <li>
                <span><strong>${escapeHtml(field.name)}</strong><small>${field.type}${field.required ? ' · обовʼязкове' : ''}</small></span>
                <button class="icon-button" title="Видалити поле" data-action="delete-field" data-field-id="${field.id}">×</button>
              </li>
            `,
          )
          .join('')}
      </ul>
    </section>
  </section>

  <section class="card records-card">
    <div class="card__header">
      <div>
        <h2>Записи</h2>
        <p>Таблиця показує збережені записи активного розділу.</p>
      </div>
    </div>
    ${renderRecordsTable(section)}
  </section>
`;

const getEditingValue = (section, field) => {
  const record = section.records.find((item) => item.id === editingRecordId);
  return record?.values[field.id] ?? defaultValueForType(field.type);
};

const renderFieldInput = (field, value) => {
  const common = `name="${field.id}" id="field-${field.id}" ${field.required ? 'required' : ''}`;
  const label = `<label for="field-${field.id}">${escapeHtml(field.name)}${field.required ? '<span>*</span>' : ''}</label>`;

  if (field.type === 'textarea') {
    return `<div class="form-control form-control--wide">${label}<textarea ${common}>${escapeHtml(value)}</textarea></div>`;
  }

  if (field.type === 'checkbox') {
    return `<div class="form-control form-control--checkbox"><label><input type="checkbox" name="${field.id}" ${value ? 'checked' : ''} /> ${escapeHtml(field.name)}</label></div>`;
  }

  return `<div class="form-control">${label}<input ${common} type="${field.type}" value="${escapeHtml(value)}" /></div>`;
};

const renderRecordsTable = (section) => {
  if (!section.records.length) {
    return '<div class="empty-table">Поки немає записів. Заповніть форму вище, щоб додати перший запис.</div>';
  }

  return `
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            ${section.fields.map((field) => `<th>${escapeHtml(field.name)}</th>`).join('')}
            <th>Оновлено</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          ${section.records
            .map(
              (record) => `
                <tr>
                  ${section.fields.map((field) => `<td>${formatValue(record.values[field.id], field.type)}</td>`).join('')}
                  <td>${new Date(record.updatedAt).toLocaleString('uk-UA')}</td>
                  <td class="table-actions">
                    <button class="button button--small" data-action="edit-record" data-record-id="${record.id}">Редагувати</button>
                    <button class="button button--small button--danger" data-action="delete-record" data-record-id="${record.id}">Видалити</button>
                  </td>
                </tr>
              `,
            )
            .join('')}
        </tbody>
      </table>
    </div>
  `;
};

const formatValue = (value, type) => {
  if (type === 'checkbox') return value ? 'Так' : 'Ні';
  if (value === undefined || value === '') return '<span class="muted">—</span>';
  return escapeHtml(value);
};

const renderSectionModal = () => `
  <dialog data-section-modal>
    <form method="dialog" class="modal" data-section-form>
      <h2>Новий розділ</h2>
      <label>Назва <input name="name" placeholder="Наприклад, Заявки" required /></label>
      <label>Опис <textarea name="description" placeholder="Що зберігаємо у цьому розділі?"></textarea></label>
      <div class="modal__actions">
        <button class="button button--ghost" value="cancel" type="button" data-action="close-section-modal">Скасувати</button>
        <button class="button button--primary" type="submit">Створити</button>
      </div>
    </form>
  </dialog>
`;

const bindEvents = () => {
  document.querySelectorAll('[data-action="select-section"]').forEach((button) => {
    button.addEventListener('click', () => {
      state.activeSectionId = button.dataset.sectionId;
      editingRecordId = null;
      persist(state, 'Розділ відкрито');
    });
  });

  document.querySelectorAll('[data-action="open-section-modal"]').forEach((button) => {
    button.addEventListener('click', () => document.querySelector('[data-section-modal]').showModal());
  });

  document.querySelector('[data-action="close-section-modal"]')?.addEventListener('click', () =>
    document.querySelector('[data-section-modal]').close(),
  );

  document.querySelector('[data-section-form]')?.addEventListener('submit', (event) => {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    try {
      persist(addSection(state, Object.fromEntries(formData)), 'Розділ створено');
      document.querySelector('[data-section-modal]').close();
    } catch (error) {
      showToast(error.message, 'error');
    }
  });

  document.querySelector('[data-field-form]')?.addEventListener('submit', (event) => {
    event.preventDefault();
    const section = activeSection();
    const formData = new FormData(event.currentTarget);
    try {
      persist(
        addField(state, section.id, {
          name: formData.get('name'),
          type: formData.get('type'),
          required: formData.get('required') === 'on',
        }),
        'Поле додано',
      );
    } catch (error) {
      showToast(error.message, 'error');
    }
  });

  document.querySelector('[data-record-form]')?.addEventListener('submit', (event) => {
    event.preventDefault();
    const section = activeSection();
    const formData = new FormData(event.currentTarget);
    const values = section.fields.reduce((acc, field) => {
      acc[field.id] = field.type === 'checkbox' ? formData.get(field.id) === 'on' : formData.get(field.id);
      return acc;
    }, {});

    try {
      persist(upsertRecord(state, section.id, editingRecordId, values), editingRecordId ? 'Запис оновлено' : 'Запис створено');
      editingRecordId = null;
      render();
    } catch (error) {
      showToast(error.message, 'error');
    }
  });

  document.querySelectorAll('[data-action="delete-field"]').forEach((button) => {
    button.addEventListener('click', () => {
      if (confirm('Видалити поле та значення цього поля у всіх записах?')) {
        persist(removeField(state, activeSection().id, button.dataset.fieldId), 'Поле видалено');
      }
    });
  });

  document.querySelectorAll('[data-action="edit-record"]').forEach((button) => {
    button.addEventListener('click', () => {
      editingRecordId = button.dataset.recordId;
      render();
      document.querySelector('[data-record-form]')?.scrollIntoView({ behavior: 'smooth' });
    });
  });

  document.querySelectorAll('[data-action="delete-record"]').forEach((button) => {
    button.addEventListener('click', () => {
      if (confirm('Видалити запис?')) {
        persist(removeRecord(state, activeSection().id, button.dataset.recordId), 'Запис видалено');
      }
    });
  });

  document.querySelector('[data-action="cancel-edit"]')?.addEventListener('click', () => {
    editingRecordId = null;
    render();
  });

  document.querySelector('[data-action="export-json"]')?.addEventListener('click', () => {
    const blob = new Blob([JSON.stringify(state, null, 2)], { type: 'application/json' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `crm-in-pc-${new Date().toISOString().slice(0, 10)}.json`;
    link.click();
    URL.revokeObjectURL(link.href);
  });

  document.querySelector('[data-action="import-json"]')?.addEventListener('change', async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    try {
      const imported = JSON.parse(await file.text());
      localStorage.setItem(STORAGE_KEY, JSON.stringify(imported));
      state = loadState();
      editingRecordId = null;
      render();
      showToast('Дані імпортовано');
    } catch {
      showToast('Не вдалося імпортувати JSON', 'error');
    }
  });
};

render();
