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

if (typeof module !== 'undefined' && module.exports) {
  module.exports = {bindPublicationFields, hasPendingPublicationUrl};
}
