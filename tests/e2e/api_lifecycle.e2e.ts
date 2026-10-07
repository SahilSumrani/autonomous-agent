import { describe, test } from '@e2e-dev/web';
import { expect } from 'e2e';

describe('TechVerse OS Full API & Intelligence Lifecycle E2E', { tags: ['api', 'lifecycle'] }, () => {
  const orgId = '00000000-0000-0000-0000-000000000001';
  const defaultHeaders = {
    'Content-Type': 'application/json',
    'X-Organization-Id': orgId,
  };

  test('Health check endpoints report healthy status', async ({ app }) => {
    // 1. Root health probe
    const rootRes = await fetch(new URL('/health', app.baseUrl));
    expect(rootRes.status).toBe(200);
    const rootData = await rootRes.json();
    expect(rootData).toHaveProperty('status');
    expect(rootData).toHaveProperty('environment');

    // 2. API v1 health probe
    const v1Res = await fetch(new URL('/api/v1/health', app.baseUrl));
    expect(v1Res.status).toBe(200);
    const v1Data = await v1Res.json();
    expect(v1Data).toHaveProperty('status');
    expect(v1Data).toHaveProperty('database');
    expect(v1Data).toHaveProperty('redis');
  });

  test('OpenAPI specification is published and describes all Phase 0-7 routes', async ({ app }) => {
    const specRes = await fetch(new URL('/openapi.json', app.baseUrl));
    expect(specRes.status).toBe(200);
    const spec = await specRes.json();
    expect(spec.openapi).toContain('3.');
    expect(spec.info.title).toContain('TechVerse');
    expect(spec.paths).toHaveProperty('/health');
    expect(spec.paths).toHaveProperty('/api/v1/agent/browser/challenge');
    expect(spec.paths).toHaveProperty('/api/v1/agent/browser/pair');
    expect(spec.paths).toHaveProperty('/api/v1/agent/tools');
  });

  test('Browser Agent Tools Registry exposes registered browser capabilities', async ({ app }) => {
    const res = await fetch(new URL('/api/v1/agent/tools', app.baseUrl));
    expect(res.status).toBe(200);
    const tools = await res.json();
    expect(typeof tools).toBe('object');
    const toolNames = Object.keys(tools);
    expect(toolNames.length).toBeGreaterThan(0);
    expect(tools).toHaveProperty('open_page');
    expect(tools).toHaveProperty('navigate');
    expect(tools).toHaveProperty('extract_visible_content');
    expect(tools).toHaveProperty('execute_approved_outreach');
  });

  test('Browser Gateway generates single-use pairing challenge for Chrome extension', async ({ app }) => {
    const res = await fetch(new URL('/api/v1/agent/browser/challenge', app.baseUrl), {
      method: 'POST',
      headers: defaultHeaders,
    });
    expect(res.status).toBe(200);
    const challenge = await res.json();
    expect(challenge).toHaveProperty('pairing_code');
    expect(challenge).toHaveProperty('expires_at');
    expect(challenge.pairing_code.length).toBeGreaterThan(0);
  });

  test('Browser Gateway status probe reports real-time connection state', async ({ app }) => {
    const res = await fetch(new URL('/api/v1/agent/browser/status', app.baseUrl), {
      headers: defaultHeaders,
    });
    expect(res.status).toBe(200);
    const status = await res.json();
    expect(status).toHaveProperty('organization_id');
    expect(status).toHaveProperty('is_connected');
    expect(status).toHaveProperty('session_state');
    expect(status.organization_id).toBe(orgId);
  });
});
