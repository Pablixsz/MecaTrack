// frontend/js/dashboard-admin.js
// Panel del dueño (owner/admin): vista global de citas y gestión de
// bahías, repuestos, servicios y mecánicos.

const adminErrorEl = document.getElementById('admin-error');
const adminExitoEl = document.getElementById('admin-exito');

const NOMBRES_ESTADO_CITA = {
  pending: 'Pendiente', confirmed: 'Confirmada', in_progress: 'En proceso',
  completed: 'Completada', cancelled: 'Cancelada',
};
const NOMBRES_ESTADO_BAHIA = { available: 'Disponible', under_maintenance: 'En mantenimiento' };

let usuarioActual = null;
let todasLasCitas = [];

// --- Utilidades (esc y formatoPesos vienen de ui.js) ---

function mostrarError(error) {
  adminExitoEl.textContent = '';
  adminErrorEl.textContent = error.message || String(error);
  if (error.status === 401) window.location.href = '../index.html';
}

function mostrarExito(mensaje) {
  adminErrorEl.textContent = '';
  adminExitoEl.textContent = mensaje;
  setTimeout(() => { if (adminExitoEl.textContent === mensaje) adminExitoEl.textContent = ''; }, 2500);
}

function badge(texto, tipo) {
  return `<span class="badge badge-${esc(tipo)}">${esc(texto)}</span>`;
}

// --- Sesión y pestañas ---

async function verificarSesion() {
  // sesionActual (nav.js) ya pidió /auth/me; es null si no hay sesión.
  usuarioActual = await sesionActual;
  if (!usuarioActual || !['owner', 'admin'].includes(usuarioActual.role)) {
    window.location.href = '../index.html';
    return false;
  }
  if (usuarioActual.role === 'owner') {
    apiGet('/businesses/mine')
      .then(n => { document.getElementById('admin-negocio').textContent = `${n.business_name} · ${n.address}`; })
      .catch(() => {});
  } else {
    // Crear o desactivar mecánicos es exclusivo del dueño
    document.getElementById('form-mecanico').classList.add('oculto');
  }
  return true;
}

// El botón de cerrar sesión lo dibuja nav.js en la barra superior.

const CARGADORES = {
  citas: cargarCitas,
  recepcion: cargarRecepcion,
  bahias: cargarBahias,
  repuestos: cargarRepuestos,
  servicios: cargarServicios,
  mecanicos: cargarMecanicos,
};

document.querySelector('.tabs').addEventListener('click', (e) => {
  const tab = e.target.closest('.tab');
  if (!tab) return;
  document.querySelectorAll('.tab').forEach(t => t.classList.toggle('activo', t === tab));
  document.querySelectorAll('.seccion-admin').forEach(s => s.classList.add('oculto'));
  document.getElementById(`seccion-${tab.dataset.seccion}`).classList.remove('oculto');
  adminErrorEl.textContent = '';
  CARGADORES[tab.dataset.seccion]();
});

// --- CITAS ---

async function cargarCitas() {
  try {
    todasLasCitas = await apiGet('/appointments');
    renderizarResumen();
    renderizarCitas();
  } catch (error) {
    mostrarError(error);
  }
}

function renderizarResumen() {
  const d = new Date();  // fecha local (las citas se guardan en hora local)
  const hoy = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  const contar = estado => todasLasCitas.filter(c => c.status === estado).length;
  const tarjetas = [
    ['Citas de hoy', todasLasCitas.filter(c => c.scheduled_start.slice(0, 10) === hoy && c.status !== 'cancelled').length],
    ['Pendientes de pago', contar('pending')],
    ['Confirmadas', contar('confirmed')],
    ['En proceso', contar('in_progress')],
    ['Completadas', contar('completed')],
  ];
  document.getElementById('resumen-citas').innerHTML = tarjetas
    .map(([titulo, valor]) => `<div class="tarjeta-resumen"><span>${esc(titulo)}</span><strong>${valor}</strong></div>`)
    .join('');
}

