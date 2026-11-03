'use strict';

// Keep the unsaved publication URL attached to the draft being displayed.
function bindPublicationFields(previousDraft, draft, input, publishedLink) {
  if (!previousDraft || previousDraft.id !== draft.id || draft.status === 'published') {
    input.value = '';
  }
  if (draft.status === 'published' && draft.post_url) publishedLink.href = draft.post_url;
  else publishedLink.removeAttribute('href');
}

function hasPendingPublicationUrl(draft, input) {
  return Boolean(draft && draft.status === 'approved' && input.value.trim());
}

function sectionDiffers(fields, original) {
  return fields.some((field, index) =>
    (field.type === 'checkbox' ? field.checked : field.value) !== original[index]);
}

async function withInertTargets(targets, action) {
  const previous = targets.map(target => target.inert);
  targets.forEach(target => { target.inert = true; });
  try { return await action(); }
  finally { targets.forEach((target, index) => { target.inert = previous[index]; }); }
}

function verifiedCopyText(shown, current, position) {
  if (!Number.isInteger(shown.approval_id) || current.approval_id !== shown.approval_id ||
      typeof shown.posts[position] !== 'string' || current.posts?.[position] !== shown.posts[position]) {
    throw new Error('Bản duyệt đã thay đổi. Hãy giữ phần đang sửa và tải lại trước khi sao chép.');
  }
  return current.posts[position];
}

function conflictTargetUrl(target) {
  if (!target || typeof target !== 'object') return null;
  const fields = target.kind === 'publication' ? ['bulletin_id', 'variant_id', 'publication_id', 'position'] :
    target.kind === 'legacy_draft' ? ['draft_id'] : null;
  if (!fields || fields.some(key => !Number.isSafeInteger(target[key]) || target[key] < (key === 'position' ? 0 : 1))) return null;
  const params = new URLSearchParams({kind: target.kind});
  fields.forEach(key => params.set(key, String(target[key])));
  return `/?${params}`;
}

function parseConflictTarget(search) {
  const params = new URLSearchParams(search);
  const kind = params.get('kind');
  const fields = kind === 'publication' ? ['bulletin_id', 'variant_id', 'publication_id', 'position'] :
    kind === 'legacy_draft' ? ['draft_id'] : null;
  if (!fields || params.getAll('kind').length !== 1 || fields.some(key => params.getAll(key).length !== 1 || !/^(0|[1-9]\d*)$/.test(params.get(key)))) return null;
  const target = {kind};
  fields.forEach(key => { target[key] = Number(params.get(key)); });
  return conflictTargetUrl(target) ? target : null;
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = {bindPublicationFields, hasPendingPublicationUrl, sectionDiffers, withInertTargets, verifiedCopyText, conflictTargetUrl, parseConflictTarget};
}
