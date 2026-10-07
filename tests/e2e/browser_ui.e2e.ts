import { describe, test } from '@e2e-dev/web';
import { expect } from 'e2e';

describe('TechVerse OS Browser & Swagger Interface E2E', { tags: ['browser', 'ui'] }, () => {
  test('FastAPI OpenAPI Swagger documentation loads in Chromium browser', async ({ app, screen, browser }) => {
    await app.open('/docs');
    await expect(browser).toHaveURL('/docs');
    
    // Check that Swagger UI title heading and sections are rendered
    await expect(screen.getByRole('heading', /TechVerse AI Client Acquisition OS/)).toBeVisible();
    await expect(screen.getByRole('heading', /Conversations/)).toBeVisible();
    await expect(screen.getByRole('heading', /Outreach Intelligence/)).toBeVisible();
  });

  test('Root health probe is directly reachable and serves healthy status in browser', async ({ app, browser }) => {
    await app.open('/health');
    await expect(browser).toHaveURL('/health');
    
    const bodyText = await browser.evaluate(() => document.body.innerText);
    expect(bodyText).toContain('status');
  });
});
