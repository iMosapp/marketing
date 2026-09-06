# "JavaScript linting failed due to a linter engine error" (blocks finish / ask_human)

Root cause (found Sep 2026): the platform pre-completion check runs the global ESLint with
/opt/plugins-venv/lib/python3.11/site-packages/linters/frontend/eslint.expo.config.js whenever the FIRST
changed file lives under the Expo app (/app/frontend). That config imports `eslint-config-expo` from the
global node_modules (/usr/lib/node_modules), which the base image does not ship, so ESLint crashes
("Cannot find package 'eslint-config-expo'") = engine error. When the first changed file is backend/other,
the standard config is used and the check passes, which is why it looked random.

Fix (re-apply in a fresh container if the error comes back):

    ln -s /app/frontend/node_modules/eslint-config-expo /usr/lib/node_modules/eslint-config-expo

Verify with the exact harness command:

    cd /app && L=/opt/plugins-venv/lib/python3.11/site-packages/linters && \
    eslint --format=$L/node_modules/eslint-formatter-unix/index.js --config $L/frontend/eslint.expo.config.js \
      --ignore-pattern "**/node_modules/**" frontend/app/inventory.tsx

Lint findings do not block; only an engine crash does. Also done: /app/eslint.config.js (root) so eslint resolves
from any cwd, and /app/frontend/eslint.config.js disables the 4 slow import/* rules (full lint 100s -> 12s).
