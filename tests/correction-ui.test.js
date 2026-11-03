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
  assert.equal(vm.runInContext('hasPendingCorrection()', context), true);
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
