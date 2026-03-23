const { getDefaultConfig } = require("expo/metro-config");
const path = require('path');
const { FileStore } = require('metro-cache');

const config = getDefaultConfig(__dirname);

const root = process.env.METRO_CACHE_ROOT || path.join(__dirname, '.metro-cache');
config.cacheStores = [
  new FileStore({ root: path.join(root, 'cache') }),
];

config.watcher = {
  watchman: { enabled: false },
  healthCheck: { enabled: false },
};

// Heavily reduce watched dirs - skip native code
config.resolver = {
  ...config.resolver,
  blockList: [
    /node_modules\/.*\/android\/.*/,
    /node_modules\/.*\/ios\/.*/,
    /node_modules\/.*\/__tests__\/.*/,
    /node_modules\/.*\/__fixtures__\/.*/,
    /node_modules\/react-native\/types_generated\/.*/,
    /\.git\/.*/,
  ],
};

config.maxWorkers = 2;

module.exports = config;
