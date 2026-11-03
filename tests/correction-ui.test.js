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

test('pending correction remains dirty until explicitly discarded', async () => {
  const elements = new Map();
  const get = id => { if (!elements.has(id)) elements.set(id, new Element()); return elements.get(id); };
  const windowListeners = {};
  const prompts = ['Lý do sửa thử', null];
  let confirm = false;
  const context = vm.createContext({...helpers, URL, URLSearchParams, Intl, Date, Error, Promise,
    setTimeout, clearTimeout, crypto: {randomUUID: () => 'test-key'},
    fetch: () => new Promise(() => {}),
    window: {location: {search: ''}, prompt: () => prompts.shift(), confirm: () => confirm,
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
  const notice = walk(area).find(el => el.dataset.pendingCorrection === 'true');
  assert.ok(notice);
  assert.equal(vm.runInContext('app.bulletinDirty', context), true);
  let prevented = false;
  windowListeners.beforeunload({preventDefault() { prevented = true; }});
  assert.equal(prevented, true);
  assert.ok(walk(notice).some(el => el.textContent.includes('Lý do sửa thử')));
  assert.equal(vm.runInContext('hasPendingPublicationEdit()', context), true);
  vm.runInContext("app.view = 'bulletins'; view('inbox')", context);
  assert.equal(vm.runInContext('app.view', context), 'bulletins');
  prompts.push('Lý do sửa thử', 'https://wrong.example/post'); confirm = true;
  button('Đính chính liên kết').listeners.click[0]({});
  await new Promise(resolve => setImmediate(resolve));
  assert.ok(walk(notice).some(el => el.textContent.includes('Liên kết không hợp lệ')));
  assert.ok(walk(notice).some(el => el.textContent.includes('https://wrong.example/post')));
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
  assert.equal(vm.runInContext('app.bulletinDirty', context), true);
  vm.runInContext("app.view = 'bulletins'; view('inbox')", context);
  assert.equal(vm.runInContext('app.view', context), 'bulletins');
  prompts.push(null);
  button('Nhập số liệu').listeners.click[0]({});
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(defaults[2], '10,0,,3,4,5,,15');
  prompts.push('10,0,,3,4,5,,15', 'sai ngày', 'ghi chú thử');
  button('Nhập số liệu').listeners.click[0]({});
  await new Promise(resolve => setImmediate(resolve));
  assert.ok(walk(area).some(el => el.textContent.includes('Thời điểm không hợp lệ')));
  assert.ok(walk(area).some(el => el.textContent.includes('sai ngày') && el.textContent.includes('ghi chú thử')));
  assert.equal(vm.runInContext('app.bulletinDirty', context), true);
  prompts.push('10,0,,3,4,5,,15', 'sai ngày', 'ghi chú thử');
  button('Nhập số liệu').listeners.click[0]({});
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(calls.length, 2);
  assert.equal(calls[0].idempotency_key, 'test-key-1');
  assert.equal(calls[1].idempotency_key, calls[0].idempotency_key);
  prompts.push('11,0,,3,4,5,,15', 'sai ngày', 'ghi chú thử');
  button('Nhập số liệu').listeners.click[0]({});
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(calls[2].idempotency_key, 'test-key-2');
  button('Bỏ số liệu chưa lưu').listeners.click[0]({});
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(vm.runInContext('app.bulletinDirty', context), false);
});
