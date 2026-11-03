'use strict';
const {test} = require('node:test');
const assert = require('node:assert/strict');
const {sourceWarnings} = require('../newsroom/static/source-warnings.js');

test('source prompts distinguish missing, short, old and future dates', () => {
  const now = Date.parse('2026-11-03T00:00:00Z');
  assert.deepEqual(sourceWarnings({summary: '', published_at: null}, now), [
    'Nguồn chưa có trích đoạn hoặc ghi chú.', 'Chưa rõ ngày nguồn.']);
  assert.deepEqual(sourceWarnings({summary: 'a'.repeat(79), published_at: '2026-10-26T23:59:59Z'}, now), [
    'Trích đoạn hoặc ghi chú ngắn hơn 80 ký tự.', 'Nguồn đã quá 7 ngày; hãy kiểm tra cập nhật.']);
  assert.deepEqual(sourceWarnings({summary: 'a'.repeat(80), published_at: '2026-11-04T00:00:00Z'}, now), [
    'Ngày nguồn ở tương lai; hãy kiểm tra lại.']);
  assert.deepEqual(sourceWarnings({summary: 'a'.repeat(80), published_at: '2026-10-27T00:00:00Z'}, now), []);
});
