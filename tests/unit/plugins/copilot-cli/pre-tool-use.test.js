'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const { decide } = require(
  '../../../../src/aegis/plugins/copilot-cli/hooks/pre-tool-use.js'
);

test('Copilot decide: five-stage pipeline can require confirmation', async () => {
  const originalFetch = global.fetch;
  global.fetch = async (url, options = {}) => {
    if (String(url).includes('synced-overrides')) {
      return { ok: true, json: async () => ({ synced: [] }) };
    }
    if (String(url).includes('/api/runtime/pretool/decide')) {
      const body = JSON.parse(options.body);
      assert.equal(body.runtime_kind, 'copilot-cli');
      return {
        ok: true,
        json: async () => ({
          action: 'confirm', risk_score: 40, drift_score: 40,
          reason: 'Capability confirmation', signals: [{ layer: 'capability' }],
        }),
      };
    }
    throw new Error(`unexpected URL ${url}`);
  };
  try {
    const result = await decide('view', 'http://127.0.0.1:8741', 's1', { path: 'README.md' });
    assert.equal(result.decision, 'ask');
    assert.equal(result.pipeline.drift_score, 40);
  } finally {
    global.fetch = originalFetch;
  }
});
