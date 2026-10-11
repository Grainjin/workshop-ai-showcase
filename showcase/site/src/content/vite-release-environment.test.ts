import { mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { afterEach, describe, expect, it } from 'vitest';
import { loadViteReleaseEnvironment } from '../../e2e/vite-release-environment';

const originalDemoUrl = process.env.VITE_DEMO_URL;
const temporaryDirectories: string[] = [];

afterEach(() => {
  if (originalDemoUrl === undefined) delete process.env.VITE_DEMO_URL;
  else process.env.VITE_DEMO_URL = originalDemoUrl;
  for (const directory of temporaryDirectories.splice(0)) rmSync(directory, { recursive: true, force: true });
});

function temporaryEnvironment(contents: string): string {
  const directory = mkdtempSync(join(tmpdir(), 'case-study-vite-env-'));
  temporaryDirectories.push(directory);
  writeFileSync(join(directory, '.env.development'), contents);
  return directory;
}

describe('loadViteReleaseEnvironment', () => {
  it('loads release targets from the same mode-specific env files as the Vite server', () => {
    delete process.env.VITE_DEMO_URL;
    const directory = temporaryEnvironment('VITE_DEMO_URL=https://file.example/demo\n');

    expect(loadViteReleaseEnvironment(directory).VITE_DEMO_URL).toBe('https://file.example/demo');
  });

  it('preserves Vite precedence when a process variable overrides the env file', () => {
    process.env.VITE_DEMO_URL = 'https://process.example/demo';
    const directory = temporaryEnvironment('VITE_DEMO_URL=https://file.example/demo\n');

    expect(loadViteReleaseEnvironment(directory).VITE_DEMO_URL).toBe('https://process.example/demo');
  });
});
