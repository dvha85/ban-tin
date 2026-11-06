'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const helpers = require('../newsroom/static/draft-state.js');

// Exercise the real save function with a fake DOM and API, not a browser smoke test.
function setup(confirmResult, stubCollect = true) {
  const elements = new Map();
  const get = id => {
    if (!elements.has(id)) elements.set(id, {
      value: '', hidden: false, classList: {toggle() {}}, addEventListener() {}, removeAttribute() {},
    });
    return elements.get(id);
  };
  const calls = [];
  const context = vm.createContext({...helpers, URL, URLSearchParams, Date, Intl, Promise,
    setTimeout, clearTimeout, structuredClone, calls,
    fetch: () => new Promise(() => {}),
    window: {location: {search: ''}, addEventListener() {}, confirm: message => {
      calls.push(['confirm', message]); return confirmResult;
    }},
    document: {getElementById: get, querySelectorAll: () => [], querySelector: () => get('query'),
      createElement: () => get('created'), createTextNode: text => text},
  });
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../newsroom/static/app.js'), 'utf8'), context);
  vm.runInContext(`app.draft = {id: 7, revision: 4, status: 'approved'}; app.dirty = true;
    api = async (url, payload) => { calls.push(['api', url, payload.revision]); return {id: 7, revision: 5, status: 'draft'}; };
    setDraft = async draft => { bindPublicationFields(app.draft, draft, $('post-url'), $('published-link')); app.draft = draft; app.dirty = false; };
    loadState = async () => {}; toast = () => {};`, context);
  if (stubCollect) vm.runInContext('collectDraft = () => ({revision: app.draft.revision})', context);
  get('post-url').value = 'https://www.facebook.com/page/posts/111';
  return {context, get, calls};
}

test('canceling save warning preserves pending URL and does not save', async () => {
  const {context, get, calls} = setup(false);
  await vm.runInContext('saveDraft()', context);
  assert.equal(calls.length, 1);
  assert.match(calls[0][1], /URL/);
  assert.equal(get('post-url').value, 'https://www.facebook.com/page/posts/111');
  assert.equal(vm.runInContext('app.draft.status', context), 'approved');
  assert.equal(vm.runInContext('app.dirty', context), true);
});

test('accepting warning saves once and clears URL when approval is revoked', async () => {
  const {context, get, calls} = setup(true);
  await vm.runInContext('saveDraft()', context);
  assert.equal(calls.length, 2);
  assert.equal(calls[1][1], '/api/drafts/7/save');
  assert.equal(calls[1][2], 4);
  assert.equal(get('post-url').value, '');
  assert.equal(vm.runInContext('app.draft.status', context), 'draft');
});

test('failed save retains URL and approval after warning', async () => {
  const {context, get} = setup(true);
  vm.runInContext("api = async () => { throw new Error('save failed'); }", context);
  await assert.rejects(vm.runInContext('saveDraft()', context), /save failed/);
  assert.equal(get('post-url').value, 'https://www.facebook.com/page/posts/111');
  assert.equal(vm.runInContext('app.draft.status', context), 'approved');
  assert.equal(vm.runInContext('app.busy', context), false);
});

test('saving unchanged legacy fields preserves original line endings and source evidence', () => {
  const {context, get} = setup(true, false);
  const original = {id: 7, revision: 4, status: 'approved', page_name: 'Trang\r\nA', category: 'tools',
    title: 'Tiêu\r\nđề', body: 'Một\r\nHai\rBa', angle: 'Góc\r\nnhìn',
    sources: [{title: 'Nguồn\r\nA', url: 'https://example.com/a', summary: 'Ghi\r\nchú\rnguồn',
      collection_method: 'test', excerpt_hash: 'original'}]};
  context.original = original;
  vm.runInContext('app.draft = structuredClone(original)', context);
  get('field-page').value = 'TrangA'; get('field-category').value = 'tools';
  get('field-title').value = 'Tiêuđề'; get('field-body').value = 'Một\nHai\nBa';
  get('field-angle').value = 'Góc\nnhìn';
  const fields = {title: {value: 'NguồnA'}, url: {value: 'https://example.com/a'}, summary: {value: 'Ghi\nchú\nnguồn'}};
  get('source-fields').children = [{sourceRecord: original.sources[0],
    querySelector: selector => fields[selector.match(/"([^"]+)"/)[1]]}];
  const result = vm.runInContext('collectDraft()', context);
  assert.equal(result.page_name, original.page_name); assert.equal(result.title, original.title);
  assert.equal(result.body, original.body); assert.equal(result.angle, original.angle);
  assert.equal(result.sources[0].title, original.sources[0].title);
  assert.equal(result.sources[0].summary, original.sources[0].summary);
  assert.equal(result.sources[0].excerpt_hash, 'original');
  get('field-body').value = 'Đã sửa\nHai'; fields.summary.value = 'Ghi chú mới';
  const edited = vm.runInContext('collectDraft()', context);
  assert.equal(edited.body, 'Đã sửa\nHai'); assert.equal(edited.sources[0].summary, 'Ghi chú mới');
});
