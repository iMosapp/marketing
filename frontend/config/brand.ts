/**
 * Universal branding config — single source of truth.
 * Uses environment variables so it works across preview, staging, and production.
 */
const _base = (process.env.EXPO_PUBLIC_BACKEND_URL || process.env.REACT_APP_BACKEND_URL || 'https://app.imonsocial.com').replace(/\/api$/, '');

export const BRAND = {
  name: "I'm On Social",
  poweredByText: "Powered by VI Ventures Group LLC",
  url: `${_base}/imos`,
  domain: _base.replace(/^https?:\/\//, '') + '/imos',
};
