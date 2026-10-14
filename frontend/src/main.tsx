import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'

// Service Worker Lifecycle Management
if (typeof window !== 'undefined' && 'serviceWorker' in navigator) {
  if (import.meta.env.DEV) {
    // In development: never register SW. Actively unregister any stale SW to prevent HMR or module loading issues.
    navigator.serviceWorker.getRegistrations().then((registrations) => {
      for (const reg of registrations) {
        reg.unregister().then(() => {
          console.log('[CarePill Dev] Unregistered stale service worker for origin:', window.location.origin);
        }).catch((err) => {
          console.warn('[CarePill Dev] SW unregister error:', err);
        });
      }
    });
  } else if (import.meta.env.PROD) {
    // In production: safely register PWA service worker
    window.addEventListener('load', () => {
      navigator.serviceWorker
        .register('/sw.js')
        .then((reg) => {
          console.log('[CarePill PWA] SW registered:', reg.scope);
        })
        .catch((err) => {
          console.warn('[CarePill PWA] SW registration failed:', err);
        });
    });
  }
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