function renderizarCitas() {
  const estado = document.getElementById('filtro-estado').value;
  const fecha = document.getElementById('filtro-fecha').value;
  const citas = todasLasCitas.filter(c =>
    (!estado || c.status === estado) && (!fecha || c.scheduled_start.slice(0, 10) === fecha));

  document.getElementById('citas-vacio').classList.toggle('oculto', citas.length > 0);
  document.getElementById('tabla-citas').innerHTML = citas.map(c => `
    <tr data-id="${c.appointment_id}">
      <td>${c.appointment_id}</td>
      <td>${esc(new Date(c.scheduled_start).toLocaleString('es-CO', { dateStyle: 'medium', timeStyle: 'short' }))}</td>
      <td>${esc(c.client_name)}</td>
      <td>${esc(c.vehicle_plate)}</td>
      <td>${esc(c.service_name)}</td>
      <td>${esc(c.mechanic_name)}</td>
      <td>${esc(c.bay_number)}</td>
      <td>
        <select class="select-estado-cita" aria-label="Estado de la cita ${c.appointment_id}">
          ${Object.entries(NOMBRES_ESTADO_CITA).map(([valor, nombre]) =>
            `<option value="${valor}" ${valor === c.status ? 'selected' : ''}>${nombre}</option>`).join('')}
        </select>
      </td>
      <td><button class="btn-chico btn-guardar-cita">Guardar</button></td>
    </tr>`).join('');
}

document.getElementById('filtro-estado').addEventListener('change', renderizarCitas);
document.getElementById('filtro-fecha').addEventListener('change', renderizarCitas);
document.getElementById('btn-limpiar-filtros').addEventListener('click', () => {
  document.getElementById('filtro-estado').value = '';
  document.getElementById('filtro-fecha').value = '';
  renderizarCitas();
});

document.getElementById('tabla-citas').addEventListener('click', async (e) => {
  if (!e.target.classList.contains('btn-guardar-cita')) return;
  const fila = e.target.closest('tr');
  const nuevoEstado = fila.querySelector('.select-estado-cita').value;
  try {
    await apiPut(`/appointments/${fila.dataset.id}/status`, { status: nuevoEstado });
    mostrarExito(`Cita #${fila.dataset.id} actualizada a "${NOMBRES_ESTADO_CITA[nuevoEstado]}".`);
    cargarCitas().catch(errorNoControlado);
  } catch (error) {
    mostrarError(error);
  }
});

// --- BAHÍAS ---

async function cargarBahias() {
  try {
    const bahias = await apiGet('/bays');
    document.getElementById('tabla-bahias').innerHTML = bahias.map(b => `
      <tr data-id="${b.bay_id}">
        <td>${esc(b.bay_number)}</td>
        <td><input type="checkbox" class="check-elevador" ${b.has_elevator ? 'checked' : ''} aria-label="Elevador"></td>
        <td>
          <select class="select-estado-bahia" aria-label="Estado de la bahía">
            ${Object.entries(NOMBRES_ESTADO_BAHIA).map(([valor, nombre]) =>
              `<option value="${valor}" ${valor === b.status ? 'selected' : ''}>${nombre}</option>`).join('')}
          </select>
        </td>
      </tr>`).join('');
  } catch (error) {
    mostrarError(error);
  }
}

document.getElementById('tabla-bahias').addEventListener('change', async (e) => {
  const fila = e.target.closest('tr');
  if (!fila) return;
  const body = e.target.classList.contains('check-elevador')
    ? { has_elevator: e.target.checked }
    : { status: e.target.value };
  try {
    await apiPut(`/bays/${fila.dataset.id}`, body);
    mostrarExito('Bahía actualizada.');
  } catch (error) {
    mostrarError(error);
    cargarBahias().catch(errorNoControlado);
  }
});

document.getElementById('form-bahia').addEventListener('submit', async (e) => {
  e.preventDefault();
  try {
    await apiPost('/bays', {
      bay_number: document.getElementById('bahia-numero').value.trim(),
      has_elevator: document.getElementById('bahia-elevador').checked,
    });
    e.target.reset();
    mostrarExito('Bahía creada.');
    cargarBahias().catch(errorNoControlado);
  } catch (error) {
    mostrarError(error);
  }
});

// --- REPUESTOS ---

