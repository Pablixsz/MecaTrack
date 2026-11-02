// frontend/js/dashboard-empleado.js
// Panel del mecánico: cambiar estado de la cita y registrar seguimientos con repuestos.

const listaCitas = document.getElementById('lista-citas');
const citasErrorEl = document.getElementById('citas-error');
const resumenEl = document.getElementById('resumen-mecanico');

let mapaVehiculos = new Map();
let mapaServicios = new Map();
let listaPartes = []; // array de {part_id, part_name, unit_price, stock_quantity}

const ESTADOS_CITA = ['pending', 'confirmed', 'in_progress', 'completed', 'cancelled'];
const ESTADOS_TRACKING = ['received', 'diagnosing', 'in_repair', 'quality_check', 'ready_for_pickup', 'delivered'];

// Orden en que se muestran los grupos; los cerrados empiezan plegados.
const GRUPOS = [
  { estado: 'in_progress', titulo: 'En proceso' },
  { estado: 'confirmed', titulo: 'Confirmadas' },
  { estado: 'pending', titulo: 'Pendientes de pago' },
  { estado: 'completed', titulo: 'Completadas', plegado: true },
  { estado: 'cancelled', titulo: 'Canceladas', plegado: true },
];

async function cargarTodo() {
  citasErrorEl.textContent = '';
  try {
    const [servicios, partes, citas] = await Promise.all([
      apiGet('/services'),
      apiGet('/parts'),
      apiGet('/appointments'),
    ]);

    mapaServicios = new Map(servicios.map(s => [s.service_id, s]));
    listaPartes = partes;

    // Pedimos cada vehículo individualmente por id (GET /vehicles no sirve para mecánico)
    const idsVehiculosUnicos = [...new Set(citas.map(c => c.vehicle_id))];
    const vehiculos = await Promise.all(
      idsVehiculosUnicos.map(id => apiGet(`/vehicles/${id}`).catch(() => null))
    );
    mapaVehiculos = new Map(
      vehiculos.filter(v => v !== null).map(v => [v.vehicle_id, v])
    );

    renderizarResumen(citas);
    renderizarCitas(citas).catch(errorNoControlado);
  } catch (error) {
    listaCitas.innerHTML = '';
    citasErrorEl.textContent = 'No se pudieron cargar tus citas: ' + error.message;
  }
}

function esHoy(iso) {
  const d = new Date(iso);
  const hoy = new Date();
  return d.getFullYear() === hoy.getFullYear() && d.getMonth() === hoy.getMonth() && d.getDate() === hoy.getDate();
}

function renderizarResumen(citas) {
  const contar = estado => citas.filter(c => c.status === estado).length;
  const tarjetas = [
    ['Citas de hoy', citas.filter(c => esHoy(c.scheduled_start) && c.status !== 'cancelled').length],
    ['En proceso', contar('in_progress')],
    ['Confirmadas', contar('confirmed')],
    ['Pendientes de pago', contar('pending')],
  ];
  resumenEl.innerHTML = tarjetas
    .map(([titulo, valor]) => `<div class="stat"><span>${esc(titulo)}</span><strong>${valor}</strong></div>`)
    .join('');
}

function renderizarCitas(citas) {
  listaCitas.innerHTML = '';

  if (citas.length === 0) {
    listaCitas.innerHTML = estadoVacio({
      icon: 'llave',
      titulo: 'Aún no tienes citas asignadas',
      texto: 'Cuando un cliente agende y se te asigne, la verás aquí.',
    });
    return;
  }

  GRUPOS.forEach(grupo => {
    const delGrupo = citas
      .filter(c => c.status === grupo.estado)
      .sort((a, b) => new Date(a.scheduled_start) - new Date(b.scheduled_start));
    if (delGrupo.length === 0) return;

    const contenedor = document.createElement(grupo.plegado ? 'details' : 'section');
    contenedor.className = 'grupo-citas';
    const encabezado = `<h2 class="section-title">${esc(grupo.titulo)} <span class="count">${delGrupo.length}</span></h2>`;
    contenedor.innerHTML = grupo.plegado
      ? `<summary class="section-title">${icono('chevron', 'chevron')}${encabezado}</summary>`
      : encabezado;

    const lista = document.createElement('div');
    lista.className = 'lista-grupo';
    delGrupo.forEach(cita => lista.appendChild(crearTarjeta(cita)));
    contenedor.appendChild(lista);
    listaCitas.appendChild(contenedor);
  });
}

