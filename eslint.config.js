// Root ESLint config: lets `eslint` resolve when run from /app or any subfolder without its own config.
const frontend = require('/app/frontend/eslint.config.js');

module.exports = [
  {
    ignores: [
      '**/node_modules/**', '**/*.html', '**/*.min.js',
      'frontend/dist/**', 'frontend/.expo/**', 'frontend/.metro-cache/**', 'frontend/public/**', 'frontend/plugins/**', 'frontend/scripts/**', 'frontend/craco.config.js',
      'marketing/**', 'backend/**', 'memory/**', 'test_reports/**', 'tests/**',
    ],
  },
  ...frontend,
];
