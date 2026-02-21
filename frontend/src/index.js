import React from 'react';
import ReactDOM from 'react-dom/client';
import { registerRootComponent } from 'expo';
import App from './App';
import './index.css';

// For web, we need to manually mount the app
const rootElement = document.getElementById('root');
if (rootElement) {
  const root = ReactDOM.createRoot(rootElement);
  root.render(
    <React.StrictMode>
      <App />
    </React.StrictMode>
  );
}

// Register for Expo
registerRootComponent(App);
