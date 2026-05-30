import assert from 'node:assert/strict';
import test from 'node:test';
import {
  addField,
  addSection,
  createInitialState,
  removeField,
  removeRecord,
  upsertRecord,
} from '../src/storage.js';

test('creates a custom section and makes it active', () => {
  const state = createInitialState();
  const next = addSection(state, { name: 'Заявки', description: 'Вхідні звернення клієнтів' });

  assert.equal(next.sections.length, state.sections.length + 1);
  assert.equal(next.sections.at(-1).name, 'Заявки');
  assert.equal(next.activeSectionId, next.sections.at(-1).id);
});

test('adds a field to a section and backfills existing records', () => {
  const state = createInitialState();
  const next = addField(state, 'contacts', { name: 'VIP', type: 'checkbox', required: false });
  const addedField = next.sections.find((section) => section.id === 'contacts').fields.at(-1);
  const demoRecord = next.sections.find((section) => section.id === 'contacts').records[0];

  assert.equal(addedField.name, 'VIP');
  assert.equal(demoRecord.values[addedField.id], false);
});

test('creates, updates, and removes a record', () => {
  let state = createInitialState();
  state = upsertRecord(state, 'deals', null, {
    title: 'Впровадження CRM',
    amount: '15000',
    stage: 'Нова',
    closeDate: '2026-06-30',
  });

  const section = state.sections.find((item) => item.id === 'deals');
  const recordId = section.records[0].id;
  assert.equal(section.records.length, 1);

  state = upsertRecord(state, 'deals', recordId, {
    title: 'Впровадження CRM',
    amount: '18000',
    stage: 'У роботі',
    closeDate: '2026-07-15',
  });
  assert.equal(state.sections.find((item) => item.id === 'deals').records[0].values.amount, '18000');

  state = removeRecord(state, 'deals', recordId);
  assert.equal(state.sections.find((item) => item.id === 'deals').records.length, 0);
});

test('rejects records with missing required fields', () => {
  const state = createInitialState();

  assert.throws(
    () => upsertRecord(state, 'contacts', null, { fullName: '', phone: '', email: '', nextContact: '' }),
    /Заповніть обовʼязкові поля/,
  );
});

test('removes field values from existing records when schema field is deleted', () => {
  const state = createInitialState();
  const next = removeField(state, 'contacts', 'phone');
  const section = next.sections.find((item) => item.id === 'contacts');

  assert.equal(section.fields.some((field) => field.id === 'phone'), false);
  assert.equal('phone' in section.records[0].values, false);
});
