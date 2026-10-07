import type { E2EConfig } from 'e2e';
import { web } from '@e2e-dev/web';

export default {
  tests: 'tests/e2e/**/*.e2e.ts',
  timeout: 60000,
  targets: [
    {
      engine: web(),
      app: {
        url: 'http://127.0.0.1:8000',
        command: {
          executable: '.venv/Scripts/python.exe',
          args: ['-m', 'uvicorn', 'services.api.app.main:app', '--host', '127.0.0.1', '--port', '{port}'],
          log: '.e2e/logs/app.log',
          reuseExisting: true,
        },
      },
    },
  ],
} satisfies E2EConfig;
