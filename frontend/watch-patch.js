// Patch fs.watch to use polling instead of inotify (container kernel limit).
// Directories under the app source are scanned entry-by-entry so EDITS to existing files are seen
// (a directory's own mtime only changes on add/remove, which is why edits used to go unnoticed).
const fs = require('fs');
const path = require('path');
const EventEmitter = require('events');

const watching = new Map();
const APP_ROOT = process.cwd();
const SHALLOW = /node_modules|\.git|\.metro-cache|\.expo/;

function snapshot(dir) {
  const out = new Map();
  let names = [];
  try { names = fs.readdirSync(dir); } catch (_e) { return out; }
  for (const n of names) {
    try {
      const st = fs.statSync(path.join(dir, n));
      if (st.isFile()) out.set(n, st.mtimeMs);
      else if (st.isDirectory()) out.set(n, -1);
    } catch (_e) {}
  }
  return out;
}

fs.watch = function (filename, options, listener) {
  if (typeof options === 'function') { listener = options; options = {}; }
  options = options || {};

  const emitter = new EventEmitter();
  if (listener) emitter.on('change', listener);
  const key = filename;
  if (watching.has(key)) return emitter;

  let isDir = false;
  try { isDir = fs.statSync(filename).isDirectory(); } catch (_e) {}
  const deep = isDir && filename.startsWith(APP_ROOT) && !SHALLOW.test(filename);

  let prevMtime = 0;
  let prev = deep ? snapshot(filename) : null;
  try { prevMtime = fs.statSync(filename).mtimeMs; } catch (_e) {}

  const interval = setInterval(() => {
    try {
      const stat = fs.statSync(filename);
      if (deep) {
        const cur = snapshot(filename);
        for (const [n, m] of cur) {
          if (!prev.has(n)) emitter.emit('change', 'rename', n);
          else if (prev.get(n) !== m) emitter.emit('change', 'change', n);
        }
        for (const n of prev.keys()) if (!cur.has(n)) emitter.emit('change', 'rename', n);
        prev = cur;
      } else if (stat.mtimeMs !== prevMtime) {
        prevMtime = stat.mtimeMs;
        emitter.emit('change', 'change', isDir ? null : path.basename(filename));
      }
    } catch (_e) {
      clearInterval(interval);
      watching.delete(key);
    }
  }, 2000);

  watching.set(key, interval);
  emitter.close = function () { clearInterval(interval); watching.delete(key); };
  return emitter;
};
