---
name: js-ts-dev
description: JavaScript/TypeScript development workflow — npm/pnpm, testing with vitest/jest, linting with eslint, type checking, and bundling
license: MIT
compatibility: opencode
metadata:
  audience: developers
  language: javascript
---

## What I do

Full JavaScript/TypeScript development workflow with modern tooling.

## When to use me

- Writing JavaScript/TypeScript code
- Running tests
- Linting and formatting
- Type checking
- Building and bundling

## Toolchain

```bash
# Install deps
npm install
pnpm install
yarn install

# Run tests
npm test
pnpm test
vitest run
jest

# Lint
npm run lint
eslint src/
pnpm lint

# Format
npm run format
prettier --write src/
pnpm format

# Type check
npm run typecheck
tsc --noEmit
pnpm typecheck

# Build
npm run build
pnpm build
tsc

# Dev server
npm run dev
pnpm dev
```

## Package.json Scripts

```json
{
  "scripts": {
    "dev": "tsx watch src/index.ts",
    "build": "tsc",
    "start": "node dist/index.js",
    "test": "vitest run",
    "test:watch": "vitest",
    "test:coverage": "vitest run --coverage",
    "lint": "eslint src/",
    "lint:fix": "eslint src/ --fix",
    "format": "prettier --write src/",
    "typecheck": "tsc --noEmit"
  }
}
```

## Testing with Vitest

```typescript
import { describe, it, expect, vi } from 'vitest';
import { myFunction } from './mylib';

describe('myFunction', () => {
  it('should do something', () => {
    const result = myFunction(1);
    expect(result).toBe(2);
  });

  it('should handle edge cases', () => {
    expect(() => myFunction(-1)).toThrow('Invalid input');
  });

  it('should mock dependencies', () => {
    const mock = vi.fn().mockReturnValue(42);
    // Use mock
  });
});
```

## Testing with Jest

```typescript
import { myFunction } from './mylib';

describe('myFunction', () => {
  it('should do something', () => {
    const result = myFunction(1);
    expect(result).toBe(2);
  });

  it('should handle edge cases', () => {
    expect(() => myFunction(-1)).toThrow('Invalid input');
  });
});
```

## TypeScript Configuration

```json
// tsconfig.json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "NodeNext",
    "moduleResolution": "NodeNext",
    "lib": ["ES2022"],
    "outDir": "./dist",
    "rootDir": "./src",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true,
    "resolveJsonModule": true,
    "declaration": true,
    "declarationMap": true,
    "sourceMap": true
  },
  "include": ["src/**/*"],
  "exclude": ["node_modules", "dist", "**/*.test.ts"]
}
```

## ESLint Configuration

```javascript
// eslint.config.js
import js from '@eslint/js';
import tseslint from 'typescript-eslint';

export default [
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    rules: {
      '@typescript-eslint/no-unused-vars': 'error',
      '@typescript-eslint/explicit-function-return-type': 'warn',
      '@typescript-eslint/no-explicit-any': 'error',
    },
  },
];
```

## Prettier Configuration

```json
// .prettierrc
{
  "semi": true,
  "trailingComma": "es5",
  "singleQuote": true,
  "printWidth": 80,
  "tabWidth": 2
}
```

## Monorepo with pnpm

```yaml
# pnpm-workspace.yaml
packages:
  - 'packages/*'
  - 'apps/*'
```

```json
// package.json
{
  "scripts": {
    "dev": "pnpm -r --parallel run dev",
    "build": "pnpm -r run build",
    "test": "pnpm -r run test"
  }
}
```

## Rules

- **Use TypeScript** — no plain JavaScript for new code
- **Strict mode** — enable all strict checks
- **Run typecheck before commit** — no type errors
- **Run lint before commit** — no warnings
- **Run tests before commit** — all tests pass
- **Use vitest** — faster than jest for ESM
- **Pin dependencies** — use lockfiles
- **Document public APIs** — JSDoc comments
