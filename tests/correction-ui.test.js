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
    calls.push(body); if (calls.length === 1) throw Object.assign(new Error('Mất kết nối'), {outcomeUnknown: true}); return {}; }
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
  vm.runInContext(`api = async (path, body) => path.endsWith('/publications') ? (body ? (calls.push(body), {}) : []) : {posts: ['test']};
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
  let confirmed = false, uncertain = false, listFails = false;
  const context = vm.createContext({...helpers, URL, URLSearchParams, Intl, Date, Error, Promise,
    setTimeout, clearTimeout, fetch: () => new Promise(() => {}), calls, messages,
    shouldFail: () => uncertain, shouldFailList: () => listFails,
    window: {location: {search: ''}, addEventListener() {}, confirm: () => confirmed},
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
  confirmed = true;
  button('Lưu trữ bản tin').listeners.click[0]({}); await tick();
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
  assert.match(messages.at(-1), /có thể đã thay đổi/);
  assert.equal(vm.runInContext('app.bulletin.archived', context), true);
  uncertain = false; listFails = true;
  button('Khôi phục bản tin').listeners.click[0]({}); await tick();
  assert.deepEqual(JSON.parse(JSON.stringify(calls[2].body)), {revision: 4, archive_revision: 1, archived: false});
  assert.equal(vm.runInContext('app.bulletin.archived', context), false);
  assert.match(messages.at(-1), /Đã khôi phục.*chưa tải lại/i);
  vm.runInContext(`app.bulletin = {id: 7, revision: 4, title: 'Máy chủ cũ',
    edition_date: '2026-11-04', introduction: '', conclusion: '', items: []}; renderBulletin();`, context);
  assert.equal(button('Lưu trữ bản tin'), undefined);
  assert.ok(walk(get('bulletin-editor')).some(el => /khởi động lại.*ứng dụng/i.test(el.textContent)));
});
