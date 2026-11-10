// frontend/js/api.js
// Wrapper centralizado de fetch. Ninguna otra página debe llamar fetch() directamente.

// When Flask serves the pages (Docker, Render) the API is on the same origin: relative URLs.
// Only a separate static server (Live Server on 5500/5501, or file://) points at Flask on :5000.
const STATIC_DEV_SERVER = window.location.protocol === 'file:' || ['5500', '5501'].includes(window.location.port);
const API_HOST = ['localhost', '127.0.0.1'].includes(window.location.hostname)
  ? window.location.hostname
  : '127.0.0.1';
const API_BASE_URL = STATIC_DEV_SERVER ? `http://${API_HOST}:5000` : '';
const LOGIN_ENDPOINT = '/api/auth/login';

// Security: the JWT lives in sessionStorage so it disappears when the tab closes, and it is
// only ever sent in the Authorization header. Any script on the page could read it, so
// rendered data must stay escaped (see esc() in ui.js) and tokens are short-lived.
function guardarSesion(data) {
  sessionStorage.setItem('access_token', data.access_token);
  sessionStorage.setItem('user_id', data.user_id);
  sessionStorage.setItem('role', data.role);
}

function cerrarSesionLocal() {
  sessionStorage.clear();
}

function irAlLogin() {
  window.location.href = window.location.pathname.includes('/pages/') ? '../index.html' : 'index.html';
}

/**
 * Función base. Arma la petición, maneja JSON y centraliza errores.
 * @param {string} endpoint - ej: '/services', '/auth/login'
 * @param {object} options - method, body (objeto JS, no string), etc.
 */
async function apiRequest(endpoint, options = {}) {
  const config = {
    method: options.method || 'GET',
    headers: {},
  };

  const token = sessionStorage.getItem('access_token');
  if (token) {
    config.headers['Authorization'] = `Bearer ${token}`;
  }

  // Si hay body, lo convertimos a JSON y avisamos el Content-Type
  if (options.body) {
    config.headers['Content-Type'] = 'application/json';
    config.body = JSON.stringify(options.body);
  }

  let response;
  try {
    response = await fetch(`${API_BASE_URL}${endpoint}`, config);
  } catch (networkError) {
    // Esto salta solo si el servidor está caído o no hay red
    throw new Error('No se pudo conectar con el servidor. ¿Está corriendo el backend?');
  }

  // El backend puede responder sin body en algunos casos (poco común, pero por seguridad)
  let data = null;
  try {
    data = await response.json();
  } catch (_) {
    data = null;
  }

  // Token vencido o inválido (401) o rol sin permiso (403): de vuelta al login. Sin token,
  // el 401 es normal en páginas públicas y cada página decide qué mostrar.
  if ((response.status === 401 || response.status === 403) && token && endpoint !== LOGIN_ENDPOINT) {
    cerrarSesionLocal();
    irAlLogin();
  }

  if (!response.ok) {
    // Rutas antiguas: { error: '...' }. API v1: { code, message, details }.
    const mensaje = data?.error || data?.message || `Error ${response.status}`;
    const error = new Error(mensaje);
    error.status = response.status; // guardamos el código por si cada página quiere reaccionar distinto
    error.code = data?.code;
    throw error;
  }

  return data;
}

// Funciones de conveniencia — esto es lo que vas a usar en cada página
function apiGet(endpoint) {
  return apiRequest(endpoint, { method: 'GET' });
}

function apiPost(endpoint, body) {
  return apiRequest(endpoint, { method: 'POST', body });
}

function apiPut(endpoint, body) {
  return apiRequest(endpoint, { method: 'PUT', body });
}

function apiDelete(endpoint) {
  return apiRequest(endpoint, { method: 'DELETE' });
}