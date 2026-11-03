'use strict';
const {test} = require('node:test');
const assert = require('node:assert/strict');
const {matchesAge, hiddenSelectionCount} = require('../newsroom/static/inbox-utils.js');

test('time filter excludes unknown and future dates outside all', () => {
  const now = Date.parse('2026-11-03T00:00:00Z');
  assert.equal(matchesAge('2026-11-02T00:00:00Z', '1', now), true);
  assert.equal(matchesAge('2026-11-01T23:59:59Z', '1', now), false);
  assert.equal(matchesAge('2026-11-03T00:00:01Z', '7', now), false);
  assert.equal(matchesAge(null, '7', now), false);
  assert.equal(matchesAge(null, 'all', now), true);
  assert.equal(matchesAge('invalid', 'all', now), true);
  assert.equal(matchesAge('2026-11-03T00:00:00Z', '0', now), false);
  assert.equal(matchesAge('2026-11-03T00:00:00Z', '1.5', now), false);
});

test('hidden selections remain counted after a filter', () => {
  assert.equal(hiddenSelectionCount(new Set([1, 2, 9]), [{id: 1}, {id: 3}]), 2);
  assert.equal(hiddenSelectionCount(new Set(), [{id: 1}]), 0);
});
