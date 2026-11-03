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
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.children = children; }
  addEventListener(name, listener) { (this.listeners[name] ||= []).push(listener); }
  setAttribute(name, value) { this[name] = value; }
  querySelectorAll(selector) {
    const rows = [];
    const visit = element => {
      if (!(element instanceof Element)) return;
      if (selector === '[data-dirty="true"]' && element.dataset.dirty === 'true') rows.push(element);
      if (selector === '[data-pending-correction="true"]' && element.dataset.pendingCorrection === 'true') rows.push(element);
      if (selector === '[data-pending-publication-edit="true"]' && element.dataset.pendingPublicationEdit === 'true') rows.push(element);
      if (selector === '[data-publication-url]' && element.dataset.publicationUrl) rows.push(element);
      element.children.forEach(visit);
    };
    this.children.forEach(visit); return rows;
  }
  querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
}

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
  vm.runInContext(`api = async (path, body) => path.endsWith('/metrics') ? (calls.push(body), Promise.reject(new Error('Lỗi thử'))) : path.endsWith('/publications') ?
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
  field('url').value = 'https://x.com/a/status/456'; field('url').listeners.input[0]({}); await tick();
  assert.equal(field('confirm').checked, false);
  button('Lưu đính chính').listeners.click[0]({}); await tick();
  assert.equal(calls.length, 1);
  assert.equal(vm.runInContext('app.bulletinDirty', context), true);
  button('Bỏ đính chính chưa lưu').listeners.click[0]({}); await tick();
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
  button('Bỏ đính chính chưa lưu').listeners.click[0]({});
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