async function cargarRepuestos() {
  try {
    const repuestos = await apiGet('/parts?include_inactive=1');
    document.getElementById('tabla-repuestos').innerHTML = repuestos.map(p => `
      <tr data-id="${p.part_id}" class="${p.status === 'inactive' ? 'fila-inactiva' : ''}">
        <td><input type="text" class="input-tabla rep-nombre" value="${esc(p.part_name)}" aria-label="Nombre"></td>
        <td><input type="number" class="input-tabla rep-precio" min="0" value="${p.unit_price}" aria-label="Precio"></td>
        <td>
          <input type="number" class="input-tabla rep-stock" min="0" value="${p.stock_quantity}" aria-label="Stock">
          ${p.stock_quantity <= 5 ? badge('Stock bajo', 'alerta') : ''}
        </td>
        <td>${p.status === 'active' ? badge('Activo', 'ok') : badge('Inactivo', 'apagado')}</td>
        <td class="acciones">
          <button class="btn-chico btn-guardar-repuesto">Guardar</button>
          <button class="btn-chico btn-secundario btn-estado-repuesto" data-status="${p.status === 'active' ? 'inactive' : 'active'}">
            ${p.status === 'active' ? 'Desactivar' : 'Activar'}
          </button>
        </td>
      </tr>`).join('');
  } catch (error) {
    mostrarError(error);
  }
}

document.getElementById('tabla-repuestos').addEventListener('click', async (e) => {
  const fila = e.target.closest('tr');
  if (!fila) return;
  let body = null;
  if (e.target.classList.contains('btn-guardar-repuesto')) {
    body = {
      part_name: fila.querySelector('.rep-nombre').value.trim(),
      unit_price: Number.parseInt(fila.querySelector('.rep-precio').value),
      stock_quantity: Number.parseInt(fila.querySelector('.rep-stock').value),
    };
  } else if (e.target.classList.contains('btn-estado-repuesto')) {
    body = { status: e.target.dataset.status };
  }
  if (!body) return;
  try {
    await apiPut(`/parts/${fila.dataset.id}`, body);
    mostrarExito('Repuesto actualizado.');
    cargarRepuestos().catch(errorNoControlado);
  } catch (error) {
    mostrarError(error);
  }
});

document.getElementById('form-repuesto').addEventListener('submit', async (e) => {
  e.preventDefault();
  try {
    await apiPost('/parts', {
      part_name: document.getElementById('repuesto-nombre').value.trim(),
      unit_price: Number.parseInt(document.getElementById('repuesto-precio').value),
      stock_quantity: Number.parseInt(document.getElementById('repuesto-stock').value),
    });
    e.target.reset();
    mostrarExito('Repuesto creado.');
    cargarRepuestos().catch(errorNoControlado);
  } catch (error) {
    mostrarError(error);
  }
});

// --- SERVICIOS ---

async function cargarServicios() {
  try {
    const servicios = await apiGet('/services/manage');
    document.getElementById('tabla-servicios').innerHTML = servicios.map(s => `
      <tr data-id="${s.service_id}" class="${s.status === 'inactive' ? 'fila-inactiva' : ''}">
        <td><input type="text" class="input-tabla serv-nombre" value="${esc(s.service_name)}" aria-label="Nombre"></td>
        <td><input type="text" class="input-tabla serv-descripcion" value="${esc(s.description)}" aria-label="Descripción"></td>
        <td><input type="number" class="input-tabla serv-duracion" min="5" step="5" value="${s.estimated_duration_minutes}" aria-label="Duración"></td>
        <td>
          <input type="number" class="input-tabla serv-precio" min="0" value="${s.base_price}" aria-label="Precio">
          <small class="detalle-servicio">${esc(formatoPesos.format(s.base_price))}</small>
        </td>
        <td>${s.status === 'active' ? badge('Activo', 'ok') : badge('Inactivo', 'apagado')}</td>
        <td class="acciones">
          <button class="btn-chico btn-guardar-servicio">Guardar</button>
          <button class="btn-chico btn-secundario btn-estado-servicio" data-status="${s.status === 'active' ? 'inactive' : 'active'}">
            ${s.status === 'active' ? 'Desactivar' : 'Activar'}
          </button>
        </td>
      </tr>`).join('');
  } catch (error) {
    mostrarError(error);
  }
}

document.getElementById('tabla-servicios').addEventListener('click', async (e) => {
  const fila = e.target.closest('tr');
  if (!fila) return;
  let body = null;
  if (e.target.classList.contains('btn-guardar-servicio')) {
    body = {
      service_name: fila.querySelector('.serv-nombre').value.trim(),
      description: fila.querySelector('.serv-descripcion').value.trim() || null,
      estimated_duration_minutes: Number.parseInt(fila.querySelector('.serv-duracion').value),
      base_price: Number.parseInt(fila.querySelector('.serv-precio').value),
    };
  } else if (e.target.classList.contains('btn-estado-servicio')) {
    body = { status: e.target.dataset.status };
  }
  if (!body) return;
  try {
    await apiPut(`/services/${fila.dataset.id}`, body);
    mostrarExito('Servicio actualizado.');
    cargarServicios().catch(errorNoControlado);
  } catch (error) {
    mostrarError(error);
  }
});

