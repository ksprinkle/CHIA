/* eslint-env node */
module.exports = {
  root: true,
  env: { browser: true, es2022: true, node: true },
  parser: '@typescript-eslint/parser',
  parserOptions: {
    ecmaVersion: 2022,
    sourceType: 'module',
    ecmaFeatures: { jsx: true },
  },
  plugins: ['@typescript-eslint', 'react', 'react-hooks', 'jsx-a11y'],
  extends: [
    'eslint:recommended',
    'plugin:@typescript-eslint/recommended',
    'plugin:react/recommended',
    'plugin:react/jsx-runtime',
    'plugin:react-hooks/recommended',
    'plugin:jsx-a11y/recommended',
  ],
  settings: { react: { version: 'detect' } },
  ignorePatterns: ['dist', 'coverage', 'node_modules'],
  rules: {
    // TypeScript provides prop typing.
    'react/prop-types': 'off',
    // Allow the standard skip-link focus target pattern (tabIndex={-1} on <main>).
    'jsx-a11y/no-noninteractive-tabindex': [
      'warn',
      { tags: [], roles: ['tabpanel'], allowExpressionValues: true },
    ],
  },
  overrides: [
    {
      files: ['**/*.test.ts', '**/*.test.tsx', 'src/test/**/*'],
      env: { node: true },
    },
  ],
}