function crearTarjeta(cita) {
  const vehiculo = mapaVehiculos.get(cita.vehicle_id);
  const servicio = mapaServicios.get(cita.service_id);
  const id = cita.appointment_id;

  const tarjeta = document.createElement('article');
  tarjeta.className = 'tarjeta-servicio';
  tarjeta.dataset.appointmentId = id;

  const filasPartes = listaPartes.length === 0
    ? '<p class="field-hint partes-vacio">No hay repuestos activos en inventario.</p>'
    : listaPartes.map(p => {
      const sinStock = p.stock_quantity <= 0;
      return `
        <div class="fila-parte${sinStock ? ' sin-stock' : ''}">
          <input type="checkbox" class="check-parte" value="${p.part_id}" id="parte-${id}-${p.part_id}" ${sinStock ? 'disabled' : ''}>
          <label for="parte-${id}-${p.part_id}">${esc(p.part_name)}</label>
          <span class="badge ${sinStock ? 'badge-danger' : p.stock_quantity <= 5 ? 'badge-warning' : 'badge-neutral'} badge-plain">Stock ${p.stock_quantity}</span>
          <input type="number" class="cantidad-parte" min="1" max="${Math.max(p.stock_quantity, 1)}" value="1" disabled
            aria-label="Cantidad de ${esc(p.part_name)}">
        </div>`;
    }).join('');

  tarjeta.innerHTML = `
    <div class="card-header">
      <div>
        <h3 class="card-title">${esc(servicio ? servicio.service_name : (cita.service_name || 'Servicio #' + cita.service_id))}</h3>
        <p class="card-subtitle">Cita #${id}</p>
      </div>
      <span class="estado-badge">${badgeEstado('cita', cita.status)}</span>
    </div>

    <ul class="meta-list">
      <li>${icono('calendario')}<strong>${esc(fechaLarga(cita.scheduled_start))}</strong></li>
      <li>${icono('reloj')}${esc(hora(cita.scheduled_start))} – ${esc(hora(cita.scheduled_end))}${cita.bay_number ? ` · ${icono('bahia')}${esc(cita.bay_number)}` : ''}</li>
      <li>${icono('auto')}${vehiculo
        ? `<span class="plate">${esc(vehiculo.license_plate)}</span> ${esc(vehiculo.brand)} ${esc(vehiculo.model)}`
        : esc(cita.vehicle_plate || cita.vehicle_id)}</li>
      ${cita.client_name ? `<li>${icono('usuario')}${esc(cita.client_name)}</li>` : ''}
    </ul>

    <div class="estado-control">
      <div class="field">
        <label for="estado-cita-${id}">Estado de la cita</label>
        <select class="select-estado-cita" id="estado-cita-${id}">
          ${ESTADOS_CITA.map(s => `<option value="${s}" ${s === cita.status ? 'selected' : ''}>${esc(nombreEstado('cita', s))}</option>`).join('')}
        </select>
      </div>
      <button class="btn-secundario btn-guardar-estado">Guardar</button>
    </div>

    <p class="mensaje-error" role="alert"></p>
    <p class="mensaje-exito" role="status"></p>

    <div class="card-footer">
      <button class="btn-toggle-seguimiento" aria-expanded="false" aria-controls="seguimiento-${id}">${icono('mas')}Agregar seguimiento</button>
    </div>

    <form class="form-seguimiento oculto" id="seguimiento-${id}">
      <div class="form-grid">
        <div class="field">
          <label for="tracking-estado-${id}">Estado del proceso</label>
          <select class="tracking-estado" id="tracking-estado-${id}" required>
            ${ESTADOS_TRACKING.map(s => `<option value="${s}">${esc(nombreEstado('seguimiento', s))}</option>`).join('')}
          </select>
        </div>
        <div class="field">
          <label for="tracking-km-${id}">Kilometraje actual</label>
          <input type="number" class="tracking-kilometraje" id="tracking-km-${id}" min="0" inputmode="numeric" placeholder="Opcional">
        </div>
      </div>

      <div class="field">
        <label for="tracking-notas-${id}">Notas</label>
        <textarea class="tracking-notas" id="tracking-notas-${id}" rows="2" placeholder="Hallazgos, trabajo realizado…"></textarea>
      </div>

      <fieldset class="field repuestos-fieldset">
        <legend class="repuestos-legend">Repuestos usados</legend>
        <div class="lista-partes-checkbox">${filasPartes}</div>
      </fieldset>

      <div class="form-actions">
        <button type="submit">${icono('check')}Guardar seguimiento</button>
        <button type="button" class="btn-ghost btn-toggle-seguimiento">Cancelar</button>
      </div>
    </form>
  `;
  return tarjeta;
}

