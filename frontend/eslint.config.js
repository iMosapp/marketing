// https://docs.expo.dev/guides/using-eslint/
const { defineConfig } = require('eslint/config');
const expoConfig = require('eslint-config-expo/flat');

module.exports = defineConfig([
  expoConfig,
  {
    ignores: ['dist/*', '.metro-cache/*', 'node_modules/*', 'public/*', 'plugins/*', '.expo/*', 'scripts/*', 'craco.config.js'],
  },
  {
    rules: {
      // these four parse every imported module's exports (walks node_modules) and made a full lint take ~100s; no-unresolved stays
      'import/namespace': 'off',
      'import/default': 'off',
      'import/export': 'off',
      'import/named': 'off',
      'react/no-unescaped-entities': 'off',
      'react/display-name': 'off',
    },
  },
]);
