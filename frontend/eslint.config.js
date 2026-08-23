import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import { defineConfig, globalIgnores } from 'eslint/config'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{js,jsx}'],
    extends: [
      js.configs.recommended,
      // eslint-plugin-react-hooks v5 exposes its flat config as
      // 'recommended-latest'. `configs.flat` does not exist in v5, so
      // reading `.recommended` off it threw before any file was linted.
      reactHooks.configs['recommended-latest'],
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      globals: globals.browser,
      parserOptions: { ecmaFeatures: { jsx: true } },
    },
    rules: {
      // Core `no-unused-vars` does not count a binding referenced only
      // from JSX as used -- that is `react/jsx-uses-vars`, and
      // eslint-plugin-react is not a dependency here. Without this,
      // every imported component in every file is reported unused and
      // the genuinely useful rules (react-hooks) are lost in the noise.
      // Components and hooks are PascalCase by convention, so ignoring
      // that shape is enough; ordinary lowercase variables are still
      // checked normally.
      // `argsIgnorePattern` covers the polymorphic `as: As = 'div'`
      // parameter the primitives use, which is likewise only ever
      // referenced from JSX.
      'no-unused-vars': [
        'error',
        { varsIgnorePattern: '^[A-Z]', argsIgnorePattern: '^[A-Z]' },
      ],
    },
  },
  {
    // These modules intentionally export helpers next to their provider
    // or component (a context's own hook, the shared tone table, the
    // notification formatters). That costs a little HMR granularity in
    // development and nothing else, so the rule is switched off here
    // rather than the code being split to satisfy it.
    files: [
      'src/context/*.jsx',
      'src/components/ui.jsx',
      'src/components/ui/primitives.jsx',
      'src/components/DocumentSections.jsx',
    ],
    rules: { 'react-refresh/only-export-components': 'off' },
  },
])
