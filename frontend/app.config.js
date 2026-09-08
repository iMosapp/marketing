const fs = require('fs');
const path = require('path');

// app.json is the source of truth; this only adds Firebase config for Android push when the file exists.
module.exports = ({ config }) => {
  const googleServices = path.join(__dirname, 'google-services.json');
  if (fs.existsSync(googleServices)) {
    config.android = { ...config.android, googleServicesFile: './google-services.json' };
  }
  return config;
};
