// Patch fs.watch to use polling instead of inotify (container kernel limit)
const fs = require('fs');
const EventEmitter = require('events');

const origWatch = fs.watch;
const watching = new Map();

fs.watch = function(filename, options, listener) {
  if (typeof options === 'function') {
    listener = options;
    options = {};
  }
  options = options || {};
  
  const emitter = new EventEmitter();
  if (listener) emitter.on('change', listener);
  
  const key = filename;
  if (watching.has(key)) {
    return emitter;
  }
  
  let prevMtime = 0;
  try { prevMtime = fs.statSync(filename).mtimeMs; } catch(e) {}
  
  const interval = setInterval(() => {
    try {
      const stat = fs.statSync(filename);
      if (stat.mtimeMs !== prevMtime) {
        prevMtime = stat.mtimeMs;
        emitter.emit('change', 'change', filename);
      }
    } catch(e) {
      clearInterval(interval);
      watching.delete(key);
    }
  }, 3000);
  
  watching.set(key, interval);
  
  emitter.close = function() {
    clearInterval(interval);
    watching.delete(key);
  };
  
  return emitter;
};
