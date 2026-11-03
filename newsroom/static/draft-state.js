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

if (typeof module !== 'undefined' && module.exports) {
  module.exports = {bindPublicationFields, hasPendingPublicationUrl, sectionDiffers, withInertTargets, verifiedCopyText};
}
