import { loadEnv } from 'vite';
import type { ReleaseEnvironment } from '../src/content/types';

export const caseStudyViteMode = 'development';

export function loadViteReleaseEnvironment(cwd = process.cwd()): ReleaseEnvironment {
  return loadEnv(caseStudyViteMode, cwd, 'VITE_');
}
