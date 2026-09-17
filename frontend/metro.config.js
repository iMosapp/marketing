const { getDefaultConfig } = require("expo/metro-config");
const path = require('path');
const { FileStore } = require('metro-cache');

const config = getDefaultConfig(__dirname);

const root = process.env.METRO_CACHE_ROOT || path.join(__dirname, '.metro-cache');
config.cacheStores = [
  new FileStore({ root: path.join(root, 'cache') }),
];

config.watcher = {
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

// react-native-webrtc imports "event-target-shim/index", which the package's exports map (v6) does not list.
const baseResolveRequest = config.resolver.resolveRequest;
config.resolver.resolveRequest = (context, moduleName, platform) => {
  const name = moduleName === 'event-target-shim/index' ? 'event-target-shim' : moduleName;
  return baseResolveRequest ? baseResolveRequest(context, name, platform) : context.resolveRequest(context, name, platform);
};

module.exports = config;
