// @ts-nocheck
import { ScrollViewStyleReset } from "expo-router/html";
import type { PropsWithChildren } from "react";

export default function Root({ children }: PropsWithChildren) {
  return (
    <html lang="en" style={{ height: "100%", backgroundColor: "#000000" }}>
      <head>
        <meta charSet="utf-8" />
        <meta httpEquiv="X-UA-Compatible" content="IE=edge" />
        <meta
          name="viewport"
          content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no, shrink-to-fit=no, viewport-fit=cover"
        />
        <title>i'M On Social</title>
        {/* Open Graph / iMessage Link Previews */}
        <meta property="og:title" content="i'M On Social" />
        <meta property="og:description" content="Your all-in-one relationship management system" />
        <meta property="og:image" content="/logo512.png" />
        <meta property="og:type" content="website" />
        <meta name="twitter:card" content="summary" />
        <meta name="twitter:image" content="/logo512.png" />
        {/* PWA  - must be in static HTML for iOS standalone mode */}
        <meta name="apple-mobile-web-app-capable" content="yes" />
        <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent" />
        <meta name="apple-mobile-web-app-title" content="i'M On Social" />
        <meta name="mobile-web-app-capable" content="yes" />
        <meta name="theme-color" content="#007AFF" />
        <meta name="format-detection" content="telephone=no" />
        <link rel="manifest" href="/manifest.json" />
        <link rel="icon" href="/favicon.ico" />
        <link rel="apple-touch-icon" href="/apple-touch-icon.png" />
        {/* Splash screen hints for iOS */}
        <meta name="apple-mobile-web-app-orientations" content="portrait" />
        {/*
          Disable body scrolling on web to make ScrollView components work correctly.
          If you want to enable scrolling, remove `ScrollViewStyleReset` and
          set `overflow: auto` on the body style below.
        */}
        <ScrollViewStyleReset />
        <style
          dangerouslySetInnerHTML={{
            __html: `
              html, body { background-color: #000000 !important; }
              body > div:first-child { position: fixed !important; top: 0; left: 0; right: 0; bottom: 0; }
              [role="tablist"] [role="tab"] * { overflow: visible !important; }
              [role="heading"], [role="heading"] * { overflow: visible !important; display: none !important; }
              /* Prevent iOS Safari from zooming in on input focus (happens when font-size < 16px) */
              input, textarea, select { font-size: 16px !important; }
              /* iOS safe area  - fill the bottom home indicator area with black */
              @supports(padding: env(safe-area-inset-bottom)) {
                body { padding-bottom: env(safe-area-inset-bottom); }
              }
            `,
          }}
        />
      </head>
      <body
        style={{
          margin: 0,
          height: "100%",
          overflow: "hidden",
          display: "flex",
          flexDirection: "column",
          backgroundColor: "#000000",
        }}
      >
        {children}
        {/* Register service worker on ALL routes  - critical for iOS PWA standalone mode */}
        <script
          dangerouslySetInnerHTML={{
            __html: `
              if ('serviceWorker' in navigator) {
                navigator.serviceWorker.register('/sw.js').catch(function() {});
              }
            `,
          }}
        />
      </body>
    </html>
  );
}