function mostrarFormulario(tarjeta, visible) {
  tarjeta.querySelector('.form-seguimiento').classList.toggle('oculto', !visible);
  tarjeta.querySelectorAll('.btn-toggle-seguimiento')[0].setAttribute('aria-expanded', String(visible));
  tarjeta.querySelector('.card-footer').classList.toggle('oculto', visible);
}

// --- Delegación de eventos: todo dentro de #lista-citas ---

listaCitas.addEventListener('click', async (e) => {
  const tarjeta = e.target.closest('.tarjeta-servicio');
  if (!tarjeta) return;
  const appointmentId = tarjeta.dataset.appointmentId;
  const objetivo = e.target.closest('button, input') || e.target;

  // Guardar cambio de estado de la cita
  if (objetivo.classList.contains('btn-guardar-estado')) {
    const nuevoEstado = tarjeta.querySelector('.select-estado-cita').value;
    const errorEl = tarjeta.querySelector('.mensaje-error');
    const exitoEl = tarjeta.querySelector('.mensaje-exito');
    errorEl.textContent = '';
    exitoEl.textContent = '';

    objetivo.disabled = true;
    try {
      await apiPut(`/appointments/${appointmentId}/status`, { status: nuevoEstado });
      exitoEl.textContent = 'Estado actualizado.';
      tarjeta.querySelector('.estado-badge').innerHTML = badgeEstado('cita', nuevoEstado);
    } catch (error) {
      errorEl.textContent = error.message;
    } finally {
      objetivo.disabled = false;
    }
  }

  // Mostrar/ocultar formulario de seguimiento
  if (objetivo.classList.contains('btn-toggle-seguimiento')) {
    const visible = tarjeta.querySelector('.form-seguimiento').classList.contains('oculto');
    mostrarFormulario(tarjeta, visible);
    if (visible) tarjeta.querySelector('.tracking-estado').focus();
  }

  // Habilitar/deshabilitar el input de cantidad según el checkbox
  if (objetivo.classList.contains('check-parte')) {
    const inputCantidad = objetivo.closest('.fila-parte').querySelector('.cantidad-parte');
    inputCantidad.disabled = !objetivo.checked;
  }
});

listaCitas.addEventListener('submit', async (e) => {
  if (!e.target.classList.contains('form-seguimiento')) return;
  e.preventDefault();

  const tarjeta = e.target.closest('.tarjeta-servicio');
  const appointmentId = tarjeta.dataset.appointmentId;
  const errorEl = tarjeta.querySelector('.mensaje-error');
  const exitoEl = tarjeta.querySelector('.mensaje-exito');
  errorEl.textContent = '';
  exitoEl.textContent = '';

  // Armamos parts_used solo con los checkboxes marcados
  const partsUsed = [];
  tarjeta.querySelectorAll('.check-parte:checked').forEach(chk => {
    const cantidad = chk.closest('.fila-parte').querySelector('.cantidad-parte').value;
    partsUsed.push({ part_id: parseInt(chk.value), quantity: parseInt(cantidad) });
  });

  const body = {
    status: e.target.querySelector('.tracking-estado').value,
    notes: e.target.querySelector('.tracking-notas').value || null,
    current_mileage: e.target.querySelector('.tracking-kilometraje').value
      ? parseInt(e.target.querySelector('.tracking-kilometraje').value)
      : null,
  };
  if (partsUsed.length > 0) {
    body.parts_used = partsUsed;
  }

  const botonGuardar = e.target.querySelector('button[type="submit"]');
  botonGuardar.disabled = true;
  try {
    await apiPost(`/tracking/appointment/${appointmentId}`, body);
    exitoEl.textContent = `Seguimiento registrado: ${nombreEstado('seguimiento', body.status)}.`;
    e.target.reset();
    e.target.querySelectorAll('.cantidad-parte').forEach(input => { input.disabled = true; });
    mostrarFormulario(tarjeta, false);
  } catch (error) {
    errorEl.textContent = error.message;
  } finally {
    botonGuardar.disabled = false;
  }
});

cargarTodo().catch(errorNoControlado);
