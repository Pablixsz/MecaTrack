// frontend/js/ui.js
// Utilidades de presentación compartidas: iconos SVG, insignias de estado,
// formato de fechas/precios y bloques de "vacío" y "cargando".
// No hace llamadas a la API.

// Iconos (trazos de 24x24, estilo lineal). Se insertan como HTML.
const ICONOS = {
  llave: '<path d="M14.7 6.3a4 4 0 0 0-5.4 5.4L3 18l3 3 6.3-6.3a4 4 0 0 0 5.4-5.4l-2.5 2.5-2.4-.6-.6-2.4z"/>',
  auto: '<path d="M5 17h14M6 17v2M18 17v2"/><path d="M3 13l2-5a2 2 0 0 1 1.9-1.3h10.2A2 2 0 0 1 19 8l2 5v4H3z"/><circle cx="7.5" cy="13.5" r="1"/><circle cx="16.5" cy="13.5" r="1"/>',
  calendario: '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 10h18"/>',
  reloj: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  usuario: '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
  bahia: '<path d="M3 21V8l9-5 9 5v13"/><path d="M7 21v-8h10v8"/>',
  tarjeta: '<rect x="2" y="5" width="20" height="14" rx="2"/><path d="M2 10h20"/>',
  lista: '<path d="M9 6h12M9 12h12M9 18h12"/><circle cx="4" cy="6" r="1"/><circle cx="4" cy="12" r="1"/><circle cx="4" cy="18" r="1"/>',
  grid: '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
  historial: '<path d="M3 12a9 9 0 1 0 3-6.7"/><path d="M3 4v5h5"/><path d="M12 8v4l3 2"/>',
  salir: '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="M16 17l5-5-5-5M21 12H9"/>',
  mas: '<path d="M12 5v14M5 12h14"/>',
  editar: '<path d="M4 20h4L19 9l-4-4L4 16z"/>',
  basura: '<path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/>',
  check: '<path d="M5 12l5 5L20 7"/>',
  x: '<path d="M6 6l12 12M18 6L6 18"/>',
  chevron: '<path d="M9 6l6 6-6 6"/>',
  panel: '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M9 21V9"/>',
  repuesto: '<circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M4.2 4.2l2.1 2.1M17.7 17.7l2.1 2.1M2 12h3M19 12h3M4.2 19.8l2.1-2.1M17.7 6.3l2.1-2.1"/>',
  velocimetro: '<path d="M12 14l4-4"/><path d="M3.3 17a9 9 0 1 1 17.4 0"/>',
  grafico: '<path d="M3 3v18h18"/><path d="M7 15v3M11 11v7M15 7v11M19 12v6"/>',
  actualizar: '<path d="M21 12a9 9 0 1 1-2.6-6.4"/><path d="M21 4v5h-5"/>',
  alerta: '<path d="M12 3l9.5 17h-19z"/><path d="M12 10v4M12 17.5v.01"/>',
  pausa: '<circle cx="12" cy="12" r="9"/><path d="M10 9v6M14 9v6"/>',
};

// Ultimo recurso para promesas sin await: las funciones cargar* ya muestran sus
// errores de la API; esto registra lo que se les escape en vez de perderlo.
function errorNoControlado(error) {
  console.error(error);
}

function icono(nombre, extraClase = '') {
  return `<svg class="${extraClase}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" `
    + `stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">${ICONOS[nombre] || ''}</svg>`;
}

// Escapa texto antes de meterlo en innerHTML.
function esc(valor) {
  return String(valor ?? '').replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[c]));
}

const formatoPesos = new Intl.NumberFormat('es-CO', { style: 'currency', currency: 'COP', maximumFractionDigits: 0 });

function pesos(valor) {
  return formatoPesos.format(valor || 0);
}

function fechaLarga(iso) {
  return new Date(iso).toLocaleDateString('es-CO', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
}

function fechaCorta(iso) {
  return new Date(iso).toLocaleDateString('es-CO', { day: 'numeric', month: 'short', year: 'numeric' });
}

function hora(iso) {
  return new Date(iso).toLocaleTimeString('es-CO', { hour: 'numeric', minute: '2-digit' });
}

// --- Insignias de estado ---
const ESTADOS = {
  cita: {
    pending: ['Pendiente de pago', 'warning'],
    confirmed: ['Confirmada', 'info'],
    in_progress: ['En proceso', 'primary'],
    completed: ['Completada', 'success'],
    cancelled: ['Cancelada', 'neutral'],
  },
  pago: {
    pending: ['Pendiente', 'warning'],
    completed: ['Pagado', 'success'],
    failed: ['Fallido', 'danger'],
    refunded: ['Reembolsado', 'neutral'],
  },
  seguimiento: {
    received: ['Recibido', 'neutral'],
    diagnosing: ['Diagnosticando', 'info'],
    in_repair: ['En reparación', 'primary'],
    quality_check: ['Control de calidad', 'warning'],
    ready_for_pickup: ['Listo para entrega', 'success'],
    delivered: ['Entregado', 'success'],
  },
};

function nombreEstado(tipo, estado) {
  return (ESTADOS[tipo][estado] || [estado])[0];
}

function badgeEstado(tipo, estado) {
  const [texto, variante] = ESTADOS[tipo][estado] || [estado, 'neutral'];
  return `<span class="badge badge-${variante}">${esc(texto)}</span>`;
}

// --- Bloques reutilizables ---
function estadoVacio({ icon = 'lista', titulo, texto = '', accion = null }) {
  return `
    <div class="empty-state">
      <span class="icon-tile">${icono(icon)}</span>
      <h3>${esc(titulo)}</h3>
      ${texto ? `<p>${esc(texto)}</p>` : ''}
      ${accion ? `<a class="btn" href="${esc(accion.href)}">${icono('mas')}${esc(accion.texto)}</a>` : ''}
    </div>`;
}

function cargando(texto = 'Cargando…') {
  return `<div class="loading" role="status"><span class="spinner" aria-hidden="true"></span>${esc(texto)}</div>`;
}
