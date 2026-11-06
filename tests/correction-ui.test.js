'use strict';
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const helpers = require('../newsroom/static/draft-state.js');

// Minimal DOM harness for the real event handlers. Browser behavior still needs smoke testing.
class Element {
  constructor(tag = 'div') {
    this.tagName = tag; this.children = []; this.dataset = {}; this.listeners = {};
    this.classList = {toggle() {}}; this.inert = false; this.isConnected = true;
    this.value = ''; this.textContent = ''; this.disabled = false;
  }
  append(...children) { for (const child of children) if (child instanceof Element) child.parentElement = this; this.children.push(...children); }
  remove() { if (this.parentElement) this.parentElement.children = this.parentElement.children.filter(child => child !== this); this.isConnected = false; }
  replaceChildren(...children) { this.children = children; }
  addEventListener(name, listener) { (this.listeners[name] ||= []).push(listener); }
  dispatchEvent(event) { for (const listener of this.listeners[event.type] || []) listener(event); }
  setAttribute(name, value) { this[name] = value; }
  focus() { this.focused = true; }
  querySelectorAll(selector) {
    const rows = [];
    const visit = element => {
      if (!(element instanceof Element)) return;
      if (selector === '[data-dirty="true"]' && element.dataset.dirty === 'true') rows.push(element);
      if (selector === '[data-pending-correction="true"]' && element.dataset.pendingCorrection === 'true') rows.push(element);
      if (selector === '[data-pending-publication-edit="true"]' && element.dataset.pendingPublicationEdit === 'true') rows.push(element);
      if (selector === '[data-publication-url]' && element.dataset.publicationUrl) rows.push(element);
      if (selector === '.bulletin-item, .variant-editor' && /\b(bulletin-item|variant-editor)\b/.test(element.className || '')) rows.push(element);
      element.children.forEach(visit);
    };
    this.children.forEach(visit); return rows;
  }
  querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
}

test('manual import displays errors in the dialog and distinguishes a saved import from refresh failure', async () => {
  const elements = new Map();
  const get = id => { if (!elements.has(id)) elements.set(id, new Element()); return elements.get(id); };
  const messages = [];
  let response = 'invalid', resets = 0, closes = 0;
  get('import-form').reset = () => { resets++; };
  get('import-dialog').close = () => { closes++; };
  get('import-dialog').showModal = () => {};
  const context = vm.createContext({...helpers, URL, URLSearchParams, Intl, Date, Error, Promise, setTimeout, clearTimeout,
    Event: class { constructor(type) { this.type = type; } }, messages, mode: () => response,
    fetch: () => new Promise(() => {}), sourceWarnings: () => [],
    window: {location: {search: ''}, addEventListener() {}},
    document: {getElementById: get, querySelectorAll: () => [], querySelector: () => new Element(),
      createElement: tag => new Element(tag), createTextNode: text => text}});
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../newsroom/static/app.js'), 'utf8'), context);
  vm.runInContext(`toast = message => messages.push(message); view = () => {};
    api = async () => { if (mode() !== 'saved') { const error = new Error('Liên kết không hợp lệ');
      error.outcomeUnknown = mode() === 'unknown'; throw error; } return {id: 42}; };
    loadState = async () => { throw new Error('Không tải được'); };`, context);
  get('import-url').value = 'https://@example.com/story';
  get('import-title').value = 'Tin thử';
  get('import-summary').value = 'Ghi chú thử';
  const submit = async () => { get('import-form').dispatchEvent({type: 'submit', preventDefault() {}});
    await new Promise(resolve => setImmediate(resolve)); };
  await submit();
  assert.equal(get('import-error').hidden, false);
  assert.match(get('import-error').textContent, /không hợp lệ/);
  assert.equal(get('import-url').value, 'https://@example.com/story');
  assert.equal(get('import-title').value, 'Tin thử');
  assert.equal(resets, 0); assert.equal(closes, 0);
  response = 'unknown'; await submit();
  assert.match(get('import-error').textContent, /chưa rõ.*kiểm tra/i);
  assert.equal(resets, 0); assert.equal(closes, 0);
  response = 'saved'; await submit();
  assert.equal(resets, 1); assert.equal(closes, 1);
  assert.match(messages.at(-1), /đã.*lưu.*chưa tải lại/i);
  assert.equal(vm.runInContext('app.articleId', context), 42);
});

test('packet copy rejects stale or changed editor state and copies matching snapshot', async () => {
  const elements = new Map();
  const get = id => { if (!elements.has(id)) elements.set(id, new Element()); return elements.get(id); };
  const copies = [];
  const context = vm.createContext({...helpers, URL, URLSearchParams, Intl, Date, Error, Promise,
    setTimeout, clearTimeout, copies, fetch: () => new Promise(() => {}),
    window: {location: {search: ''}, addEventListener() {}},
    document: {getElementById: get, querySelectorAll: () => [], querySelector: () => new Element(),
      createElement: tag => new Element(tag), createTextNode: text => text}});
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../newsroom/static/app.js'), 'utf8'), context);
  vm.runInContext(`app.bulletin = {id: 7, revision: 4};
    copy = async text => copies.push(text);
    api = async () => ({text: 'Gói mới', bulletin_revision: 5});`, context);
  await assert.rejects(vm.runInContext('copyBulletinPacket(app.bulletin)', context), /bản tin.*thay đổi/i);
  assert.equal(copies.length, 0);
  vm.runInContext(`api = async () => ({text: 'Không rõ revision'});`, context);
  await assert.rejects(vm.runInContext('copyBulletinPacket(app.bulletin)', context), /bản tin.*thay đổi/i);
  vm.runInContext(`api = async () => { app.bulletinDirty = true; return {text: 'Gói cũ', bulletin_revision: 4}; }`, context);
  await assert.rejects(vm.runInContext('copyBulletinPacket(app.bulletin)', context), /thay đổi/i);
  vm.runInContext(`app.bulletinDirty = false;
    api = async () => { app.bulletin = {id: 8, revision: 4}; return {text: 'Gói cũ', bulletin_revision: 4}; }`, context);
  await assert.rejects(vm.runInContext('copyBulletinPacket(app.bulletin)', context), /thay đổi/i);
  vm.runInContext(`app.bulletin = {id: 7, revision: 4};
    api = async () => { app.storeChanged = true; return {text: 'Gói cũ', bulletin_revision: 4}; }`, context);
  await assert.rejects(vm.runInContext('copyBulletinPacket(app.bulletin)', context), /thay đổi/i);
  assert.equal(copies.length, 0);
  vm.runInContext(`app.storeChanged = false; api = async () => ({text: 'Gói đúng', bulletin_revision: 4});`, context);
  await vm.runInContext('copyBulletinPacket(app.bulletin)', context);
  assert.deepEqual(copies, ['Gói đúng']);
});

test('variant actions carry the displayed bulletin revision', async () => {
  const elements = new Map();
  const get = id => { if (!elements.has(id)) elements.set(id, new Element()); return elements.get(id); };
  const calls = [], messages = [];
  const context = vm.createContext({...helpers, URL, URLSearchParams, Intl, Date, Error, Promise,
    setTimeout, clearTimeout, calls, messages, fetch: () => new Promise(() => {}),
    window: {location: {search: ''}, addEventListener() {}},
    document: {getElementById: get, querySelectorAll: () => [], querySelector: () => new Element(),
      createElement: tag => new Element(tag), createTextNode: text => text}});
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../newsroom/static/app.js'), 'utf8'), context);
  context.container = new Element();
  vm.runInContext(`app.variantId = 3;
    api = async (path, data) => {
      if (path.endsWith('/variants')) return [{id: 3, revision: 2, platform: 'x', account_label: 'Kênh thử', status: 'draft',
        locked_at: null, needs_update: false, policy_stale: false, checks: {},
        segments: [{text: 'Tin giả', item_ids: [1], source_ids: ['source-1']}]}];
      calls.push({path, data}); throw new Error('Bản tin đã thay đổi');
    }; toast = message => messages.push(message);`, context);
  context.bulletin = {id: 7, revision: 4, items: [{id: 1, title: 'Tin giả', sources: [{source_id: 'source-1', url: 'https://example.com/a'}]}]};
  await vm.runInContext('renderVariants(container, bulletin)', context);
  const walk = el => [el, ...el.children.filter(child => child instanceof Element).flatMap(walk)];
  const all = walk(context.container);
  for (const name of ['Đề xuất chia đoạn', 'Duyệt phiên bản', 'Tạo bản sao']) {
    const button = all.find(el => el.tagName === 'button' && el.textContent === name);
    button.dispatchEvent({type: 'click'}); await new Promise(resolve => setImmediate(resolve));
    assert.equal(calls.at(-1).data.expected_bulletin_revision, 4, name);
  }
  assert.equal(calls.length, 3);
});

test('variant save includes the displayed bulletin revision and keeps text on conflict', async () => {
  const elements = new Map();
  const get = id => { if (!elements.has(id)) elements.set(id, new Element()); return elements.get(id); };
  const calls = [], messages = [];
  const context = vm.createContext({...helpers, URL, URLSearchParams, Intl, Date, Error, Promise,
    setTimeout, clearTimeout, calls, messages, fetch: () => new Promise(() => {}),
    window: {location: {search: ''}, addEventListener() {}},
    document: {getElementById: get, querySelectorAll: () => [], querySelector: () => new Element(),
      createElement: tag => new Element(tag), createTextNode: text => text}});
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../newsroom/static/app.js'), 'utf8'), context);
  context.container = new Element();
  vm.runInContext(`app.variantId = 3;
    api = async (path, data) => {
      if (path.endsWith('/variants')) return [{id: 3, revision: 2, platform: 'x', account_label: 'Kênh thử', status: 'draft',
        locked_at: null, needs_update: true, policy_stale: false, checks: {},
        segments: [{text: 'Tin giả', item_ids: [1], source_ids: ['source-1']}]}];
      calls.push({path, data}); throw new Error('Bản tin đã thay đổi');
    }; toast = message => messages.push(message);`, context);
  context.bulletin = {id: 7, revision: 4, items: [{id: 1, title: 'Tin giả', sources: [{source_id: 'source-1', url: 'https://example.com/a'}]}]};
  await vm.runInContext('renderVariants(container, bulletin)', context);
  const walk = el => [el, ...el.children.filter(child => child instanceof Element).flatMap(walk)];
  const all = walk(context.container);
  const text = all.find(el => el.tagName === 'textarea'); text.value = 'Nội dung đang soạn';
  const save = all.find(el => el.tagName === 'button' && el.textContent === 'Lưu phiên bản');
  save.dispatchEvent({type: 'click'}); await new Promise(resolve => setImmediate(resolve));
  assert.equal(calls.length, 1);
  assert.equal(calls[0].data.expected_bulletin_revision, 4);
  assert.equal(calls[0].data.segments[0].text, 'Nội dung đang soạn');
  assert.equal(text.value, 'Nội dung đang soạn');
  assert.match(messages.at(-1), /bản tin đã thay đổi/i);
});

test('saving a variant restores keyboard focus without stealing focus moved during the request', async () => {
  const elements = new Map();
  const get = id => { if (!elements.has(id)) elements.set(id, new Element()); return elements.get(id); };
  const body = new Element('body');
  const document = {body, activeElement: body, getElementById: get, querySelectorAll: () => [],
    querySelector: () => new Element(), createElement: tag => new Element(tag), createTextNode: text => text};
  const context = vm.createContext({...helpers, URL, URLSearchParams, Intl, Date, Error, Promise,
    setTimeout, clearTimeout, fetch: () => new Promise(() => {}), document,
    window: {location: {search: ''}, addEventListener() {}}});
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../newsroom/static/app.js'), 'utf8'), context);
  context.bulletin = {id: 7, revision: 4, items: [{id: 1, title: 'Tin giả',
    sources: [{source_id: 'source-1', url: 'https://example.com/a'}]}]};
  vm.runInContext(`app.view = 'bulletins'; app.bulletin = bulletin; app.variantId = 3;
    api = async path => path.endsWith('/variants') ? [{id: 3, revision: 2, platform: 'x', account_label: 'Kênh thử',
      status: 'draft', locked_at: null, needs_update: false, policy_stale: false, checks: {},
      segments: [{text: 'Tin giả', item_ids: [1], source_ids: ['source-1']}]}] : {id: 3};
    renderBulletin = async () => {}; toast = () => {};`, context);
  const walk = el => [el, ...el.children.filter(child => child instanceof Element).flatMap(walk)];
  const run = async moveFocus => {
    context.container = new Element();
    await vm.runInContext('renderVariants(container, bulletin)', context);
    const save = walk(context.container).find(el => el.tagName === 'button' && el.textContent === 'Lưu phiên bản');
    document.activeElement = save;
    let finish;
    context.saved = new Promise(resolve => { finish = resolve; });
    vm.runInContext(`api = async path => path.endsWith('/variants') ? [] : saved;`, context);
    save.dispatchEvent({type: 'click'});
    await new Promise(resolve => setImmediate(resolve));
    document.activeElement = moveFocus ? new Element('button') : body;
    finish({id: 3});
    await new Promise(resolve => setImmediate(resolve));
    return get('variant-save').focused === true;
  };
  assert.equal(await run(false), true);
  get('variant-save').focused = false;
  vm.runInContext(`api = async path => [{id: 3, revision: 2, platform: 'x', account_label: 'Kênh thử',
    status: 'draft', locked_at: null, needs_update: false, policy_stale: false, checks: {},
    segments: [{text: 'Tin giả', item_ids: [1], source_ids: ['source-1']}]}];`, context);
  assert.equal(await run(true), false);
});