document.getElementById('form-servicio').addEventListener('submit', async (e) => {
  e.preventDefault();
  try {
    await apiPost('/services', {
      service_name: document.getElementById('servicio-nombre').value.trim(),
      description: document.getElementById('servicio-descripcion').value.trim() || null,
      estimated_duration_minutes: Number.parseInt(document.getElementById('servicio-duracion').value),
      base_price: Number.parseInt(document.getElementById('servicio-precio').value),
    });
    e.target.reset();
    mostrarExito('Servicio creado.');
    cargarServicios().catch(errorNoControlado);
  } catch (error) {
    mostrarError(error);
  }
});

// --- MECÁNICOS ---

async function cargarMecanicos() {
  try {
    const mecanicos = await apiGet('/businesses/mechanics');
    const esDueno = usuarioActual.role === 'owner';
    document.getElementById('tabla-mecanicos').innerHTML = mecanicos.map(m => `
      <tr data-id="${m.user_id}" class="${m.status === 'inactive' ? 'fila-inactiva' : ''}">
        <td>${esc(m.first_name)} ${esc(m.last_name)}</td>
        <td>${esc(m.email)}</td>
        <td>${esc(m.phone || '—')}</td>
        <td>${m.status === 'active' ? badge('Activo', 'ok') : badge('Inactivo', 'apagado')}</td>
        <td>
          ${esDueno ? `<button class="btn-chico btn-secundario btn-estado-mecanico" data-status="${m.status === 'active' ? 'inactive' : 'active'}">
            ${m.status === 'active' ? 'Desactivar' : 'Activar'}</button>` : ''}
        </td>
      </tr>`).join('');
  } catch (error) {
    mostrarError(error);
  }
}

document.getElementById('tabla-mecanicos').addEventListener('click', async (e) => {
  if (!e.target.classList.contains('btn-estado-mecanico')) return;
  const fila = e.target.closest('tr');
  try {
    await apiPut(`/businesses/mechanics/${fila.dataset.id}`, { status: e.target.dataset.status });
    mostrarExito('Mecánico actualizado.');
    cargarMecanicos().catch(errorNoControlado);
  } catch (error) {
    mostrarError(error);
  }
});

document.getElementById('form-mecanico').addEventListener('submit', async (e) => {
  e.preventDefault();
  try {
    await apiPost('/businesses/mechanics', {
      first_name: document.getElementById('mec-nombre').value.trim(),
      last_name: document.getElementById('mec-apellido').value.trim(),
      document_number: document.getElementById('mec-documento').value.trim(),
      email: document.getElementById('mec-email').value.trim(),
      phone: document.getElementById('mec-telefono').value.trim() || null,
      password: document.getElementById('mec-password').value,
    });
    e.target.reset();
    mostrarExito('Mecánico creado. Ya puede iniciar sesión con su correo.');
    cargarMecanicos().catch(errorNoControlado);
  } catch (error) {
    mostrarError(error);
  }
});

// --- RECEPCIÓN: agendar a nombre de un cliente ---
// Flujo: 1) buscar o registrar al cliente, 2) elegir o agregar su vehículo,
// 3) agendar (POST /appointments con client_user_id) y registrar el depósito.

const NOMBRES_METODO = { cash: 'Efectivo', card: 'Tarjeta', transfer: 'Transferencia' };
let clienteRecepcion = null;

const $ = (id) => document.getElementById(id);

async function cargarRecepcion() {
  // Fecha mínima: ahora (formato local YYYY-MM-DDTHH:MM).
  const ahora = new Date();
  ahora.setMinutes(ahora.getMinutes() - ahora.getTimezoneOffset());
  $('rc-fecha').min = ahora.toISOString().slice(0, 16);
  try {
    const servicios = await apiGet('/services');
    $('rc-servicio').innerHTML = servicios.map(s =>
      `<option value="${s.service_id}">${esc(s.service_name)} · ${s.estimated_duration_minutes} min · ${esc(pesos(s.base_price))}</option>`).join('');
  } catch (error) {
    mostrarError(error);
  }
}

function habilitarPasos() {
  $('paso-vehiculo').classList.toggle('paso-bloqueado', !clienteRecepcion);
  const hayVehiculo = !!$('select-vehiculo-cliente').value;
  $('paso-cita').classList.toggle('paso-bloqueado', !clienteRecepcion || !hayVehiculo);
}

