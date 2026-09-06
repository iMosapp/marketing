// The platform's pre-completion linter loads eslint-config-expo / eslint-plugin-expo from the
// global node_modules, which this image does not ship. Link them from the app on every start.
const fs = require('fs');
const path = require('path');

const globalDir = '/usr/lib/node_modules';
for (const name of ['eslint-config-expo', 'eslint-plugin-expo']) {
  const target = path.join(__dirname, '..', 'node_modules', name);
  const link = path.join(globalDir, name);
  try {
    if (fs.existsSync(target) && !fs.existsSync(link)) fs.symlinkSync(target, link, 'dir');
  } catch (e) {
    // best effort only
  }
}