test('variant save unlocks while the refreshed variant list is delayed', async () => {
  const elements = new Map();
  const get = id => { if (!elements.has(id)) elements.set(id, new Element()); return elements.get(id); };
  const body = new Element('body');
  const document = {body, activeElement: body, getElementById: get, querySelectorAll: () => [],
    querySelector: () => new Element(), createElement: tag => new Element(tag), createTextNode: text => text};
  const context = vm.createContext({...helpers, URL, URLSearchParams, Intl, Date, Error, Promise,
    setTimeout, clearTimeout, fetch: () => new Promise(() => {}), document,
    window: {location: {search: ''}, addEventListener() {}}});
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../newsroom/static/app.js'), 'utf8'), context);
  context.bulletin = {id: 7, revision: 4, items: [{id: 1, title: 'Tin giả',
    sources: [{source_id: 'source-1', url: 'https://example.com/a'}]}]};
  vm.runInContext(`app.view = 'bulletins'; app.bulletin = bulletin; app.variantId = 3;
    api = async path => path.endsWith('/variants') ? [{id: 3, revision: 2, platform: 'x', account_label: 'Kênh thử',
      status: 'draft', locked_at: null, needs_update: false, policy_stale: false, checks: {},
      segments: [{text: 'Tin giả', item_ids: [1], source_ids: ['source-1']}]}] : {id: 3};
    renderBulletin = () => refreshed; toast = () => {};`, context);
  const walk = el => [el, ...el.children.filter(child => child instanceof Element).flatMap(walk)];
  const run = async moveFocus => {
    context.container = new Element();
    await vm.runInContext('renderVariants(container, bulletin)', context);
    const save = walk(context.container).find(el => el.tagName === 'button' && el.textContent === 'Lưu phiên bản');
    document.activeElement = save;
    let finish;
    context.refreshed = new Promise(resolve => { finish = resolve; });
    save.dispatchEvent({type: 'click'});
    await new Promise(resolve => setImmediate(resolve));
    document.activeElement = moveFocus ? new Element('button') : body;
    assert.equal(vm.runInContext('app.busy', context), false);
    assert.equal(get('bulletin-editor').inert, false);
    assert.notEqual(get('variant-save').focused, true);
    finish();
    await new Promise(resolve => setImmediate(resolve));
    return get('variant-save').focused === true;
  };
  assert.equal(await run(false), true);
  get('variant-save').focused = false;
  assert.equal(await run(true), false);
});

test('removing an edited segment requires confirmation and preserves it on cancel or later edits', async () => {
  const elements = new Map();
  const get = id => { if (!elements.has(id)) elements.set(id, new Element()); return elements.get(id); };
  const messages = [];
  const context = vm.createContext({...helpers, URL, URLSearchParams, Intl, Date, Error, Promise,
    setTimeout, clearTimeout, messages, fetch: () => new Promise(() => {}),
    window: {location: {search: ''}, addEventListener() {}},
    document: {getElementById: get, querySelectorAll: () => [], querySelector: () => new Element(),
      createElement: tag => new Element(tag), createTextNode: text => text}});
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../newsroom/static/app.js'), 'utf8'), context);
  context.container = new Element();
  vm.runInContext(`app.variantId = 3;
    api = async () => [{id: 3, revision: 1, platform: 'x', account_label: 'Kênh thử', status: 'draft',
      locked_at: null, needs_update: false, policy_stale: false, checks: {},
      segments: [{text: 'Đoạn đầu', item_ids: [1], source_ids: ['source-1']},
                 {text: 'Đoạn hai', item_ids: [1], source_ids: ['source-1']}]}];
    toast = message => messages.push(message);`, context);
  context.bulletin = {id: 7, items: [{id: 1, title: 'Tin giả', sources: [{source_id: 'source-1', url: 'https://example.com/a'}]}]};
  await vm.runInContext('renderVariants(container, bulletin)', context);
  const walk = el => [el, ...el.children.filter(child => child instanceof Element).flatMap(walk)];
  const all = () => walk(context.container);
  const button = name => all().find(el => el.tagName === 'button' && el.textContent === name);
  const click = async el => { assert.ok(el); el.dispatchEvent({type: 'click'}); await new Promise(resolve => setImmediate(resolve)); };
  const firstText = all().find(el => el.tagName === 'textarea' && el.value === 'Đoạn đầu');
  firstText.value = 'Đoạn đầu chưa lưu';
  await click(button('Bỏ đoạn'));
  let confirm = button('Xác nhận bỏ đoạn'), cancel = button('Hủy bỏ đoạn');
  assert.ok(confirm && cancel); assert.equal(confirm.parentElement.hidden, false);
  assert.equal(firstText.value, 'Đoạn đầu chưa lưu');
  await click(cancel);
  assert.equal(confirm.parentElement.hidden, true); assert.equal(firstText.value, 'Đoạn đầu chưa lưu');
  await click(button('Bỏ đoạn'));
  firstText.value = 'Đoạn vừa sửa tiếp';
  await click(confirm);
  assert.ok(all().includes(firstText)); assert.match(messages.at(-1), /đã thay đổi/i);
  await click(button('Bỏ đoạn'));
  const firstSource = all().find(el => el.tagName === 'label' && el.children.includes('https://example.com/a'))
    .children.find(el => el instanceof Element && el.type === 'checkbox');
  firstSource.checked = false;
  await click(confirm);
  assert.ok(all().includes(firstText)); assert.match(messages.at(-1), /đã thay đổi/i);
  await click(button('Bỏ đoạn'));
  await click(confirm);
  assert.ok(!all().includes(firstText));
  assert.ok(all().some(el => el.tagName === 'textarea' && el.value === 'Đoạn hai'));
  assert.equal(vm.runInContext('app.bulletinDirty', context), true);
});

test('source picker requires one to three checked sources and supports cancellation', async () => {
  const elements = new Map();
  const get = id => { if (!elements.has(id)) elements.set(id, new Element()); return elements.get(id); };
  const body = new Element('body');
  const make = tag => {
    const el = new Element(tag);
    el.showModal = () => { el.open = true; };
    el.close = () => { el.open = false; el.dispatchEvent({type: 'close'}); };
    el.remove = () => { body.children = body.children.filter(child => child !== el); };
    return el;
  };
  const context = vm.createContext({...helpers, URL, URLSearchParams, Intl, Date, Error, Promise, setTimeout, clearTimeout,
    fetch: () => new Promise(() => {}), window: {location: {search: ''}, addEventListener() {},
      prompt() { throw new Error('Unexpected native prompt'); }},
    document: {body, getElementById: get, querySelectorAll: () => [], querySelector: () => new Element(),
      createElement: make, createTextNode: text => text}});
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../newsroom/static/app.js'), 'utf8'), context);
  context.article = {title: 'Tin thử', sources: [1, 2, 3, 4].map(i => ({source_name: `Nguồn ${i}`, url: `https://example.com/${i}`}))};
  const walk = el => [el, ...el.children.filter(child => child instanceof Element).flatMap(walk)];
  assert.equal(await vm.runInContext('chooseBulletinSources({...article, sources: article.sources.slice(0, 3)})', context), undefined);
  let pending = vm.runInContext('chooseBulletinSources(article)', context);
  let dialog = body.children[0];
  assert.ok(dialog && dialog.open);
  let all = walk(dialog), checks = all.filter(el => el.tagName === 'input' && el.type === 'checkbox');
  assert.ok(all.some(el => el.textContent.includes('cho “Tin thử”')));
  assert.equal(checks.length, 4);
  const confirm = all.find(el => el.tagName === 'button' && el.textContent === 'Chọn nguồn');
  confirm.dispatchEvent({type: 'click'});
  assert.ok(all.some(el => el.role === 'alert' && el.textContent));
  checks.forEach(el => { el.checked = true; });
  confirm.dispatchEvent({type: 'click'});
  assert.equal(dialog.open, true);
  checks[1].checked = false;
  confirm.dispatchEvent({type: 'click'});
  assert.deepEqual(Array.from(await pending), ['https://example.com/1', 'https://example.com/3', 'https://example.com/4']);
  assert.equal(body.children.length, 0);
  pending = vm.runInContext('chooseBulletinSources(article)', context);
  dialog = body.children[0]; dialog.close();
  assert.equal(await pending, null);
  assert.equal(body.children.length, 0);
  pending = vm.runInContext("chooseBulletinSources({...article, id: 8, title: ''})", context);
  dialog = body.children[0];
  assert.ok(walk(dialog).some(el => el.textContent.includes('Bài #8 (chưa đặt tiêu đề)')));
  dialog.close();
  assert.equal(await pending, null);
});

test('source selection is awaited by create, add, and legacy copy actions', async () => {
  const elements = new Map();
  const get = id => { if (!elements.has(id)) elements.set(id, new Element()); return elements.get(id); };
  const calls = [], errors = [];
  const context = vm.createContext({...helpers, URL, URLSearchParams, Intl, Date, Error, Promise, setTimeout, clearTimeout,
    calls, errors, fetch: () => new Promise(() => {}),
    window: {location: {search: ''}, addEventListener() {}, confirm: () => true},
    document: {getElementById: get, querySelectorAll: () => [], querySelector: () => new Element(),
      createElement: tag => new Element(tag), createTextNode: text => text}});
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../newsroom/static/app.js'), 'utf8'), context);
  vm.runInContext(`app.state = {articles: [{id: 11, title: 'Tin A', sources: []}, {id: 12, title: 'Tin B', sources: []}], bulletin_usage: {}};
    app.selectedArticles = new Set([11, 12]);
    app.draft = {id: 8, revision: 3, sources: []};
    toast = message => errors.push(message); loadState = async () => {}; loadBulletinList = async () => {};
    view = () => {}; renderVariants = async () => {};
    api = async (path, body) => { calls.push({path, body});
      if (path.includes('copy-bulletin')) return {bulletin: null, variant_id: 1};
      return {id: 7, revision: 4, items: []}; };
    choices = []; chooseBulletinSources = () => new Promise(resolve => choices.push(resolve));`, context);
  const tick = () => new Promise(resolve => setImmediate(resolve));
  const click = async el => { el.dispatchEvent({type: 'click'}); await tick(); };
  const resolveChoice = async value => { context.choices.shift()(value); await tick(); };
  await click(get('create-bulletin'));
  assert.equal(vm.runInContext('app.busy', context), true);
  await resolveChoice(['https://example.com/1']);
  assert.equal(calls.length, 0);
  await resolveChoice(null);
  assert.equal(calls.length, 0);
  assert.equal(vm.runInContext('app.busy', context), false);
  assert.equal(vm.runInContext('app.selectedArticles.size', context), 2);
  await click(get('create-bulletin'));
  await resolveChoice(['https://example.com/1']);
  await resolveChoice(['https://example.com/2']);
  assert.deepEqual(JSON.parse(JSON.stringify(calls[0].body.source_selection)), {'11': ['https://example.com/1'], '12': ['https://example.com/2']});
  vm.runInContext(`app.bulletin = {id: 7, revision: 4, title: 'Bản thử', edition_date: '', introduction: '', conclusion: '', items: []}; renderBulletin();`, context);
  const walk = el => [el, ...el.children.filter(child => child instanceof Element).flatMap(walk)];
  const all = walk(get('bulletin-editor'));
  const select = all.find(el => el.tagName === 'select' && el['aria-label'] === 'Tin muốn thêm vào bản tin');
  select.value = '11';
  const add = all.find(el => el.tagName === 'button' && el.textContent === 'Thêm tin vào bản tin');
  await click(add); await resolveChoice(['https://example.com/3']);
  assert.deepEqual(JSON.parse(JSON.stringify(calls[1].body)), {revision: 4, article_id: 11, source_selection: ['https://example.com/3']});
  await click(get('copy-legacy-bulletin'));
  vm.runInContext('app.draft = {id: 99, revision: 10, sources: []}', context);
  await resolveChoice(['https://example.com/4']);
  assert.equal(calls[2].path, '/api/drafts/8/copy-bulletin');
  assert.deepEqual(JSON.parse(JSON.stringify(calls[2].body)), {revision: 3, source_selection: ['https://example.com/4']});
  assert.equal(vm.runInContext('app.busy', context), false);
  assert.ok(!errors.some(message => /Unexpected|error/i.test(message)));
});

