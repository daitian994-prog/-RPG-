const requested = new URLSearchParams(window.location.search).get('debug') === '1'

// Vite removes this branch from production builds. There is deliberately no
// player-facing switch: local developers opt in with ?debug=1.
export const debugMode = Boolean(import.meta.env.DEV && requested)

export const withDebug = path => debugMode
  ? `${path}${path.includes('?') ? '&' : '?'}debug=true`
  : path