async function buscarClientes(texto) {
  try {
    const clientes = await apiGet(`/businesses/clients${texto ? `?q=${encodeURIComponent(texto)}` : ''}`);
    $('resultados-clientes').innerHTML = clientes.length ? clientes.map(c => `
      <li>
        <span><strong>${esc(c.first_name)} ${esc(c.last_name)}</strong>
          <small>${esc(c.email)} · doc. ${esc(c.document_number)}${c.phone ? ` · ${esc(c.phone)}` : ''}</small></span>
        <button type="button" class="btn-chico btn-secundario" data-id="${c.user_id}">Seleccionar</button>
      </li>`).join('')
      : '<li class="texto-suave">No hay clientes con ese dato. Puedes registrarlo como cliente nuevo.</li>';
    $('resultados-clientes').dataset.clientes = JSON.stringify(clientes);
  } catch (error) {
    mostrarError(error);
  }
}

async function seleccionarCliente(cliente) {
  clienteRecepcion = cliente;
  $('buscar-cliente').value = '';
  $('resultados-clientes').innerHTML = '';
  $('form-cliente-nuevo').classList.add('oculto');
  $('resultado-cita').classList.add('oculto');
  $('cliente-seleccionado').classList.remove('oculto');
  $('cliente-seleccionado').innerHTML = `${icono('usuario')}<span><strong>${esc(cliente.first_name)} ${esc(cliente.last_name)}</strong>
    <small>${esc(cliente.email)}</small></span>
    <button type="button" class="btn-chico btn-ghost" id="btn-cambiar-cliente">Cambiar</button>`;
  await cargarVehiculosCliente();
}

async function cargarVehiculosCliente(seleccionarId = null) {
  try {
    const vehiculos = await apiGet(`/vehicles?client_user_id=${clienteRecepcion.user_id}`);
    $('select-vehiculo-cliente').innerHTML = vehiculos.length
      ? vehiculos.map(v => `<option value="${v.vehicle_id}">${esc(v.brand)} ${esc(v.model)} · ${esc(v.license_plate)}</option>`).join('')
      : '<option value="">Sin vehículos: agrega uno</option>';
    if (seleccionarId) $('select-vehiculo-cliente').value = seleccionarId;
    $('form-vehiculo-cliente').classList.toggle('oculto', vehiculos.length > 0);
  } catch (error) {
    mostrarError(error);
  }
  habilitarPasos();
}

$('form-buscar-cliente').addEventListener('submit', (e) => {
  e.preventDefault();
  buscarClientes($('buscar-cliente').value.trim()).catch(errorNoControlado);
});

$('resultados-clientes').addEventListener('click', (e) => {
  const boton = e.target.closest('button[data-id]');
  if (!boton) return;
  const clientes = JSON.parse($('resultados-clientes').dataset.clientes || '[]');
  seleccionarCliente(clientes.find(c => String(c.user_id) === boton.dataset.id)).catch(errorNoControlado);
});

$('btn-cliente-nuevo').addEventListener('click', () => {
  $('form-cliente-nuevo').classList.remove('oculto');
  $('resultados-clientes').innerHTML = '';
  $('cli-nombre').focus();
});
$('btn-cancelar-cliente').addEventListener('click', () => $('form-cliente-nuevo').classList.add('oculto'));

$('cliente-seleccionado').addEventListener('click', (e) => {
  if (e.target.id !== 'btn-cambiar-cliente') return;
  clienteRecepcion = null;
  $('cliente-seleccionado').classList.add('oculto');
  $('select-vehiculo-cliente').innerHTML = '';
  $('resultado-cita').classList.add('oculto');
  habilitarPasos();
  $('buscar-cliente').focus();
});

$('form-cliente-nuevo').addEventListener('submit', async (e) => {
  e.preventDefault();
  const datos = {
    first_name: $('cli-nombre').value.trim(),
    last_name: $('cli-apellido').value.trim(),
    document_number: $('cli-documento').value.trim(),
    email: $('cli-email').value.trim(),
    phone: $('cli-telefono').value.trim() || null,
    password: $('cli-password').value,
  };
  try {
    const creado = await apiPost('/businesses/clients', datos);
    e.target.reset();
    mostrarExito('Cliente registrado.');
    await seleccionarCliente({ user_id: creado.user_id, ...datos });
  } catch (error) {
    mostrarError(error);
  }
});

