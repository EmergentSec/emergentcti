import { describe, expect, it } from 'vitest';

// `destructive-foreground` (--on-destructive) is the text color for content ON
// a destructive fill. Standalone error copy must use `text-destructive`.
const sources = import.meta.glob('/src/**/*.{ts,tsx}', {
  query: '?raw',
  import: 'default',
  eager: true,
}) as Record<string, string>;

/** Every quoted/back-ticked string literal that mentions the class. */
function offendingLiterals(code: string): string[] {
  const literals = code.match(/(['"`])(?:(?!\1)[^\\]|\\.)*?\1/g) ?? [];
  return literals.filter(
    (lit) => /\btext-destructive-foreground\b/.test(lit) && !/\bbg-destructive\b/.test(lit),
  );
}

describe('destructive text tokens', () => {
  it('scans the source tree', () => {
    expect(Object.keys(sources).length).toBeGreaterThan(20);
  });

  it('uses text-destructive-foreground only alongside bg-destructive', () => {
    const offenders = Object.entries(sources)
      .filter(([file]) => !file.endsWith('destructiveTokens.test.ts'))
      .flatMap(([file, code]) => offendingLiterals(code).map((lit) => `${file}: ${lit}`));
    expect(offenders).toEqual([]);
  });
});
