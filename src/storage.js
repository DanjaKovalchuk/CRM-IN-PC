export const STORAGE_KEY = 'crm-in-pc-data-v1';

export const FIELD_TYPES = [
  { value: 'text', label: 'Текст' },
  { value: 'number', label: 'Число' },
  { value: 'date', label: 'Дата' },
  { value: 'textarea', label: 'Багаторядковий текст' },
  { value: 'checkbox', label: 'Так / Ні' },
];

export const createId = (prefix = 'id') =>
  `${prefix}_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`;

export const createInitialState = () => ({
  version: 1,
  activeSectionId: 'contacts',
  sections: [
    {
      id: 'contacts',
      name: 'Контакти',
      description: 'Клієнти, партнери та відповідальні особи',
      fields: [
        { id: 'fullName', name: 'ПІБ', type: 'text', required: true },
        { id: 'phone', name: 'Телефон', type: 'text', required: false },
        { id: 'email', name: 'Email', type: 'text', required: false },
        { id: 'nextContact', name: 'Наступний контакт', type: 'date', required: false },
      ],
      records: [
        {
          id: 'contact_demo',
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
          values: {
            fullName: 'Іван Петренко',
            phone: '+38 067 000 00 00',
            email: 'ivan@example.com',
            nextContact: '',
          },
        },
      ],
    },
    {
      id: 'deals',
      name: 'Угоди',
      description: 'Продажі, статуси та суми потенційних контрактів',
      fields: [
        { id: 'title', name: 'Назва', type: 'text', required: true },
        { id: 'amount', name: 'Сума', type: 'number', required: false },
        { id: 'stage', name: 'Етап', type: 'text', required: false },
        { id: 'closeDate', name: 'Дата закриття', type: 'date', required: false },
      ],
      records: [],
    },
  ],
});

export const cloneState = (state) => JSON.parse(JSON.stringify(state));

export const ensureStateShape = (state) => {
  const fallback = createInitialState();
  if (!state || !Array.isArray(state.sections)) return fallback;

  const sections = state.sections.map((section) => ({
    id: section.id || createId('section'),
    name: section.name || 'Новий розділ',
    description: section.description || '',
    fields: Array.isArray(section.fields) ? section.fields : [],
    records: Array.isArray(section.records) ? section.records : [],
  }));

  return {
    version: 1,
    activeSectionId: sections.some((section) => section.id === state.activeSectionId)
      ? state.activeSectionId
      : sections[0]?.id || null,
    sections,
  };
};

export const loadState = (storage = window.localStorage) => {
  try {
    const raw = storage.getItem(STORAGE_KEY);
    return raw ? ensureStateShape(JSON.parse(raw)) : createInitialState();
  } catch {
    return createInitialState();
  }
};

export const saveState = (state, storage = window.localStorage) => {
  storage.setItem(STORAGE_KEY, JSON.stringify(state));
  return state;
};

export const addSection = (state, { name, description = '' }) => {
  const trimmedName = name.trim();
  if (!trimmedName) throw new Error('Назва розділу обовʼязкова');

  const next = cloneState(state);
  const section = {
    id: createId('section'),
    name: trimmedName,
    description: description.trim(),
    fields: [{ id: createId('field'), name: 'Назва', type: 'text', required: true }],
    records: [],
  };
  next.sections.push(section);
  next.activeSectionId = section.id;
  return next;
};

export const addField = (state, sectionId, field) => {
  const trimmedName = field.name.trim();
  if (!trimmedName) throw new Error('Назва поля обовʼязкова');
  if (!FIELD_TYPES.some(({ value }) => value === field.type)) throw new Error('Невідомий тип поля');

  const next = cloneState(state);
  const section = next.sections.find((item) => item.id === sectionId);
  if (!section) throw new Error('Розділ не знайдено');

  const newField = {
    id: createId('field'),
    name: trimmedName,
    type: field.type,
    required: Boolean(field.required),
  };
  section.fields.push(newField);
  section.records = section.records.map((record) => ({
    ...record,
    values: { ...record.values, [newField.id]: defaultValueForType(newField.type) },
  }));
  return next;
};

export const removeField = (state, sectionId, fieldId) => {
  const next = cloneState(state);
  const section = next.sections.find((item) => item.id === sectionId);
  if (!section) throw new Error('Розділ не знайдено');
  section.fields = section.fields.filter((field) => field.id !== fieldId);
  section.records = section.records.map((record) => {
    const values = { ...record.values };
    delete values[fieldId];
    return { ...record, values };
  });
  return next;
};

export const defaultValueForType = (type) => (type === 'checkbox' ? false : '');

export const validateRecord = (section, values) => {
  const missing = section.fields.filter((field) => field.required && !String(values[field.id] ?? '').trim());
  if (missing.length) throw new Error(`Заповніть обовʼязкові поля: ${missing.map((field) => field.name).join(', ')}`);
};

export const upsertRecord = (state, sectionId, recordId, values) => {
  const next = cloneState(state);
  const section = next.sections.find((item) => item.id === sectionId);
  if (!section) throw new Error('Розділ не знайдено');

  validateRecord(section, values);
  const now = new Date().toISOString();
  const normalizedValues = section.fields.reduce((acc, field) => {
    acc[field.id] = values[field.id] ?? defaultValueForType(field.type);
    return acc;
  }, {});

  if (recordId) {
    const record = section.records.find((item) => item.id === recordId);
    if (!record) throw new Error('Запис не знайдено');
    record.values = normalizedValues;
    record.updatedAt = now;
  } else {
    section.records.unshift({ id: createId('record'), createdAt: now, updatedAt: now, values: normalizedValues });
  }

  return next;
};

export const removeRecord = (state, sectionId, recordId) => {
  const next = cloneState(state);
  const section = next.sections.find((item) => item.id === sectionId);
  if (!section) throw new Error('Розділ не знайдено');
  section.records = section.records.filter((record) => record.id !== recordId);
  return next;
};
