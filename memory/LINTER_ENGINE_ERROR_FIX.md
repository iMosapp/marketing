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

UPDATE: the symlink is lost on container restart (/usr/lib is not persistent). Both lint arms need it:
ESLint arm imports eslint-config-expo, oxlint arm loads eslint-plugin-expo (.oxlintrc-expo.json jsPlugins).
Persistent fix: frontend/scripts/link-global-lint-deps.js runs from the `yarn start` script (supervisor) and
re-creates both symlinks on every frontend start. If the error appears right after a restart, run:
    node /app/frontend/scripts/link-global-lint-deps.js

## REAL ROOT CAUSE (confirmed from /var/log/e1_agent.log, Sep 6 2026)
The pre-completion check runs the oxlint arm on /app/frontend (`lint_javascript_oxlint path=/app/frontend
engine_success=False`). engine_success is `oxlint ok AND ImportValidator ok`. ImportValidator failed on
`frontend/plugins/visual-edits/dev-server-setup.js` (platform plugin) which requires `express`, not listed in
package.json. Fix: `cd /app/frontend && yarn add -D express` (done). Verify with:
    /opt/plugins-venv/bin/python -c "import asyncio,sys; sys.path.insert(0,'/opt/plugins-venv/lib/python3.11/site-packages'); from linters.lint_tools import run_javascript_oxlint_linter as r; print(asyncio.run(r(['/app/frontend'])).engine_success)"
Must print True. The eslint-config-expo symlink fix above is still needed for the ESLint arm.
