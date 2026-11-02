// frontend/js/nav.js
// Barra de navegación común. Se dibuja dentro de <header id="app-nav">
// con los enlaces del rol, el nombre del usuario y "Cerrar sesión".
// Requiere api.js y ui.js cargados antes.

const ENLACES_POR_ROL = {
  client: [
    { href: 'catalogo.html', texto: 'Servicios', icon: 'grid' },
    { href: 'historial-cliente.html', texto: 'Mi historial', icon: 'historial' },
  ],
  mechanic: [
    { href: 'dashboard-empleado.html', texto: 'Mis citas', icon: 'llave' },
  ],
  owner: [
    { href: 'dashboard-admin.html', texto: 'Panel del taller', icon: 'panel' },
    { href: 'mercado.html', texto: 'Mercado', icon: 'grafico' },
    { href: 'catalogo.html', texto: 'Catálogo', icon: 'grid' },
  ],
};
ENLACES_POR_ROL.admin = ENLACES_POR_ROL.owner;

const NOMBRES_ROL = { client: 'Cliente', mechanic: 'Mecánico', owner: 'Dueño', admin: 'Administrador' };

function dibujarNav(usuario) {
  const contenedor = document.getElementById('app-nav');
  if (!contenedor) return;

  const paginaActual = window.location.pathname.split('/').pop();
  const enlaces = usuario ? (ENLACES_POR_ROL[usuario.role] || []) : [];
  const iniciales = usuario
    ? `${usuario.first_name?.[0] || ''}${usuario.last_name?.[0] || ''}`.toUpperCase()
    : '';

  contenedor.className = 'navbar';
  contenedor.innerHTML = `
    <nav class="navbar-inner" aria-label="Principal">
      <a class="navbar-brand" href="${enlaces[0]?.href || '../index.html'}">
        <span class="navbar-logo">${icono('llave')}</span>MecaTrack
      </a>
      <ul class="navbar-links">
        ${enlaces.map(e => `
          <li><a href="${e.href}" ${e.href === paginaActual ? 'aria-current="page"' : ''}>${icono(e.icon)}${esc(e.texto)}</a></li>
        `).join('')}
      </ul>
      <div class="navbar-user">
        ${usuario ? `
          <span class="navbar-avatar" aria-hidden="true">${esc(iniciales)}</span>
          <span class="navbar-user-text">
            <span class="navbar-user-name">${esc(usuario.first_name)} ${esc(usuario.last_name)}</span>
            <span class="navbar-user-role">${esc(NOMBRES_ROL[usuario.role] || usuario.role)}</span>
          </span>
          <button type="button" class="btn-ghost btn-sm" id="btn-logout">${icono('salir')}<span>Salir</span></button>
        ` : `<a class="btn btn-sm" href="../index.html">Iniciar sesión</a>`}
      </div>
    </nav>`;

  document.getElementById('btn-logout')?.addEventListener('click', async () => {
    try { await apiPost('/auth/logout', {}); } catch (_) { /* la sesión ya no existía */ }
    sessionStorage.clear();
    window.location.href = '../index.html';
  });
}

// Promesa con el usuario actual (o null si no hay sesión); otras páginas
// pueden esperarla sin volver a pedir /auth/me.
const sesionActual = apiGet('/auth/me').catch(() => null);
sesionActual.then(dibujarNav).catch(errorNoControlado);
