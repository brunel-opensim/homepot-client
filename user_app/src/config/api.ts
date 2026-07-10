const configuredApiBaseUrl = import.meta.env.VITE_API_BASE_URL

export const apiBaseUrl = (
  configuredApiBaseUrl || 'http://localhost:8000/api/v1'
).replace(/\/$/, '')
