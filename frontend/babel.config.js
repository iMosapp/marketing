module.exports = function (api) {
  api.cache(true);
  return {
    presets: ['babel-preset-expo'],
    plugins: ['./babel-plugin-max-font.js', './babel-plugin-keyboard.js', './babel-plugin-modal-kav.js', './babel-plugin-testid.js'],
  };
};
