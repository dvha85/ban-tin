'use strict';
const {test} = require('node:test');
const assert = require('node:assert/strict');
const {requestJson} = require('../newsroom/static/request-size.js');

test('request size is measured after JSON serialization in UTF-8', () => {
  const exact = {text: 'a'.repeat(127989)}; // 11 bytes of JSON framing
  assert.equal(Buffer.byteLength(requestJson(exact), 'utf8'), 128000);
  assert.throws(() => requestJson({text: exact.text + 'a'}), /128\.000 byte/);
  assert.throws(() => requestJson({text: 'ệ'.repeat(64000)}), /128\.000 byte/);
  assert.equal(JSON.parse(requestJson({text: 'dòng\n"thử"'})).text, 'dòng\n"thử"');
});
