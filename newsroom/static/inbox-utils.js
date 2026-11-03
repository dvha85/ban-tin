'use strict';

function matchesAge(publishedAt, days, now = Date.now()) {
  if (days === 'all') return true;
  const limit = Number(days);
  const date = publishedAt ? Date.parse(publishedAt) : NaN;
  if (!Number.isFinite(limit) || limit <= 0 || !Number.isInteger(limit) || !Number.isFinite(date)) return false;
  const age = now - date;
  return age >= 0 && age <= limit * 86400000;
}

function hiddenSelectionCount(selected, visible) {
  const visibleIds = new Set(visible.map(article => article.id));
  return [...selected].filter(id => !visibleIds.has(id)).length;
}

if (typeof module !== 'undefined' && module.exports) module.exports = {matchesAge, hiddenSelectionCount};