$('btn-vehiculo-nuevo').addEventListener('click', () => $('form-vehiculo-cliente').classList.remove('oculto'));
$('btn-cancelar-vehiculo').addEventListener('click', () => $('form-vehiculo-cliente').classList.add('oculto'));
$('select-vehiculo-cliente').addEventListener('change', habilitarPasos);

$('form-vehiculo-cliente').addEventListener('submit', async (e) => {
  e.preventDefault();
  try {
    const creado = await apiPost('/vehicles', {
      client_user_id: clienteRecepcion.user_id,
      license_plate: $('rv-placa').value.trim().toUpperCase(),
      brand: $('rv-marca').value.trim(),
      model: $('rv-modelo').value.trim(),
      year: Number.parseInt($('rv-anio').value, 10),
      vehicle_type: $('rv-tipo').value,
      fuel_type: $('rv-combustible').value,
      transmission_type: $('rv-transmision').value,
    });
    e.target.reset();
    mostrarExito('Vehículo registrado.');
    await cargarVehiculosCliente(creado.vehicle_id);
  } catch (error) {
    mostrarError(error);
  }
});

$('form-cita-recepcion').addEventListener('submit', async (e) => {
  e.preventDefault();
  const boton = e.target.querySelector('button[type="submit"]');
  boton.disabled = true;
  try {
    const cita = await apiPost('/appointments', {
      client_user_id: clienteRecepcion.user_id,
      vehicle_id: Number.parseInt($('select-vehiculo-cliente').value, 10),
      service_id: Number.parseInt($('rc-servicio').value, 10),
      scheduled_start: `${$('rc-fecha').value}:00`,
      payment_method: $('rc-pago').value,
    });
    mostrarExito(`Cita #${cita.appointment_id} agendada.`);
    await mostrarResultadoCita(cita);
  } catch (error) {
    if (error.status === 409) error.message = 'No hay bahía o mecánico libre en ese horario. Prueba otra hora.';
    mostrarError(error);
  } finally {
    boton.disabled = false;
  }
});

async function mostrarResultadoCita(cita) {
  const pagos = await apiGet(`/payments/appointment/${cita.appointment_id}`);
  const detalle = (await apiGet(`/appointments/${cita.appointment_id}`));
  $('resultado-cita').classList.remove('oculto');
  $('resultado-cita').innerHTML = `
    <div class="resultado-cita">
      <p><strong>Cita #${cita.appointment_id}</strong> · ${esc(fechaLarga(cita.scheduled_start))}, ${esc(hora(cita.scheduled_start))} a ${esc(hora(cita.scheduled_end))}
        · ${esc(detalle.bay_number)} · Mecánico: ${esc(detalle.mechanic_name)} · ${badgeEstado('cita', detalle.status)}</p>
      <table class="tabla tabla-compacta">
        <thead><tr><th>Pago</th><th>Método</th><th class="num">Valor</th><th>Estado</th><th></th></tr></thead>
        <tbody>${pagos.map(p => `
          <tr data-id="${p.payment_id}" data-cita="${cita.appointment_id}">
            <td>${p.payment_type === 'deposit' ? 'Depósito (30 %)' : 'Saldo (70 %)'}</td>
            <td>${esc(NOMBRES_METODO[p.payment_method] || p.payment_method)}</td>
            <td class="num">${esc(pesos(p.amount))}</td>
            <td>${badgeEstado('pago', p.status)}</td>
            <td>${p.status === 'pending' ? '<button type="button" class="btn-chico btn-pagar">Registrar pago</button>' : ''}</td>
          </tr>`).join('')}</tbody>
      </table>
      <p class="field-hint">Registrar el depósito confirma la cita. El cliente la ve en «Mi historial» al iniciar sesión.</p>
    </div>`;
}

$('resultado-cita').addEventListener('click', async (e) => {
  if (!e.target.classList.contains('btn-pagar')) return;
  const fila = e.target.closest('tr');
  try {
    await apiPost(`/payments/${fila.dataset.id}/pay`, {});
    mostrarExito('Pago registrado.');
    const cita = await apiGet(`/appointments/${fila.dataset.cita}`);
    await mostrarResultadoCita(cita);
  } catch (error) {
    mostrarError(error);
  }
});

// --- Inicio ---
verificarSesion().then(ok => (ok ? cargarCitas() : null)).catch(errorNoControlado);