test('removing a source or item requires an in-page confirmation and rechecks pending changes', async () => {
  const elements = new Map();
  const get = id => { if (!elements.has(id)) elements.set(id, new Element()); return elements.get(id); };
  const calls = [], messages = [];
  let outcomeUnknown = false, listFails = false;
  const context = vm.createContext({...helpers, URL, URLSearchParams, Intl, Date, Error, Promise, setTimeout, clearTimeout,
    Event: class { constructor(type) { this.type = type; } }, calls, messages, outcomeUnknown: () => outcomeUnknown, listFails: () => listFails,
    fetch: () => new Promise(() => {}), sourceWarnings: () => [],
    window: {location: {search: ''}, addEventListener() {}, confirm() { throw new Error('Unexpected native confirm'); }},
    document: {getElementById: get, querySelectorAll: () => [], querySelector: () => new Element(),
      createElement: tag => new Element(tag), createTextNode: text => text}});
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../newsroom/static/app.js'), 'utf8'), context);
  vm.runInContext(`app.state = {articles: [], bulletin_usage: {}};
    const source = (id, url) => ({source_id: id, url, title: id, date_kind: 'unknown'});
    const item = (id, sources) => ({id, article_id: id, revision: 2, title: 'Mục ' + id, body: '', angle: '',
      verification_note: '', verified: false, claims: [], sources});
    app.bulletin = {id: 7, revision: 4, title: 'Bản thử', edition_date: '2026-11-04', introduction: '', conclusion: '',
      items: [item(5, [source('a', 'https://example.com/a'), source('b', 'https://example.com/b')]),
              item(6, [source('c', 'https://example.com/c')])]};
    toast = message => messages.push(message); loadBulletinList = async () => { if (listFails()) throw new Error('list'); }; renderVariants = async () => {};
    loadState = async () => {}; renderStories = () => {};
    api = async (path, body) => { calls.push({path, body}); if (outcomeUnknown()) {
      const error = new Error('Mất kết nối'); error.outcomeUnknown = true; throw error; } return app.bulletin; };
    renderBulletin();`, context);
  const walk = el => [el, ...el.children.filter(child => child instanceof Element).flatMap(walk)];
  const find = (root, text) => walk(root).find(el => el.tagName === 'button' && el.textContent === text);
  const click = async el => { assert.ok(el); el.dispatchEvent({type: 'click'}); await new Promise(resolve => setImmediate(resolve)); };
  let editor = get('bulletin-editor');
  assert.equal(find(editor, 'Bỏ nguồn này')['aria-label'], 'Bỏ nguồn https://example.com/a khỏi mục Mục 5');
  await click(find(editor, 'Bỏ nguồn này'));
  let confirm = find(editor, 'Xác nhận bỏ nguồn'), cancel = find(editor, 'Hủy bỏ nguồn');
  assert.ok(confirm && cancel); assert.equal(confirm.focused, true); assert.equal(calls.length, 0);
  await click(cancel); assert.equal(calls.length, 0);
  await click(find(editor, 'Bỏ nguồn này'));
  vm.runInContext('app.bulletinDirty = true', context);
  await click(confirm); assert.equal(calls.length, 0); assert.match(messages.at(-1), /lưu/i);
  vm.runInContext('app.bulletinDirty = false', context);
  vm.runInContext('hasPendingPublicationEdit = () => true', context);
  await click(confirm); assert.equal(calls.length, 0); assert.match(messages.at(-1), /lưu/i);
  vm.runInContext('hasPendingPublicationEdit = () => false; app.bulletin.revision = 5', context);
  await click(confirm); assert.equal(calls.length, 0); assert.match(messages.at(-1), /đã thay đổi/i);
  vm.runInContext('app.bulletin.revision = 4', context);
  await click(find(editor, 'Bỏ nguồn này'));
  outcomeUnknown = true; await click(confirm);
  assert.equal(calls.length, 1); assert.match(messages.at(-1), /chưa rõ/i);
  assert.deepEqual(JSON.parse(JSON.stringify(calls[0].body)), {bulletin_revision: 4, revision: 2, remove_source_id: 'a'});
  outcomeUnknown = false; listFails = true;
  await click(confirm); assert.equal(calls.length, 2); assert.match(messages.at(-1), /Đã bỏ nguồn.*chưa tải lại/i);
  editor = get('bulletin-editor'); listFails = false;
  await click(find(editor, 'Bỏ mục khỏi bản tin'));
  confirm = find(editor, 'Xác nhận bỏ mục'); cancel = find(editor, 'Hủy bỏ mục');
  assert.ok(confirm && cancel); await click(cancel); assert.equal(calls.length, 2);
  await click(find(editor, 'Bỏ mục khỏi bản tin')); await click(confirm);
  assert.deepEqual(JSON.parse(JSON.stringify(calls[2].body)), {revision: 4, remove_item_id: 5});
  vm.runInContext("app.bulletin.items[0].title = ''; renderBulletin();", context);
  editor = get('bulletin-editor');
  const unnamedSource = find(editor, 'Bỏ nguồn này');
  const unnamedItem = find(editor, 'Bỏ mục khỏi bản tin');
  assert.match(unnamedSource['aria-label'], /#5 \(chưa đặt tiêu đề\)/);
  assert.match(unnamedItem['aria-label'], /#5 \(chưa đặt tiêu đề\)/);
  assert.ok(walk(editor).some(el => /Di chuyển mục 1 #5 \(chưa đặt tiêu đề\) xuống/.test(el['aria-label'] || '')));
  assert.ok(walk(editor).some(el => /Bỏ nguồn .*#5 \(chưa đặt tiêu đề\)/.test(el.textContent)));
  assert.ok(walk(editor).some(el => /Bỏ mục .*#5 \(chưa đặt tiêu đề\)/.test(el.textContent)));
});

test('removing an item refreshes usage and reports a failed refresh without hiding the saved removal', async () => {
  const elements = new Map();
  const get = id => { if (!elements.has(id)) elements.set(id, new Element()); return elements.get(id); };
  const messages = [];
  let refreshFails = false;
  const context = vm.createContext({...helpers, URL, URLSearchParams, Intl, Date, Error, Promise, setTimeout, clearTimeout,
    Event: class { constructor(type) { this.type = type; } }, messages, refreshFails: () => refreshFails,
    fetch: () => new Promise(() => {}), sourceWarnings: () => [],
    window: {location: {search: ''}, addEventListener() {}},
    document: {getElementById: get, querySelectorAll: () => [], querySelector: () => new Element(),
      createElement: tag => new Element(tag), createTextNode: text => text}});
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../newsroom/static/app.js'), 'utf8'), context);
  vm.runInContext(`const item = id => ({id, article_id: id, revision: 1, title: 'Mục ' + id, body: '', angle: '',
      verification_note: '', verified: false, claims: [], sources: [{source_id: 's' + id, url: 'https://example.com/' + id}]});
    app.state = {articles: [{id: 5, title: 'Tin 5'}, {id: 6, title: 'Tin 6'}], bulletin_usage: {5: 1, 6: 2}};
    app.bulletin = {id: 7, revision: 4, title: 'Bản thử', edition_date: '', introduction: '', conclusion: '', items: [item(5), item(6)]};
    toast = message => messages.push(message); renderVariants = async () => {}; renderStories = () => {};
    loadBulletinList = async () => {};
    loadState = async () => { if (refreshFails()) throw new Error('offline'); app.state.bulletin_usage = {5: 0, 6: 2}; };
    api = async () => ({...app.bulletin, revision: 5, items: [item(6)]}); renderBulletin();`, context);
  const walk = el => [el, ...el.children.filter(child => child instanceof Element).flatMap(walk)];
  const find = text => walk(get('bulletin-editor')).find(el => el.tagName === 'button' && el.textContent === text);
  const click = async el => { assert.ok(el); el.dispatchEvent({type: 'click'}); await new Promise(resolve => setImmediate(resolve)); };
  await click(find('Bỏ mục khỏi bản tin')); await click(find('Xác nhận bỏ mục'));
  let option = walk(get('bulletin-editor')).find(el => el.tagName === 'option' && el.value === 5);
  assert.equal(option.textContent, 'Tin 5');
  assert.match(messages.at(-1), /Đã bỏ mục/);
  vm.runInContext(`app.state.bulletin_usage[5] = 2; app.bulletin = {id: 7, revision: 4, title: 'Bản thử',
    edition_date: '', introduction: '', conclusion: '', items: [item(5), item(6)]}; renderBulletin();`, context);
  refreshFails = true;
  await click(find('Bỏ mục khỏi bản tin')); await click(find('Xác nhận bỏ mục'));
  option = walk(get('bulletin-editor')).find(el => el.tagName === 'option' && el.value === 5);
  assert.match(option.textContent, /đã dùng trong 1 bản tin/);
  assert.match(messages.at(-1), /Đã bỏ mục.*chưa tải lại.*sử dụng/i);
  assert.equal(vm.runInContext('app.bulletin.items.length', context), 1);
});

test('confirmed source and item removals restore keyboard focus without stealing it', async () => {
  const elements = new Map();
  const walk = el => [el, ...el.children.filter(child => child instanceof Element).flatMap(walk)];
  const get = id => {
    const existing = elements.get('bulletin-editor');
    const match = existing && walk(existing).find(el => el.id === id);
    if (match) return match;
    if (!elements.has(id)) elements.set(id, new Element());
    return elements.get(id);
  };
  const body = new Element('body'), elsewhere = new Element('button');
  const document = {body, activeElement: body, getElementById: get, querySelectorAll: () => [],
    querySelector: () => new Element(), createElement: tag => new Element(tag), createTextNode: text => text};
  let moveFocus = false;
  const context = vm.createContext({...helpers, URL, URLSearchParams, Intl, Date, Error, Promise, setTimeout, clearTimeout,
    Event: class { constructor(type) { this.type = type; } }, document, moveFocus: () => moveFocus, elsewhere,
    fetch: () => new Promise(() => {}), sourceWarnings: () => [],
    window: {location: {search: ''}, addEventListener() {}}});
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../newsroom/static/app.js'), 'utf8'), context);
  vm.runInContext(`const item = id => ({id, article_id: id, revision: 1, title: 'Mục ' + id, body: '', angle: '',
      verification_note: '', verified: false, claims: [], sources: [{source_id: 's' + id, url: 'https://example.com/' + id},
      {source_id: 'shared', url: 'https://example.com/shared'}]});
    app.view = 'bulletins'; app.state = {articles: [], bulletin_usage: {5: 1, 6: 1}};
    app.bulletin = {id: 7, revision: 4, title: 'Bản thử', edition_date: '', introduction: '', conclusion: '', items: [item(5), item(6)]};
    toast = () => {}; renderVariants = async () => {}; renderStories = () => {}; loadState = async () => {};
    loadBulletinList = async () => {};
    api = async path => { document.activeElement = moveFocus() ? elsewhere : document.body;
      if (path.endsWith('/save')) return {...app.bulletin, revision: 5, items: [{...item(5), sources: [item(5).sources[1]]}, item(6)]};
      return {...app.bulletin, revision: 6, items: [item(6)]}; };
    renderBulletin();`, context);
  const find = text => walk(get('bulletin-editor')).find(el => el.tagName === 'button' && el.textContent === text);
  const click = async el => { assert.ok(el); el.dispatchEvent({type: 'click'}); await new Promise(resolve => setImmediate(resolve)); };
  await click(find('Bỏ nguồn này'));
  let confirm = find('Xác nhận bỏ nguồn'); document.activeElement = confirm;
  await click(confirm);
  let heading = walk(get('bulletin-editor')).find(el => el.id === 'bulletin-item-heading-5');
  assert.ok(heading && heading.focused); assert.equal(heading.tabIndex, -1);
  await click(find('Bỏ mục khỏi bản tin'));
  confirm = find('Xác nhận bỏ mục'); document.activeElement = confirm; moveFocus = true;
  await click(confirm);
  heading = walk(get('bulletin-editor')).find(el => el.id === 'bulletin-item-heading-6');
  assert.ok(heading); assert.notEqual(heading.focused, true);
  assert.equal(document.activeElement, elsewhere);
  vm.runInContext(`app.bulletin = {id: 7, revision: 4, title: 'Bản thử', edition_date: '', introduction: '', conclusion: '',
    items: [item(5), item(6)]}; renderBulletin();`, context);
  moveFocus = false;
  await click(find('Bỏ mục khỏi bản tin'));
  confirm = find('Xác nhận bỏ mục'); document.activeElement = confirm;
  await click(confirm);
  heading = walk(get('bulletin-editor')).find(el => el.id === 'bulletin-item-heading-6');
  assert.ok(heading && heading.focused);
});

test('inline source form keeps pending fields, blocks unrelated saves, and retains failed input', async () => {
  const elements = new Map();
  const get = id => { if (!elements.has(id)) elements.set(id, new Element()); return elements.get(id); };
  const calls = [], messages = [];
  let fail = true, unknown = false, listFails = false;
  const context = vm.createContext({...helpers, URL, URLSearchParams, Intl, Date, Error, Promise,
    Event: class { constructor(type) { this.type = type; } },
    setTimeout, clearTimeout, fetch: () => new Promise(() => {}), calls, messages,
    sourceWarnings: () => [], shouldFail: () => fail, isUnknown: () => unknown, shouldFailList: () => listFails,
    window: {location: {search: ''}, addEventListener() {}, prompt() { throw new Error('Unexpected browser prompt'); }},
    document: {getElementById: get, querySelectorAll: () => [], querySelector: () => new Element(),
      createElement: tag => new Element(tag), createTextNode: text => text}});
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../newsroom/static/app.js'), 'utf8'), context);
  vm.runInContext(`app.state = {articles: [], bulletin_usage: {}};
    app.bulletin = {id: 7, revision: 4, title: 'Bản thử', edition_date: '2026-11-04', introduction: '', conclusion: '',
      items: [{id: 5, article_id: 1, revision: 2, title: 'Mục thử', body: '', angle: '', verification_note: '',
        verified: false, claims: [], sources: [{source_id: 'source1', url: 'https://example.com/a',
          title: 'Nguồn A', published_at: null, retrieved_at: null, date_kind: 'unknown'}]}]};
    toast = message => messages.push(message);
    api = async (path, body) => {
      if (path === '/api/bulletins/7/variants') return [];
      if (path === '/api/bulletins/7/items/5/save') {
        calls.push({path, body});
        if (shouldFail()) { const error = new Error('Không lưu được nguồn'); error.outcomeUnknown = isUnknown(); throw error; }
        return {...app.bulletin, revision: 5};
      }
      if (path === '/api/bulletins') { if (shouldFailList()) throw new Error('Không tải được danh sách'); return []; }
      if (path === '/api/bulletin-stats') return {bulletins: 1, variants: 0, recorded_bulletins: 0, recorded_posts: 0};
      if (path === '/api/legacy-publication-duplicates') return [];
      throw new Error('Unexpected API ' + path);
    }; renderBulletin();`, context);
  const walk = el => [el, ...el.children.filter(child => child instanceof Element).flatMap(walk)];
  const find = (tag, text) => walk(get('bulletin-editor')).find(el => el.tagName === tag && el.textContent === text);
  const input = label => find('label', label)?.children.find(el => el instanceof Element);
  const click = async label => { find('button', label).listeners.click[0]({}); await new Promise(resolve => setImmediate(resolve)); };
  await click('Bổ sung nguồn');
  assert.ok(input('Liên kết nguồn HTTPS'));
  assert.equal(input('Liên kết nguồn HTTPS').focused, true);
  const section = walk(get('bulletin-editor')).find(el => /\bbulletin-item\b/.test(el.className || ''));
  const url = input('Liên kết nguồn HTTPS'), title = input('Tiêu đề nguồn'), note = input('Ghi chú về nguồn');
  url.value = 'https://example.com/b'; title.value = 'Nguồn B'; note.value = 'Ghi chú thử';
  section.listeners.input[0]({target: url});
  assert.equal(vm.runInContext('app.bulletinDirty', context), true);
  await click('Lưu mục');
  assert.equal(calls.length, 0); assert.match(messages.at(-1), /nguồn/i);
  await click('Xác nhận thêm nguồn');
  assert.equal(calls.length, 1); assert.match(messages.at(-1), /Không lưu được nguồn/);
  assert.equal(url.value, 'https://example.com/b'); assert.equal(note.value, 'Ghi chú thử');
  assert.equal(vm.runInContext('app.bulletinDirty', context), true);
  unknown = true;
  await click('Xác nhận thêm nguồn');
  assert.equal(calls.length, 2); assert.match(messages.at(-1), /chưa rõ.*thẻ khác/i);
  assert.equal(url.value, 'https://example.com/b');
  const itemTitle = walk(section).find(el => el.tagName === 'label' && el.textContent === 'Tiêu đề').children[0];
  itemTitle.value = 'Mục sửa dở'; section.listeners.input[0]({target: itemTitle});
  await click('Xác nhận thêm nguồn');
  assert.equal(calls.length, 2); assert.match(messages.at(-1), /phần khác/i);
  await click('Hủy thêm nguồn');
  assert.equal(vm.runInContext('app.bulletinDirty', context), true);
  assert.equal(itemTitle.value, 'Mục sửa dở');
  assert.equal(url.value, ''); assert.equal(title.value, ''); assert.equal(note.value, '');
  itemTitle.value = 'Mục thử'; section.listeners.input[0]({target: itemTitle});
  assert.equal(vm.runInContext('app.bulletinDirty', context), false);
  await click('Bổ sung nguồn');
  url.value = 'https://example.com/b'; title.value = 'Nguồn B'; note.value = 'Ghi chú thử';
  section.listeners.input[0]({target: url});
  fail = false; listFails = true;
  await click('Xác nhận thêm nguồn');
  assert.deepEqual(JSON.parse(JSON.stringify(calls[2].body)), {bulletin_revision: 4, revision: 2,
    add_source: {url: 'https://example.com/b', title: 'Nguồn B', summary: 'Ghi chú thử'}});
  assert.equal(vm.runInContext('app.bulletinDirty', context), false);
  assert.match(messages.at(-1), /Đã thêm nguồn.*chưa tải lại/i);
});

test('session recovery preserves the editor and never retries a mutation automatically', async () => {
  const elements = new Map();
  const get = id => { if (!elements.has(id)) elements.set(id, new Element()); return elements.get(id); };
  const calls = [];
  const context = vm.createContext({...helpers, URL, URLSearchParams, Intl, Date, Error, Promise, setTimeout, clearTimeout,
    fetch: () => new Promise(() => {}), window: {location: {search: ''}, addEventListener() {}},
    document: {getElementById: get, querySelectorAll: () => [], querySelector: () => new Element(),
      createElement: tag => new Element(tag), createTextNode: text => text}});
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../newsroom/static/app.js'), 'utf8'), context);
  context.calls = calls;
  vm.runInContext(`app.state = {data_dir: 'fixture'};
    fetch = async () => ({ok: false, status: 401, headers: {get: () => 'application/json'},
      json: async () => ({error: 'Phiên hết hạn'})});`, context);
  get('session-recovery').hidden = true;
  await assert.rejects(vm.runInContext("api('/api/state')", context), /Phiên hết hạn/);
  assert.equal(get('session-recovery').hidden, false);
  vm.runInContext(`app.state = {data_dir: 'fixture'}; app.csrf = 'old'; app.bulletinDirty = true;
    fetch = async (url, options) => { calls.push([url, options.method]);
      if (url === '/') return {ok: true};
      return {ok: true, headers: {get: () => 'application/json'}, json: async () => ({data_dir: 'fixture', csrf_token: 'new'})}; };`, context);
  get('field-title').value = 'Nội dung chưa lưu';
  await vm.runInContext('recoverSession()', context);
  assert.equal(get('field-title').value, 'Nội dung chưa lưu');
  assert.equal(vm.runInContext('app.bulletinDirty', context), true);
  assert.equal(vm.runInContext('app.csrf', context), 'new');
  assert.deepEqual(calls.map(row => row[0]), ['/', '/api/state']);
  assert.ok(calls.every(row => row[1] !== 'POST'));
  vm.runInContext(`fetch = async url => url === '/' ? {ok: true} :
    {ok: true, headers: {get: () => 'application/json'}, json: async () => ({data_dir: 'other', csrf_token: 'bad'})}`, context);
  await assert.rejects(vm.runInContext('recoverSession()', context), /kho dữ liệu/i);
  assert.equal(vm.runInContext('app.csrf', context), 'new');
});

test('periodic refresh cannot silently switch the open editor to another data directory', async () => {
  const elements = new Map();
  const get = id => { if (!elements.has(id)) elements.set(id, new Element()); return elements.get(id); };
  const calls = [];
  const context = vm.createContext({...helpers, URL, URLSearchParams, Intl, Date, Error, Promise, setTimeout, clearTimeout,
    requestJson: JSON.stringify, fetch: () => new Promise(() => {}),
    window: {location: {search: ''}, addEventListener() {}},
    document: {getElementById: get, querySelectorAll: () => [], querySelector: () => new Element(),
      createElement: tag => new Element(tag), createTextNode: text => text}});
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../newsroom/static/app.js'), 'utf8'), context);
  context.calls = calls;
  vm.runInContext(`app.state = {data_dir: 'original'}; app.csrf = 'original-token'; app.bulletinDirty = true;
    fetch = async (url, opts) => { calls.push([url, opts.method]); return {ok: true,
      headers: {get: () => 'application/json'}, json: async () => ({data_dir: 'different', csrf_token: 'different-token'})}; };`, context);
  get('field-title').value = 'Giữ nguyên';
  await assert.rejects(vm.runInContext('loadState()', context), /kho dữ liệu/i);
  assert.equal(vm.runInContext('app.state.data_dir', context), 'original');
  assert.equal(vm.runInContext('app.csrf', context), 'original-token');
  assert.equal(get('field-title').value, 'Giữ nguyên');
  assert.equal(get('store-changed-warning').hidden, false);
  assert.equal(get('recover-session').hidden, true);
  await assert.rejects(vm.runInContext("api('/api/bulletins/1/save', {})", context), /kho dữ liệu/i);
  assert.equal(calls.filter(row => row[1] === 'POST').length, 0);
});

test('late session recovery cannot clear a concurrently detected data directory change', async () => {
  const elements = new Map();
  const get = id => { if (!elements.has(id)) elements.set(id, new Element()); return elements.get(id); };
  let release;
  const delayed = new Promise(resolve => { release = resolve; });
  const context = vm.createContext({...helpers, URL, URLSearchParams, Intl, Date, Error, Promise, setTimeout, clearTimeout,
    fetch: () => new Promise(() => {}), window: {location: {search: ''}, addEventListener() {}},
    document: {getElementById: get, querySelectorAll: () => [], querySelector: () => new Element(),
      createElement: tag => new Element(tag), createTextNode: text => text}});
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../newsroom/static/app.js'), 'utf8'), context);
  context.delayed = delayed;
  vm.runInContext(`app.state = {data_dir: 'original'}; app.csrf = 'old';
    fetch = async url => url === '/' ? {ok: true} : {ok: true, json: () => delayed};`, context);
  const recovery = vm.runInContext('recoverSession()', context);
  vm.runInContext('markStoreChanged()', context);
  release({data_dir: 'original', csrf_token: 'late-token'});
  await assert.rejects(recovery, /kho dữ liệu/i);
  assert.equal(vm.runInContext('app.csrf', context), 'old');
  assert.equal(get('session-recovery').hidden, false);
  assert.equal(get('store-changed-warning').hidden, false);
  assert.equal(get('recover-session').hidden, true);
});

test('late state refresh cannot replace the editor state after a directory change', async () => {
  const elements = new Map();
  const get = id => { if (!elements.has(id)) elements.set(id, new Element()); return elements.get(id); };
  let release;
  const delayed = new Promise(resolve => { release = resolve; });
  const context = vm.createContext({...helpers, URL, URLSearchParams, Intl, Date, Error, Promise, setTimeout, clearTimeout,
    fetch: () => new Promise(() => {}), window: {location: {search: ''}, addEventListener() {}},
    document: {getElementById: get, querySelectorAll: () => [], querySelector: () => new Element(),
      createElement: tag => new Element(tag), createTextNode: text => text}});
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../newsroom/static/app.js'), 'utf8'), context);
  context.delayed = delayed;
  vm.runInContext(`app.state = {data_dir: 'original'}; app.csrf = 'old'; api = async () => delayed;`, context);
  const refresh = vm.runInContext('loadState()', context);
  vm.runInContext('markStoreChanged()', context);
  release({data_dir: 'original', csrf_token: 'late-token'});
  await assert.rejects(refresh, /kho dữ liệu/i);
  assert.equal(vm.runInContext('app.csrf', context), 'old');
  assert.equal(get('session-recovery').hidden, false);
});

test('variant dirty tracking ignores publication and metric fields but tracks edits', () => {
  const elements = new Map();
  const get = id => { if (!elements.has(id)) elements.set(id, new Element()); return elements.get(id); };
  const context = vm.createContext({...helpers, URL, URLSearchParams, Intl, Date, Error, Promise,
    setTimeout, clearTimeout, fetch: () => new Promise(() => {}),
    window: {location: {search: ''}, addEventListener() {}},
    document: {getElementById: get, querySelectorAll: () => [], querySelector: () => new Element(),
      createElement: tag => new Element(tag), createTextNode: text => text}});
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../newsroom/static/app.js'), 'utf8'), context);
  context.area = new Element();
  vm.runInContext("markVariantDirty(area, {target: {dataset: {metricField: 'views'}}})", context);
  vm.runInContext("markVariantDirty(area, {target: {dataset: {publicationUrl: 'true'}}})", context);
  vm.runInContext("markVariantDirty(area, {target: {dataset: {correctionField: 'reason'}}})", context);
  assert.notEqual(context.area.dataset.dirty, 'true');
  vm.runInContext('markVariantDirty(area, {target: {dataset: {}}})', context);
  assert.equal(context.area.dataset.dirty, 'true');
  assert.equal(vm.runInContext('app.bulletinDirty', context), true);
});

test('publication URL fields have a distinct accessible label for each segment', async () => {
  const elements = new Map();
  const get = id => { if (!elements.has(id)) elements.set(id, new Element()); return elements.get(id); };
  const context = vm.createContext({...helpers, URL, URLSearchParams, Intl, Date, Error, Promise, setTimeout, clearTimeout,
    fetch: () => new Promise(() => {}), crypto: {randomUUID: () => 'test-key'},
    window: {location: {search: ''}, addEventListener() {}},
    document: {getElementById: get, querySelectorAll: () => [], querySelector: () => new Element(),
      createElement: tag => new Element(tag), createTextNode: text => text}});
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../newsroom/static/app.js'), 'utf8'), context);
  vm.runInContext("api = async path => path.endsWith('/publications') ? [] : {posts: ['một', 'hai']};", context);
  const area = new Element(); get('bulletin-editor').append(area); context.area = area;
  await vm.runInContext("renderVariantPublication(area, {id: 3, revision: 4, platform: 'x', account_label: 'Thử'})", context);
  const walk = el => [el, ...el.children.filter(child => child instanceof Element).flatMap(walk)];
  const inputs = walk(area).filter(el => el.dataset.publicationUrl);
  assert.equal(inputs.length, 2);
  assert.deepEqual(inputs.map(input => input['aria-label']), ['Liên kết bài đã đăng cho đoạn 1', 'Liên kết bài đã đăng cho đoạn 2']);
});


test('historical export guidance distinguishes unlocked and locked variants', async () => {
  const elements = new Map();
  const get = id => { if (!elements.has(id)) elements.set(id, new Element()); return elements.get(id); };
  const context = vm.createContext({...helpers, URL, URLSearchParams, Intl, Date, Error, Promise, setTimeout, clearTimeout,
    fetch: () => new Promise(() => {}), crypto: {randomUUID: () => 'test-key'},
    window: {location: {search: ''}, addEventListener() {}},
    document: {getElementById: get, querySelectorAll: () => [], querySelector: () => new Element(),
      createElement: tag => new Element(tag), createTextNode: text => text}});
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../newsroom/static/app.js'), 'utf8'), context);
  vm.runInContext(`api = async path => {
    if (path.endsWith('/export')) throw new Error('stale policy');
    if (path.endsWith('/archive')) return {posts: ['historical']};
    if (path.endsWith('/publications')) return [];
    throw new Error('Unexpected path');
  };`, context);
  const walk = el => [el, ...el.children.filter(child => child instanceof Element).flatMap(walk)];
  for (const [lockedAt, expected, unexpected] of [
    [null, 'lưu và duyệt lại phiên bản này', 'tạo bản sao'],
    ['2026-11-04T00:00:00Z', 'tạo bản sao', 'lưu và duyệt lại phiên bản này'],
  ]) {
    context.area = new Element();
    context.variant = {id: 3, revision: 4, platform: 'x', account_label: 'Thử', locked_at: lockedAt};
    await vm.runInContext('renderVariantPublication(area, variant)', context);
    const message = walk(context.area).find(el => el.className === 'notice warning');
    assert.ok(message);
    assert.ok(message.textContent.includes(expected), message.textContent);
    assert.ok(!message.textContent.includes(unexpected), message.textContent);
    assert.ok(!walk(context.area).some(el => el.textContent.includes('Tải bản đã duyệt')));
    assert.ok(!walk(context.area).some(el => el.tagName === 'button' && el.textContent.includes('Sao chép đoạn')));
  }
});

test('download verifies the displayed approval and all posts and blocks unsaved changes', async () => {
  const elements = new Map(), saved = [], messages = [];
  const get = id => { if (!elements.has(id)) elements.set(id, new Element()); return elements.get(id); };
  class TestURL extends URL {}
  TestURL.createObjectURL = blob => { saved.push({blob}); return 'blob:fixture'; };
  TestURL.revokeObjectURL = () => {};
  const context = vm.createContext({...helpers, URL: TestURL, URLSearchParams, Intl, Date, Error, Promise, Blob,
    setTimeout: (fn, ms) => ms === 30000 ? 0 : setTimeout(fn, ms), clearTimeout,
    saved, messages, fetch: () => new Promise(() => {}),
    window: {location: {search: ''}, addEventListener() {}},
    document: {getElementById: get, querySelectorAll: () => [], querySelector: () => new Element(),
      createElement: tag => { const el = new Element(tag); el.click = () => { saved.at(-1).filename = el.download; }; return el; },
      createTextNode: text => text}});
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../newsroom/static/app.js'), 'utf8'), context);
  vm.runInContext(`let current = {approval_id: 21, posts: ['Một\\nnguồn', 'Hai']}, failExport = false;
    api = async path => { if (path.endsWith('/publications')) return []; if (failExport) throw new Error('không còn duyệt'); return structuredClone(current); };
    toast = message => messages.push(message);`, Object.assign(context, {structuredClone}));
  context.area = new Element();
  await vm.runInContext("renderVariantPublication(area, {id: 3, revision: 4, platform: 'x', account_label: 'Thử'})", context);
  const walk = el => [el, ...el.children.filter(child => child instanceof Element).flatMap(walk)];
  const button = walk(context.area).find(el => el.textContent === 'Tải bản đã duyệt (.txt)');
  assert.equal(button.tagName, 'button');
  const click = async () => { button.dispatchEvent({type: 'click'}); await new Promise(resolve => setImmediate(resolve)); };
  vm.runInContext('app.bulletinDirty = true', context);
  await click(); assert.equal(saved.length, 0); assert.match(messages.at(-1), /lưu/i);
  vm.runInContext('app.bulletinDirty = false; current.approval_id = 22', context);
  await click(); assert.equal(saved.length, 0); assert.match(messages.at(-1), /thay đổi/i);
  vm.runInContext('current.approval_id = 21; app.storeChanged = true', context);
  await click(); assert.equal(saved.length, 0); assert.match(messages.at(-1), /Kho dữ liệu/);
  vm.runInContext('app.storeChanged = false; failExport = true', context);
  await click(); assert.equal(saved.length, 0); assert.match(messages.at(-1), /không còn duyệt/);
  vm.runInContext('failExport = false', context);
  vm.runInContext("current.approval_id = 21; current.posts[1] = 'khác'", context);
  await click(); assert.equal(saved.length, 0);
  vm.runInContext("current.posts = ['Một\\nnguồn', 'Hai', 'thêm']", context);
  await click(); assert.equal(saved.length, 0);
  vm.runInContext("current.posts = ['Một\\nnguồn', 'Hai']", context);
  await click(); assert.equal(saved.length, 1);
  assert.equal(saved[0].filename, 'ban-tin-3.txt');
  assert.equal(await saved[0].blob.text(), 'Một\nnguồn\n\n---\n\nHai');
});

test('retrying packet copy from fallback checks the displayed bulletin revision', async () => {
  const elements = new Map(), writes = [];
  const get = id => { if (!elements.has(id)) elements.set(id, new Element()); return elements.get(id); };
  get('text-dialog').showModal = () => { get('text-dialog').open = true; };
  get('dialog-text').select = () => {};
  let denied = true;
  const context = vm.createContext({...helpers, URL, URLSearchParams, Intl, Date, Error, Promise, setTimeout, clearTimeout,
    writes, fetch: () => new Promise(() => {}),
    navigator: {clipboard: {writeText: async text => { if (denied) throw new Error('denied'); writes.push(text); }}},
    window: {location: {search: ''}, addEventListener() {}},
    document: {getElementById: get, querySelectorAll: () => [], querySelector: () => new Element(),
      createElement: tag => new Element(tag), createTextNode: text => text}});
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../newsroom/static/app.js'), 'utf8'), context);
  vm.runInContext(`app.bulletin = {id: 7, revision: 4}; let packetRevision = 4;
    api = async () => ({text: 'Tư liệu giả', bulletin_revision: packetRevision}); toast = () => {};`, context);
  await vm.runInContext('copyBulletinPacket(app.bulletin)', context);
  assert.equal(get('dialog-text').value, 'Tư liệu giả');
  assert.match(get('text-dialog-note').textContent, /kiểm tra lại/i);
  denied = false;
  vm.runInContext('packetRevision = 5', context);
  get('copy-dialog').dispatchEvent({type: 'click'});
  await new Promise(resolve => setImmediate(resolve));
  assert.deepEqual(writes, []);
  assert.match(get('text-dialog-note').textContent, /thay đổi/i);
  assert.equal(get('dialog-text').value, 'Tư liệu giả');
  vm.runInContext('packetRevision = 4', context);
  get('copy-dialog').dispatchEvent({type: 'click'});
  await new Promise(resolve => setImmediate(resolve));
  assert.deepEqual(writes, ['Tư liệu giả']);
});

test('retrying copy from fallback checks the approval and leaves a visible warning if stale', async () => {
  const elements = new Map(), writes = [], messages = [];
  const get = id => { if (!elements.has(id)) elements.set(id, new Element()); return elements.get(id); };
  get('text-dialog').showModal = () => { get('text-dialog').open = true; };
  get('dialog-text').select = () => {};
  let denied = true;
  const context = vm.createContext({...helpers, URL, URLSearchParams, Intl, Date, Error, Promise, setTimeout, clearTimeout,
    structuredClone, writes, messages, fetch: () => new Promise(() => {}),
    navigator: {clipboard: {writeText: async text => { if (denied) throw new Error('denied'); writes.push(text); }}},
    window: {location: {search: ''}, addEventListener() {}},
    document: {getElementById: get, querySelectorAll: () => [], querySelector: () => new Element(),
      createElement: tag => new Element(tag), createTextNode: text => text}});
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../newsroom/static/app.js'), 'utf8'), context);
  vm.runInContext(`let current = {approval_id: 21, posts: ['Nội dung đã duyệt']};
    api = async path => path.endsWith('/publications') ? [] : structuredClone(current);
    toast = message => messages.push(message);`, context);
  context.area = new Element();
  await vm.runInContext("renderVariantPublication(area, {id: 3, revision: 4, platform: 'x', account_label: 'Thử'})", context);
  const walk = el => [el, ...el.children.filter(child => child instanceof Element).flatMap(walk)];
  const copyButton = walk(context.area).find(el => el.textContent === 'Sao chép đoạn 1');
  const click = async el => { el.dispatchEvent({type: 'click'}); await new Promise(resolve => setImmediate(resolve)); };
  await click(copyButton);
  assert.equal(get('dialog-text').value, 'Nội dung đã duyệt');
  assert.equal(get('copy-dialog').hidden, false);
  denied = false;
  vm.runInContext('current.approval_id = 22', context);
  await click(get('copy-dialog'));
  assert.deepEqual(writes, []);
  assert.match(get('text-dialog-note').textContent, /thay đổi/i);
  assert.equal(get('dialog-text').value, 'Nội dung đã duyệt');
  vm.runInContext('current.approval_id = 21', context);
  vm.runInContext('app.bulletinDirty = true', context);
  await click(get('copy-dialog'));
  assert.deepEqual(writes, []); assert.match(get('text-dialog-note').textContent, /lưu/i);
  vm.runInContext('app.bulletinDirty = false; app.storeChanged = true', context);
  await click(get('copy-dialog'));
  assert.deepEqual(writes, []); assert.match(get('text-dialog-note').textContent, /Kho dữ liệu/);
  vm.runInContext('app.storeChanged = false', context);
  await click(get('copy-dialog'));
  assert.deepEqual(writes, ['Nội dung đã duyệt']);
  vm.runInContext("showText('Khác', 'Nội dung khác', 'Ghi chú')", context);
  await click(get('copy-dialog'));
  assert.deepEqual(writes, ['Nội dung đã duyệt', 'Nội dung khác']);
});

test('network failure marks a mutation outcome as unknown', async () => {
  const elements = new Map();
  const get = id => { if (!elements.has(id)) elements.set(id, new Element()); return elements.get(id); };
  const context = vm.createContext({...helpers, URL, URLSearchParams, Intl, Date, Error, Promise, setTimeout, clearTimeout,
    requestJson: JSON.stringify, fetch: async () => { throw new Error('offline'); },
    window: {location: {search: ''}, addEventListener() {}},
    document: {getElementById: get, querySelectorAll: () => [], querySelector: () => new Element(),
      createElement: tag => new Element(tag), createTextNode: text => text}});
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../newsroom/static/app.js'), 'utf8'), context);
  await assert.rejects(vm.runInContext("api('/api/variants/3/publications', {url: 'fixture'})", context),
    error => error.outcomeUnknown === true);
  await assert.rejects(vm.runInContext("api('/api/state')", context),
    error => error.outcomeUnknown !== true);
});

test('unreadable response body marks a mutation outcome as unknown', async () => {
  const elements = new Map();
  const get = id => { if (!elements.has(id)) elements.set(id, new Element()); return elements.get(id); };
  let contentType = 'application/json';
  const context = vm.createContext({...helpers, URL, URLSearchParams, Intl, Date, Error, Promise, setTimeout, clearTimeout,
    requestJson: JSON.stringify,
    fetch: async () => ({ok: true, headers: {get: () => contentType},
      json: async () => { throw new SyntaxError('truncated'); }, text: async () => { throw new Error('stream lost'); }}),
    window: {location: {search: ''}, addEventListener() {}},
    document: {getElementById: get, querySelectorAll: () => [], querySelector: () => new Element(),
      createElement: tag => new Element(tag), createTextNode: text => text}});
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../newsroom/static/app.js'), 'utf8'), context);
  await assert.rejects(vm.runInContext("api('/api/variants/3/publications', {url: 'fixture'})", context),
    error => error.outcomeUnknown === true);
  await assert.rejects(vm.runInContext("api('/api/state')", context),
    error => error.outcomeUnknown !== true);
  contentType = 'text/plain';
  await assert.rejects(vm.runInContext("api('/api/variants/3/publications', {url: 'fixture'})", context),
    error => error.outcomeUnknown === true);
});

test('server failure marks a mutation outcome as unknown without changing conflict errors', async () => {
  const elements = new Map();
  const get = id => { if (!elements.has(id)) elements.set(id, new Element()); return elements.get(id); };
  let status = 503;
  const context = vm.createContext({...helpers, URL, URLSearchParams, Intl, Date, Error, Promise, setTimeout, clearTimeout,
    requestJson: JSON.stringify, fetch: async () => ({ok: false, status, headers: {get: () => 'application/json'},
      json: async () => ({error: 'Lỗi thử', target: {kind: 'publication'}})}),
    window: {location: {search: ''}, addEventListener() {}},
    document: {getElementById: get, querySelectorAll: () => [], querySelector: () => new Element(),
      createElement: tag => new Element(tag), createTextNode: text => text}});
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../newsroom/static/app.js'), 'utf8'), context);
  await assert.rejects(vm.runInContext("api('/api/variants/3/publications', {url: 'fixture'})", context),
    error => error.outcomeUnknown === true && error.message.includes('Máy chủ gặp lỗi'));
  await assert.rejects(vm.runInContext("api('/api/state')", context), error => error.outcomeUnknown !== true);
  status = 409;
  await assert.rejects(vm.runInContext("api('/api/variants/3/publications', {url: 'fixture'})", context),
    error => error.outcomeUnknown !== true && error.target.kind === 'publication');
});

test('publication retry reuses its key but a later new recording gets a new key', async () => {
  const elements = new Map();
  const get = id => { if (!elements.has(id)) elements.set(id, new Element()); return elements.get(id); };
  const calls = []; let keyCount = 0;
  const context = vm.createContext({...helpers, URL, URLSearchParams, Intl, Date, Error, Promise, setTimeout, clearTimeout, calls,
    fetch: () => new Promise(() => {}), crypto: {randomUUID: () => `key-${++keyCount}`},
    window: {location: {search: ''}, confirm: () => true, addEventListener() {}},
    document: {getElementById: get, querySelectorAll: () => [], querySelector: () => new Element(),
      createElement: tag => new Element(tag), createTextNode: text => text}});
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../newsroom/static/app.js'), 'utf8'), context);
  vm.runInContext(`api = async (path, body) => { if (path.endsWith('/publications') && body) {
    calls.push(body); if (calls.length === 1) throw Object.assign(new Error('Mất kết nối'), {outcomeUnknown: true}); return {active: 1}; }
    return path.endsWith('/publications') ? [] : {posts: ['test']}; };
    renderBulletin = () => {}; loadBulletinList = async () => {}; toast = () => {};`, context);
  const area = new Element(); get('bulletin-editor').append(area); context.area = area;
  await vm.runInContext("renderVariantPublication(area, {id: 3, revision: 4, platform: 'x', account_label: 'Thử'})", context);
  const walk = el => [el, ...el.children.filter(child => child instanceof Element).flatMap(walk)];
  const url = walk(area).find(el => el.dataset.publicationUrl);
  const report = walk(area).find(el => el.tagName === 'button' && el.textContent === 'Ghi nhận đã đăng');
  const tick = () => new Promise(resolve => setImmediate(resolve));
  url.value = 'https://x.com/a/status/123';
  report.listeners.click[0]({}); await tick();
  const confirm = () => walk(area).find(el => el.tagName === 'button' && el.textContent === 'Xác nhận ghi nhận');
  confirm().listeners.click[0]({}); await tick();
  assert.ok(walk(area).some(el => !el.hidden && el.textContent.includes('có thể đã được ghi nhận')));
  assert.equal(url.value, 'https://x.com/a/status/123');
  confirm().listeners.click[0]({}); await tick();
  assert.equal(calls[0].idempotency_key, calls[1].idempotency_key);
  confirm().listeners.click[0]({}); await tick();
  assert.notEqual(calls[1].idempotency_key, calls[2].idempotency_key);
});

test('retrying a cancelled publication warns and an incomplete response keeps the retry key', async () => {
  const elements = new Map();
  const get = id => { if (!elements.has(id)) elements.set(id, new Element()); return elements.get(id); };
  const calls = [], messages = []; let keyCount = 0;
  const context = vm.createContext({...helpers, URL, URLSearchParams, Intl, Date, Error, Promise, setTimeout, clearTimeout, calls, messages,
    fetch: () => new Promise(() => {}), crypto: {randomUUID: () => `key-${++keyCount}`},
    window: {location: {search: ''}, addEventListener() {}},
    document: {getElementById: get, querySelectorAll: () => [], querySelector: () => new Element(),
      createElement: tag => new Element(tag), createTextNode: text => text}});
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../newsroom/static/app.js'), 'utf8'), context);
  vm.runInContext(`api = async (path, body) => {
    if (path.endsWith('/publications') && body) {
      calls.push(body);
      if (calls.length === 1) throw Object.assign(new Error('Mất kết nối'), {outcomeUnknown: true});
      return calls.length === 2 ? {} : {id: 11, active: 0};
    }
    return path.endsWith('/publications') ? [] : {posts: ['test']};
  }; renderBulletin = () => {}; loadBulletinList = async () => {}; toast = message => messages.push(message);`, context);
  const area = new Element(); get('bulletin-editor').append(area); context.area = area;
  await vm.runInContext("renderVariantPublication(area, {id: 3, revision: 4, platform: 'x', account_label: 'Thử'})", context);
  const walk = el => [el, ...el.children.filter(child => child instanceof Element).flatMap(walk)];
  const button = name => walk(area).find(el => el.tagName === 'button' && el.textContent === name);
  const url = walk(area).find(el => el.dataset.publicationUrl);
  const tick = () => new Promise(resolve => setImmediate(resolve));
  url.value = 'https://x.com/a/status/123'; button('Ghi nhận đã đăng').listeners.click[0]({}); await tick();
  button('Xác nhận ghi nhận').listeners.click[0]({}); await tick();
  button('Xác nhận ghi nhận').listeners.click[0]({}); await tick();
  assert.equal(url.value, 'https://x.com/a/status/123');
  assert.ok(walk(area).some(el => !el.hidden && el.textContent.includes('chưa rõ')));
  assert.equal(calls[0].idempotency_key, calls[1].idempotency_key);
  assert.equal(vm.runInContext('app.publicationKeys.size', context), 1);
  button('Xác nhận ghi nhận').listeners.click[0]({}); await tick();
  assert.equal(calls[1].idempotency_key, calls[2].idempotency_key);
  assert.equal(vm.runInContext('app.publicationKeys.size', context), 0);
  assert.match(messages.at(-1), /không còn hiệu lực/i);
  assert.doesNotMatch(messages.at(-1), /đã ghi nhận thông tin/i);
});

test('publication confirmation identifies destination and invalidates when URL changes', async () => {
  const elements = new Map();
  const get = id => { if (!elements.has(id)) elements.set(id, new Element()); return elements.get(id); };
  const calls = [];
  const context = vm.createContext({...helpers, URL, URLSearchParams, Intl, Date, Error, Promise, setTimeout, clearTimeout, calls,
    fetch: () => new Promise(() => {}), crypto: {randomUUID: () => 'key-1'},
    window: {location: {search: ''}, addEventListener() {}},
    document: {getElementById: get, querySelectorAll: () => [], querySelector: () => new Element(),
      createElement: tag => new Element(tag), createTextNode: text => text}});
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../newsroom/static/app.js'), 'utf8'), context);
  vm.runInContext(`api = async (path, body) => path.endsWith('/publications') ? (body ? (calls.push(body), {active: 1}) : []) : {posts: ['test']};
    renderBulletin = () => {}; loadBulletinList = async () => {}; toast = () => {};`, context);
  const area = new Element(); get('bulletin-editor').append(area); context.area = area;
  await vm.runInContext("renderVariantPublication(area, {id: 3, revision: 4, platform: 'x', account_label: 'Kênh thử'})", context);
  const walk = el => [el, ...el.children.filter(child => child instanceof Element).flatMap(walk)];
  const button = name => walk(area).find(el => el.tagName === 'button' && el.textContent === name);
  const url = walk(area).find(el => el.dataset.publicationUrl);
  const tick = () => new Promise(resolve => setImmediate(resolve));
  url.value = 'https://x.com/a/status/123'; button('Ghi nhận đã đăng').listeners.click[0]({}); await tick();
  assert.equal(calls.length, 0);
  assert.ok(walk(area).some(el => el.textContent.includes('đoạn 1') && el.textContent.includes('Kênh thử')));
  assert.ok(walk(area).some(el => el.textContent.includes('https://x.com/a/status/123')));
  const confirm = button('Xác nhận ghi nhận'); assert.ok(confirm);
  url.value = 'https://x.com/a/status/456'; url.listeners.input[0]({});
  confirm.listeners.click[0]({}); await tick(); assert.equal(calls.length, 0);
  button('Ghi nhận đã đăng').listeners.click[0]({}); await tick();
  button('Xác nhận ghi nhận').listeners.click[0]({}); await tick();
  assert.equal(calls.length, 1); assert.equal(calls[0].url, 'https://x.com/a/status/456');
});

test('legacy publication requires in-page confirmation and invalidates changed context', async () => {
  const elements = new Map();
  const get = id => { if (!elements.has(id)) elements.set(id, new Element()); return elements.get(id); };
  const calls = []; const messages = [];
  const context = vm.createContext({...helpers, URL, URLSearchParams, Intl, Date, Error, Promise, setTimeout, clearTimeout, calls, messages,
    fetch: () => new Promise(() => {}), window: {location: {search: ''}, addEventListener() {},
      confirm: () => { throw new Error('Unexpected browser dialog'); }},
    document: {getElementById: get, querySelectorAll: () => [], querySelector: () => new Element(),
      createElement: tag => new Element(tag), createTextNode: text => text}});
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../newsroom/static/app.js'), 'utf8'), context);
  vm.runInContext(`app.draft = {id: 1, revision: 4, status: 'approved', title: 'Bài thử', page_name: 'Page thử'};
    api = async (path, body) => { calls.push({path, body}); throw new Error('Lỗi thử'); };
    mutation = async action => action(); toast = message => messages.push(message);`, context);
  const tick = () => new Promise(resolve => setImmediate(resolve));
  get('post-url').value = 'https://facebook.com/test/posts/123';
  get('mark-published').listeners.click[0]({}); await tick();
  assert.equal(calls.length, 0);
  assert.equal(get('legacy-publish-confirmation').hidden, false);
  assert.match(get('legacy-publish-summary').textContent, /Bài thử/);
  assert.match(get('legacy-publish-summary').textContent, /Page thử/);
  assert.match(get('legacy-publish-summary').textContent, /posts\/123/);
  get('post-url').value = 'https://facebook.com/test/posts/456';
  get('post-url').listeners.input[0]({});
  get('legacy-confirm-published').listeners.click[0]({}); await tick();
  assert.equal(calls.length, 0);
  get('mark-published').listeners.click[0]({}); await tick();
  vm.runInContext('app.draft.revision += 1', context);
  get('legacy-confirm-published').listeners.click[0]({}); await tick();
  assert.equal(calls.length, 0);
  get('mark-published').listeners.click[0]({}); await tick();
  get('legacy-confirm-published').listeners.click[0]({}); await tick();
  assert.equal(calls.length, 1);
  assert.equal(calls[0].body.post_url, 'https://facebook.com/test/posts/456');
  assert.equal(get('post-url').value, 'https://facebook.com/test/posts/456');
});

test('historical publications show readable events and retain their metrics', async () => {
  const elements = new Map();
  const get = id => { if (!elements.has(id)) elements.set(id, new Element()); return elements.get(id); };
  const context = vm.createContext({...helpers, URL, URLSearchParams, Intl, Date, Error, Promise, setTimeout, clearTimeout,
    fetch: () => new Promise(() => {}), crypto: {randomUUID: () => 'test-key'},
    window: {location: {search: ''}, addEventListener() {}},
    document: {getElementById: get, querySelectorAll: () => [], querySelector: () => new Element(),
      createElement: tag => new Element(tag), createTextNode: text => text}});
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../newsroom/static/app.js'), 'utf8'), context);
  vm.runInContext(`api = async path => path.endsWith('/publications') ? [{id: 11, position: 0, active: false,
    url: 'https://x.com/a/status/123', recorded_at: '2026-11-03T10:00:00Z',
    events: [{action: 'reported', at: '2026-11-03T10:00:00Z', payload: '{}'},
      {action: 'corrected', at: '2026-11-03T11:00:00Z', payload: JSON.stringify({reason: 'Sai liên kết', replacement_url: 'https://x.com/a/status/456'})},
      {action: 'future_action', at: '2026-11-03T12:00:00Z', payload: '{broken'}],
    metrics: [{observed_at: '2026-11-03T10:30:00Z', payload: JSON.stringify({views: 10, likes: 0})}]}] : {posts: ['test']};`, context);
  const area = new Element(); get('bulletin-editor').append(area); context.area = area;
  await vm.runInContext("renderVariantPublication(area, {id: 3, revision: 4, platform: 'x', account_label: 'Thử'})", context);
  const walk = el => [el, ...el.children.filter(child => child instanceof Element).flatMap(walk)];
  const texts = walk(area).map(el => el.textContent).join('\n');
  assert.match(texts, /Đã ghi nhận/); assert.match(texts, /Đã đính chính/);
  assert.match(texts, /Lý do: Sai liên kết/); assert.match(texts, /https:\/\/x.com\/a\/status\/456/);
  assert.match(texts, /Lượt xem: 10/); assert.match(texts, /Lượt thích: 0/);
  assert.match(texts, /future_action/); assert.match(texts, /Dữ liệu sự kiện: \{broken/);
  assert.doesNotMatch(texts, /"replacement_url"/);
});

test('metric form retains edits on error and retries the same payload idempotently', async () => {
  const elements = new Map();
  const get = id => { if (!elements.has(id)) elements.set(id, new Element()); return elements.get(id); };
  const calls = []; let count = 0;
  const context = vm.createContext({...helpers, URL, URLSearchParams, Intl, Date, Error, Promise, setTimeout, clearTimeout, calls,
    crypto: {randomUUID: () => `key-${++count}`}, fetch: () => new Promise(() => {}),
    window: {location: {search: ''}, confirm: () => false, addEventListener() {}},
    document: {getElementById: get, querySelectorAll: () => [], querySelector: () => new Element(),
      createElement: tag => new Element(tag), createTextNode: text => text}});
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../newsroom/static/app.js'), 'utf8'), context);
  vm.runInContext(`api = async (path, body) => path.endsWith('/metrics') ? (calls.push(body), Promise.reject(Object.assign(new Error('Lỗi thử'), {outcomeUnknown: true}))) : path.endsWith('/publications') ?
    [{id: 11, position: 0, active: true, url: 'https://x.com/a/status/123', metrics: []}] : {posts: ['test']};`, context);
  const area = new Element(); get('bulletin-editor').append(area); context.area = area;
  await vm.runInContext("renderVariantPublication(area, {id: 3, revision: 4, platform: 'x', account_label: 'Thử'})", context);
  const walk = el => [el, ...el.children.filter(child => child instanceof Element).flatMap(walk)];
  const button = name => walk(area).find(el => el.tagName === 'button' && el.textContent === name);
  const field = name => walk(area).find(el => el.dataset.metricField === name);
  const tick = () => new Promise(resolve => setImmediate(resolve));
  button('Nhập số liệu').listeners.click[0]({}); await tick();
  assert.ok(field('views')); assert.ok(field('likes')); assert.ok(field('observed_at')); assert.ok(field('note'));
  field('views').value = '10'; field('likes').value = '0'; field('observed_at').value = '2026-11-03T10:00:00+07:00';
  field('note').value = 'Thử'; field('views').listeners.input[0]({}); await tick();
  assert.equal(vm.runInContext('app.bulletinDirty', context), true);
  button('Lưu số liệu').listeners.click[0]({}); await tick();
  assert.equal(calls[0].views, 10); assert.equal(calls[0].likes, 0); assert.equal(calls[0].replies, null);
  assert.equal(field('views').value, '10'); assert.ok(walk(area).some(el => el.textContent.includes('Lỗi thử')));
  assert.ok(walk(area).some(el => el.textContent.includes('có thể đã được lưu')));
  button('Lưu số liệu').listeners.click[0]({}); await tick();
  assert.equal(calls[1].idempotency_key, calls[0].idempotency_key);
  field('views').value = '11'; button('Lưu số liệu').listeners.click[0]({}); await tick();
  assert.notEqual(calls[2].idempotency_key, calls[0].idempotency_key);
  button('Bỏ số liệu chưa lưu').listeners.click[0]({}); await tick();
  assert.equal(vm.runInContext('app.bulletinDirty', context), false);
});

test('correction form preserves inputs and requires confirmation before submitting', async () => {
  const elements = new Map();
  const get = id => { if (!elements.has(id)) elements.set(id, new Element()); return elements.get(id); };
  const calls = [];
  const context = vm.createContext({...helpers, URL, URLSearchParams, Intl, Date, Error, Promise, setTimeout, clearTimeout, calls,
    crypto: {randomUUID: () => 'test-key'}, fetch: () => new Promise(() => {}),
    window: {location: {search: ''}, addEventListener() {}},
    document: {getElementById: get, querySelectorAll: () => [], querySelector: () => new Element(),
      createElement: tag => new Element(tag), createTextNode: text => text}});
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../newsroom/static/app.js'), 'utf8'), context);
  vm.runInContext(`api = async (path, body) => path.endsWith('/corrections') ? (calls.push(body), Promise.reject(new Error('Liên kết không hợp lệ'))) : path.endsWith('/publications') ?
    [{id: 11, position: 0, active: true, url: 'https://x.com/a/status/123', metrics: []}] : {posts: ['test']};`, context);
  const area = new Element(); get('bulletin-editor').append(area); context.area = area;
  await vm.runInContext("renderVariantPublication(area, {id: 3, revision: 4, platform: 'x', account_label: 'Thử'})", context);
  const walk = el => [el, ...el.children.filter(child => child instanceof Element).flatMap(walk)];
  const button = name => walk(area).find(el => el.tagName === 'button' && el.textContent === name);
  const field = name => walk(area).find(el => el.dataset.correctionField === name);
  const tick = () => new Promise(resolve => setImmediate(resolve));
  button('Đính chính liên kết').listeners.click[0]({}); await tick();
  assert.ok(field('reason')); assert.ok(field('url')); assert.ok(field('confirm'));
  field('reason').value = 'Lý do sửa thử'; field('url').value = 'https://wrong.example/post';
  field('reason').listeners.input[0]({}); await tick();
  button('Lưu đính chính').listeners.click[0]({}); await tick();
  assert.equal(calls.length, 0);
  field('confirm').checked = true; field('confirm').listeners.change[0]({}); await tick();
  button('Lưu đính chính').listeners.click[0]({}); await tick();
  assert.equal(calls.length, 1); assert.equal(calls[0].reason, 'Lý do sửa thử');
  assert.equal(field('url').value, 'https://wrong.example/post');
  assert.ok(walk(area).some(el => el.textContent.includes('Liên kết không hợp lệ')));
  vm.runInContext(`api = async () => { throw Object.assign(new Error('Mất kết nối'), {outcomeUnknown: true}); };`, context);
  button('Lưu đính chính').listeners.click[0]({}); await tick();
  assert.ok(walk(area).some(el => el.textContent.includes('thay đổi có thể đã được lưu')));
  assert.ok(walk(area).some(el => el.textContent.includes('Đính chính đang đối soát')));
  assert.ok(!walk(area).some(el => el.textContent.includes('Đính chính chưa lưu ·')));
  assert.equal(field('reason').value, 'Lý do sửa thử');
  assert.equal(field('url').value, 'https://wrong.example/post');
  field('url').value = 'https://x.com/a/status/456'; field('url').listeners.input[0]({}); await tick();
  assert.equal(field('confirm').checked, false);
  button('Lưu đính chính').listeners.click[0]({}); await tick();
  assert.equal(calls.length, 1);
  assert.equal(vm.runInContext('app.bulletinDirty', context), true);
  button('Bỏ nội dung biểu mẫu').listeners.click[0]({}); await tick();
  assert.equal(vm.runInContext('app.bulletinDirty', context), false);
});

test('pending correction remains dirty until explicitly discarded', async () => {
  const elements = new Map();
  const get = id => { if (!elements.has(id)) elements.set(id, new Element()); return elements.get(id); };
  const windowListeners = {};
  let confirm = false;
  const context = vm.createContext({...helpers, URL, URLSearchParams, Intl, Date, Error, Promise,
    setTimeout, clearTimeout, crypto: {randomUUID: () => 'test-key'},
    fetch: () => new Promise(() => {}),
    window: {location: {search: ''}, confirm: () => confirm,
      addEventListener: (type, handler) => { windowListeners[type] = handler; }},
    document: {getElementById: get, querySelectorAll: () => [], querySelector: () => new Element(),
      createElement: tag => new Element(tag), createTextNode: text => text},
  });
  const source = fs.readFileSync(path.join(__dirname, '../newsroom/static/app.js'), 'utf8');
  vm.runInContext(source, context, {filename: 'app.js'});
  vm.runInContext(`api = async path => path.endsWith('/corrections') ? Promise.reject(new Error('Liên kết không hợp lệ')) : path.endsWith('/publications') ?
    [{id: 11, position: 0, active: true, url: 'https://x.com/a/status/123', metrics: []}] :
    {posts: ['test']};`, context);
  const editor = get('bulletin-editor');
  const area = new Element(); editor.append(area);
  context.area = area;
  await vm.runInContext("renderVariantPublication(area, {id: 3, revision: 4, platform: 'x', account_label: 'Thử'})", context);
  const walk = element => [element, ...element.children.filter(child => child instanceof Element).flatMap(walk)];
  const button = text => walk(area).find(el => el.tagName === 'button' && el.textContent === text);
  button('Đính chính liên kết').listeners.click[0]({});
  await new Promise(resolve => setImmediate(resolve));
  const field = name => walk(area).find(el => el.dataset.correctionField === name);
  field('reason').value = 'Lý do sửa thử'; field('reason').listeners.input[0]({});
  await new Promise(resolve => setImmediate(resolve));
  const notice = walk(area).find(el => el.dataset.pendingCorrection === 'true');
  assert.ok(notice);
  assert.equal(vm.runInContext('app.bulletinDirty', context), true);
  let prevented = false;
  windowListeners.beforeunload({preventDefault() { prevented = true; }});
  assert.equal(prevented, true);
  assert.equal(field('reason').value, 'Lý do sửa thử');
  assert.equal(vm.runInContext('hasPendingPublicationEdit()', context), true);
  vm.runInContext("app.view = 'bulletins'; view('inbox')", context);
  assert.equal(vm.runInContext('app.view', context), 'bulletins');
  field('url').value = 'https://wrong.example/post'; field('url').listeners.input[0]({});
  await new Promise(resolve => setImmediate(resolve));
  field('confirm').checked = true; field('confirm').listeners.change[0]({});
  await new Promise(resolve => setImmediate(resolve));
  button('Lưu đính chính').listeners.click[0]({});
  await new Promise(resolve => setImmediate(resolve));
  assert.ok(walk(notice).some(el => el.textContent.includes('Liên kết không hợp lệ')));
  assert.equal(field('url').value, 'https://wrong.example/post');
  button('Bỏ nội dung biểu mẫu').listeners.click[0]({});
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(vm.runInContext('app.bulletinDirty', context), false);
  assert.equal(notice.hidden, true);
});

test('X metrics handler keeps the order, zero and unknown values, and displays legacy shares', async () => {
  const elements = new Map();
  const get = id => { if (!elements.has(id)) elements.set(id, new Element()); return elements.get(id); };
  const prompts = ['10,0,,3,4,5,,15', '2026-11-03T10:00:00+07:00', 'Ghi chú thử'];
  const calls = [];
  const old = JSON.stringify({views: 7, likes: null, saves: null, shares: 0, followers: null, minutes: null, note: ''});
  const context = vm.createContext({...helpers, URL, URLSearchParams, Intl, Date, Error, Promise,
    setTimeout, clearTimeout, calls, old, crypto: {randomUUID: () => 'test-key'},
    fetch: () => new Promise(() => {}),
    window: {location: {search: ''}, prompt: () => prompts.shift(), addEventListener() {}},
    document: {getElementById: get, querySelectorAll: () => [], querySelector: () => new Element(),
      createElement: tag => new Element(tag), createTextNode: text => text},
  });
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../newsroom/static/app.js'), 'utf8'), context, {filename: 'app.js'});
  vm.runInContext(`api = async (path, body) => {
    if (path.endsWith('/metrics')) { calls.push({path, body}); return {}; }
    if (path.endsWith('/publications')) return [{id: 11, position: 0, active: true,
      url: 'https://x.com/a/status/123', metrics: [{observed_at: '2026-11-03T10:00:00+07:00', payload: old}]}];
    return {posts: ['test']};
  }; renderBulletin = () => {}; toast = () => {};`, context);
  const area = new Element(); get('bulletin-editor').append(area); context.area = area;
  await vm.runInContext("renderVariantPublication(area, {id: 3, revision: 4, platform: 'x', account_label: 'Thử'})", context);
  const walk = element => [element, ...element.children.filter(child => child instanceof Element).flatMap(walk)];
  assert.ok(walk(area).some(el => el.textContent.includes('Lượt chia sẻ: 0')));
  walk(area).find(el => el.tagName === 'button' && el.textContent === 'Nhập số liệu').listeners.click[0]({});
  await new Promise(resolve => setImmediate(resolve));
  const field = key => walk(area).find(el => el.dataset.metricField === key);
  ['10','0','','3','4','5','','15'].forEach((value, i) => { field(helpers.metricFields('x')[i][0]).value = value; });
  field('observed_at').value = '2026-11-03T10:00:00+07:00'; field('note').value = 'Ghi chú thử';
  walk(area).find(el => el.tagName === 'button' && el.textContent === 'Lưu số liệu').listeners.click[0]({});
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(calls.length, 1);
  assert.equal(calls[0].path, '/api/publications/11/metrics');
  assert.deepEqual(JSON.parse(JSON.stringify(calls[0].body)), {observed_at: '2026-11-03T10:00:00+07:00',
    note: 'Ghi chú thử', views: 10, likes: 0, replies: null, reposts: 3, quotes: 4, saves: 5, followers: null, minutes: 15,
    idempotency_key: 'test-key'});
});

test('cancelled metric entry remains available and blocks navigation until discarded', async () => {
  const elements = new Map();
  const get = id => { if (!elements.has(id)) elements.set(id, new Element()); return elements.get(id); };
  const prompts = ['10,0,,3,4,5,,15', null];
  const defaults = [];
  const calls = [];
  let keyCount = 0;
  const context = vm.createContext({...helpers, URL, URLSearchParams, Intl, Date, Error, Promise,
    setTimeout, clearTimeout, calls, crypto: {randomUUID: () => `test-key-${++keyCount}`},
    fetch: () => new Promise(() => {}),
    window: {location: {search: ''}, prompt: (text, value) => { defaults.push(value); return prompts.shift(); },
      confirm: () => false, addEventListener() {}},
    document: {getElementById: get, querySelectorAll: () => [], querySelector: () => new Element(),
      createElement: tag => new Element(tag), createTextNode: text => text},
  });
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../newsroom/static/app.js'), 'utf8'), context, {filename: 'app.js'});
  vm.runInContext(`api = async (path, body) => path.endsWith('/metrics') ? (calls.push(body), Promise.reject(new Error('Thời điểm không hợp lệ'))) : path.endsWith('/publications') ?
    [{id: 11, position: 0, active: true, url: 'https://x.com/a/status/123', metrics: []}] : {posts: ['test']};`, context);
  const area = new Element(); get('bulletin-editor').append(area); context.area = area;
  await vm.runInContext("renderVariantPublication(area, {id: 3, revision: 4, platform: 'x', account_label: 'Thử'})", context);
  const walk = element => [element, ...element.children.filter(child => child instanceof Element).flatMap(walk)];
  const button = text => walk(area).find(el => el.tagName === 'button' && el.textContent === text);
  button('Nhập số liệu').listeners.click[0]({});
  await new Promise(resolve => setImmediate(resolve));
  const field = key => walk(area).find(el => el.dataset.metricField === key);
  ['10','0','','3','4','5','','15'].forEach((value, i) => { field(helpers.metricFields('x')[i][0]).value = value; });
  field('views').listeners.input[0]({}); await new Promise(resolve => setImmediate(resolve));
  assert.equal(vm.runInContext('app.bulletinDirty', context), true);
  vm.runInContext("app.view = 'bulletins'; view('inbox')", context);
  assert.equal(vm.runInContext('app.view', context), 'bulletins');
  field('observed_at').value = 'sai ngày'; field('note').value = 'ghi chú thử';
  button('Lưu số liệu').listeners.click[0]({});
  await new Promise(resolve => setImmediate(resolve));
  assert.ok(walk(area).some(el => el.textContent.includes('Thời điểm không hợp lệ')));
  assert.equal(field('observed_at').value, 'sai ngày'); assert.equal(field('note').value, 'ghi chú thử');
  assert.equal(vm.runInContext('app.bulletinDirty', context), true);
  button('Lưu số liệu').listeners.click[0]({});
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(calls.length, 2);
  assert.equal(calls[0].idempotency_key, 'test-key-1');
  assert.equal(calls[1].idempotency_key, calls[0].idempotency_key);
  field('views').value = '11';
  button('Lưu số liệu').listeners.click[0]({});
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(calls[2].idempotency_key, 'test-key-2');
  button('Bỏ số liệu chưa lưu').listeners.click[0]({});
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(vm.runInContext('app.bulletinDirty', context), false);
});


test('variant selection restores focus only while the user has not moved elsewhere', async () => {
  const elements = new Map();
  const get = id => { if (!elements.has(id)) elements.set(id, new Element()); return elements.get(id); };
  const body = new Element('body');
  const document = {body, activeElement: body, getElementById: get, querySelectorAll: () => [],
    querySelector: () => new Element(), createElement: tag => new Element(tag), createTextNode: text => text};
  const context = vm.createContext({...helpers, URL, URLSearchParams, Intl, Date, Error, Promise, setTimeout, clearTimeout,
    fetch: () => new Promise(() => {}), window: {location: {search: ''}, addEventListener() {}}, document});
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../newsroom/static/app.js'), 'utf8'), context);
  context.bulletin = {id: 1, items: []};
  vm.runInContext(`app.view = 'bulletins'; app.bulletin = bulletin; api = async () => [];
    renderBulletin = focus => { globalThis.requestedFocus = focus; };`, context);
  context.container = new Element();
  await vm.runInContext('renderVariants(container, bulletin)', context);
  const selector = context.container.children[0];
  assert.equal(selector['aria-label'], 'Chọn phiên bản');
  assert.equal(context.container.children[1]['aria-label'], 'Nền tảng phiên bản mới');
  document.activeElement = selector;
  selector.listeners.change[0]({});
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(context.requestedFocus, true);
  document.activeElement = new Element('button');
  selector.listeners.change[0]({});
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(context.requestedFocus, false);

  document.activeElement = body;
  context.container = new Element();
  await vm.runInContext('renderVariants(container, bulletin, true)', context);
  assert.equal(context.container.children[0].focused, true);
  document.activeElement = new Element('button');
  context.container = new Element();
  await vm.runInContext('renderVariants(container, bulletin, true)', context);
  assert.notEqual(context.container.children[0].focused, true);
  document.activeElement = body;
  vm.runInContext("app.view = 'inbox'", context);
  context.container = new Element();
  await vm.runInContext('renderVariants(container, bulletin, true)', context);
  assert.notEqual(context.container.children[0].focused, true);
});

test('approval error stays visible and preserves editor contents until a new attempt', async () => {
  const elements = new Map();
  const get = id => { if (!elements.has(id)) elements.set(id, new Element()); return elements.get(id); };
  const calls = [];
  const context = vm.createContext({...helpers, URL, URLSearchParams, Intl, Date, Error, Promise, setTimeout, clearTimeout,
    fetch: () => new Promise(() => {}), window: {location: {search: ''}, addEventListener() {}},
    document: {getElementById: get, querySelectorAll: () => [], querySelector: () => new Element(),
      createElement: tag => new Element(tag), createTextNode: text => text}});
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../newsroom/static/app.js'), 'utf8'), context);
  context.calls = calls;
  vm.runInContext(`app.variantId = 3; api = async (path, body) => { if (path.endsWith('/variants')) return [{id: 3, revision: 4, platform: 'x', account_label: 'Kênh', status: 'draft', segments: [{text: 'Bản nháp', item_ids: [], source_ids: []}], checks: {}}];
    calls.push(body); throw new Error('Mục 1: ghi chú còn chưa xác minh'); }; toast = () => {};`, context);
  const container = new Element(); get('bulletin-editor').append(container); context.container = container;
  await vm.runInContext('renderVariants(container, {id: 1, items: []})', context);
  const walk = el => [el, ...el.children.filter(child => child instanceof Element).flatMap(walk)];
  const button = walk(container).find(el => el.tagName === 'button' && el.textContent === 'Duyệt phiên bản');
  const field = walk(container).find(el => el.tagName === 'textarea');
  field.value = 'Nội dung đang nhập';
  button.listeners.click[0]({}); await new Promise(resolve => setImmediate(resolve));
  const alert = walk(container).find(el => el.role === 'alert' && el.textContent.includes('Mục 1'));
  assert.ok(alert); assert.equal(alert.hidden, false);
  assert.equal(field.value, 'Nội dung đang nhập'); assert.equal(calls[0].revision, 4);
  button.listeners.click[0]({}); await new Promise(resolve => setImmediate(resolve));
  assert.equal(calls.length, 2); assert.match(alert.textContent, /Mục 1/);
});

test('older source dates show the Vietnam calendar date across midnight', () => {
  class FixedDate extends Date {
    static now() { return Date.parse('2026-11-04T17:30:00Z'); }
  }
  const elements = new Map();
  const get = id => { if (!elements.has(id)) elements.set(id, new Element()); return elements.get(id); };
  const context = vm.createContext({...helpers, URL, URLSearchParams, Intl, Date: FixedDate, Error, Promise,
    setTimeout, clearTimeout, fetch: () => new Promise(() => {}),
    window: {location: {search: ''}, addEventListener() {}},
    document: {getElementById: get, querySelectorAll: () => [], querySelector: () => new Element(),
      createElement: tag => new Element(tag), createTextNode: text => text}});
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../newsroom/static/app.js'), 'utf8'), context);
  assert.equal(vm.runInContext("shortDate('2026-10-23T16:59:00Z')", context), '23/10/2026');
  assert.equal(vm.runInContext("shortDate('2026-10-23T17:01:00Z')", context), '24/10/2026');
  assert.equal(vm.runInContext("shortDate('2026-11-04T16:50:00Z')", context), 'Trong giờ qua');
  assert.equal(vm.runInContext("shortDate('2026-11-04T17:31:00Z')", context), 'Ngày nguồn ở tương lai');
  assert.equal(vm.runInContext("shortDate(null)", context), 'Chưa rõ ngày');
});

test('bulletin archive controls preserve unsaved work and show archived entries on request', async () => {
  const elements = new Map();
  const get = id => { if (!elements.has(id)) elements.set(id, new Element()); return elements.get(id); };
  const calls = [], messages = [];
  let uncertain = false, listFails = false;
  const context = vm.createContext({...helpers, URL, URLSearchParams, Intl, Date, Error, Promise,
    setTimeout, clearTimeout, fetch: () => new Promise(() => {}), calls, messages,
    shouldFail: () => uncertain, shouldFailList: () => listFails,
    window: {location: {search: ''}, addEventListener() {}, confirm: () => { throw new Error('Unexpected browser dialog'); }},
    document: {getElementById: get, querySelectorAll: () => [], querySelector: () => new Element(),
      createElement: tag => new Element(tag), createTextNode: text => text}});
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../newsroom/static/app.js'), 'utf8'), context);
  vm.runInContext(`app.state = {articles: [], bulletin_usage: {}};
    app.bulletin = {id: 7, revision: 4, archive_revision: 0, archived: false, title: 'Bản tin thử',
      edition_date: '2026-11-04', introduction: '', conclusion: '', items: []};
    toast = message => messages.push(message);
    api = async (path, body) => {
      if (path === '/api/bulletins/7/archive') {
        calls.push({path, body});
        if (shouldFail()) { const error = new Error('Mất kết nối'); error.outcomeUnknown = true; throw error; }
        return {...app.bulletin, archived: body.archived, archive_revision: body.archive_revision + 1};
      }
      if (path === '/api/bulletins/7/variants') return [];
      if (path === '/api/bulletins') {
        if (shouldFailList()) throw new Error('Không tải được danh sách');
        return [
          {id: 7, revision: 4, title: 'Đang làm', edition_date: '2026-11-04', item_count: 1, archived: false},
          {id: 8, revision: 3, title: 'Đã cất', edition_date: '2026-11-03', item_count: 1, archived: true}];
      }
      if (path === '/api/bulletin-stats') return {bulletins: 2, variants: 0, recorded_bulletins: 0, recorded_posts: 0};
      if (path === '/api/legacy-publication-duplicates') return [];
      throw new Error('Unexpected API ' + path);
    }; renderBulletin();`, context);
  const walk = el => [el, ...el.children.filter(child => child instanceof Element).flatMap(walk)];
  const button = name => walk(get('bulletin-editor')).find(el => el.tagName === 'button' && el.textContent === name);
  const tick = () => new Promise(resolve => setImmediate(resolve));
  assert.ok(button('Lưu trữ bản tin'));
  vm.runInContext('app.bulletinDirty = true', context);
  button('Lưu trữ bản tin').listeners.click[0]({}); await tick();
  assert.equal(calls.length, 0); assert.match(messages.at(-1), /lưu|bỏ/i);
  vm.runInContext('app.bulletinDirty = false', context);
  const pending = new Element('input'); pending.dataset.publicationUrl = '0'; pending.value = 'https://x.com/fake/status/1';
  get('bulletin-editor').append(pending);
  button('Lưu trữ bản tin').listeners.click[0]({}); await tick();
  assert.equal(calls.length, 0); assert.match(messages.at(-1), /lưu|bỏ/i);
  get('bulletin-editor').children = get('bulletin-editor').children.filter(child => child !== pending);
  button('Lưu trữ bản tin').listeners.click[0]({}); await tick();
  assert.equal(calls.length, 0);
  assert.ok(walk(get('bulletin-editor')).some(el => /Lưu trữ.*Bản tin thử/.test(el.textContent)));
  assert.equal(button('Xác nhận lưu trữ').focused, true);
  const oldConfirm = button('Xác nhận lưu trữ');
  button('Hủy lưu trữ').listeners.click[0]({}); await tick();
  assert.equal(calls.length, 0);
  assert.equal(button('Lưu trữ bản tin').focused, true);
  oldConfirm.listeners.click[0]({}); await tick();
  assert.equal(calls.length, 0);
  button('Lưu trữ bản tin').listeners.click[0]({}); await tick();
  vm.runInContext("app.bulletin.title = 'Bản tin khác'", context);
  button('Xác nhận lưu trữ').listeners.click[0]({}); await tick();
  assert.equal(calls.length, 0); assert.match(messages.at(-1), /đã thay đổi/i);
  vm.runInContext("app.bulletin.title = 'Bản tin thử'", context);
  button('Lưu trữ bản tin').listeners.click[0]({}); await tick();
  vm.runInContext('app.bulletinDirty = true', context);
  button('Xác nhận lưu trữ').listeners.click[0]({}); await tick();
  assert.equal(calls.length, 0); assert.match(messages.at(-1), /lưu|bỏ/i);
  vm.runInContext('app.bulletinDirty = false', context);
  button('Xác nhận lưu trữ').listeners.click[0]({}); await tick();
  assert.equal(calls.length, 1);
  assert.deepEqual(JSON.parse(JSON.stringify(calls[0].body)), {revision: 4, archive_revision: 0, archived: true});
  assert.equal(vm.runInContext('app.bulletin', context), null);
  assert.ok(walk(get('bulletin-list')).some(el => el.textContent === 'Đang làm'));
  assert.ok(!walk(get('bulletin-list')).some(el => el.textContent === 'Đã cất'));
  get('show-archived-bulletins').checked = true;
  get('show-archived-bulletins').listeners.change[0]({}); await tick();
  assert.ok(walk(get('bulletin-list')).some(el => el.textContent === 'Đã cất'));

  vm.runInContext(`app.bulletin = {id: 7, revision: 4, archive_revision: 1, archived: true,
    title: 'Bản tin thử', edition_date: '2026-11-04', introduction: '', conclusion: '', items: []}; renderBulletin();`, context);
  await tick();
  assert.ok(button('Khôi phục bản tin'));
  uncertain = true;
  button('Khôi phục bản tin').listeners.click[0]({}); await tick();
  button('Xác nhận khôi phục').listeners.click[0]({}); await tick();
  assert.match(messages.at(-1), /có thể đã thay đổi/);
  assert.equal(vm.runInContext('app.bulletin.archived', context), true);
  uncertain = false; listFails = true;
  button('Xác nhận khôi phục').listeners.click[0]({}); await tick();
  assert.deepEqual(JSON.parse(JSON.stringify(calls[2].body)), {revision: 4, archive_revision: 1, archived: false});
  assert.equal(vm.runInContext('app.bulletin.archived', context), false);
  assert.match(messages.at(-1), /Đã khôi phục.*chưa tải lại/i);
  vm.runInContext(`app.bulletin = {id: 7, revision: 4, title: 'Máy chủ cũ',
    edition_date: '2026-11-04', introduction: '', conclusion: '', items: []}; renderBulletin();`, context);
  assert.equal(button('Lưu trữ bản tin'), undefined);
  assert.ok(walk(get('bulletin-editor')).some(el => /khởi động lại.*ứng dụng/i.test(el.textContent)));
});

test('preview warns if the server sees a newer bulletin revision', async () => {
  const elements = new Map();
  const get = id => { if (!elements.has(id)) elements.set(id, new Element()); return elements.get(id); };
  const previews = [];
  let stale = true, serverRevision = 5;
  const context = vm.createContext({...helpers, URL, URLSearchParams, Intl, Date, Error, Promise,
    setTimeout, clearTimeout, fetch: () => new Promise(() => {}), previews, isStale: () => stale, serverRevision: () => serverRevision,
    window: {location: {search: ''}, addEventListener() {}},
    document: {getElementById: get, querySelectorAll: () => [], querySelector: () => new Element(),
      createElement: tag => new Element(tag), createTextNode: text => text}});
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../newsroom/static/app.js'), 'utf8'), context);
  context.container = new Element();
  vm.runInContext(`app.variantId = 3;
    api = async path => path.endsWith('/variants') ? [{
      id: 3, revision: 1, platform: 'x', account_label: 'Kênh thử', status: 'draft',
      locked_at: null, needs_update: false, policy_stale: false,
      checks: {}, segments: [{text: 'Tin giả', item_ids: [1], source_ids: ['source-1']}]
    }] : {warning: 'Bộ đếm chỉ hỗ trợ.', policy_version: 'fixture-policy-v1', needs_update: isStale(), bulletin_revision: serverRevision(), omitted_item_ids: [2, 3, 9],
          posts: [{position: 0, length: 10, limit: 280, valid: true, text: 'Tin giả'}]};
    showText = (title, text, warning) => previews.push({title, text, warning});`, context);
  const bulletin = {id: 7, revision: 4, items: [
    {id: 1, title: 'Tin giả', sources: [{source_id: 'source-1', url: 'https://example.com/a'}]},
    {id: 2, title: 'Tin chưa đưa vào', sources: []},
    {id: 3, title: 'Tin chưa đưa vào', sources: []}]};
  context.bulletin = bulletin;
  await vm.runInContext('renderVariants(container, bulletin)', context);
  const walk = el => [el, ...el.children.filter(child => child instanceof Element).flatMap(walk)];
  const preview = walk(context.container).find(el => el.tagName === 'button' && el.textContent === 'Xem trước');
  assert.ok(preview);
  const tick = () => new Promise(resolve => setImmediate(resolve));
  preview.listeners.click[0]({}); await tick();
  assert.match(previews[0].warning, /bản tin gốc đã thay đổi/i);
  assert.match(previews[0].warning, /fixture-policy-v1/);
  assert.match(previews[0].warning, /sao chép nội dung chưa lưu trước khi mở lại bản tin/i);
  assert.match(previews[0].warning, /kiểm tra.*duyệt/i);
  assert.doesNotMatch(previews[0].warning, /Tin chưa đưa vào/);
  stale = false; serverRevision = 4;
  preview.listeners.click[0]({}); await tick();
  assert.doesNotMatch(previews[1].warning, /bản tin gốc đã thay đổi/i);
  assert.match(previews[1].warning, /fixture-policy-v1/);
  assert.match(previews[1].warning, /#2[^,]*Tin chưa đưa vào/);
  assert.match(previews[1].warning, /#3[^,]*Tin chưa đưa vào/);
  assert.match(previews[1].warning, /#9/);
  assert.doesNotMatch(previews[1].text, /Tin chưa đưa vào/);
  serverRevision = 5;
  preview.listeners.click[0]({}); await tick();
  assert.match(previews[2].warning, /bản tin gốc đã thay đổi/i);
  assert.doesNotMatch(previews[2].warning, /Tin chưa đưa vào/);
});
