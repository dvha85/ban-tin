'use strict';

// These are editorial prompts, not a measure of source reliability.
function sourceWarnings(source, now = Date.now()) {
  const warnings = [];
  const summary = typeof source.summary === 'string' ? source.summary.trim() : '';
  if (!summary) warnings.push('Nguồn chưa có trích đoạn hoặc ghi chú.');
  else if ([...summary].length < 80) warnings.push('Trích đoạn hoặc ghi chú ngắn hơn 80 ký tự.');
  const timestamp = source.published_at ? Date.parse(source.published_at) : NaN;
  if (!Number.isFinite(timestamp)) warnings.push('Chưa rõ ngày nguồn.');
  else if (timestamp > now) warnings.push('Ngày nguồn ở tương lai; hãy kiểm tra lại.');
  else if (now - timestamp > 7 * 86400000) warnings.push('Nguồn đã quá 7 ngày; hãy kiểm tra cập nhật.');
  return warnings;
}

if (typeof module !== 'undefined' && module.exports) module.exports = {sourceWarnings};
