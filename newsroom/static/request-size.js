'use strict';

// Keep in sync with server.MAX_BODY; count the actual UTF-8 JSON payload.
function requestJson(body) {
  const json = JSON.stringify(body);
  if (new TextEncoder().encode(json).length > 128000) {
    throw new Error('Dữ liệu gửi vượt 128.000 byte UTF-8. Hãy rút ngắn nội dung hoặc lưu từng phần.');
  }
  return json;
}

if (typeof module !== 'undefined' && module.exports) module.exports = {requestJson};
