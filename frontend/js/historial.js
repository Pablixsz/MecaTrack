// frontend/js/historial.js
// Muestra vehículos (con editar/borrar), citas (con estado de pago) y el
// listado de pagos del cliente logueado.

const listaVehiculos = document.getElementById('lista-vehiculos');
const vehiculosErrorEl = document.getElementById('vehiculos-error');
const listaCitas = document.getElementById('lista-citas');
const citasErrorEl = document.getElementById('citas-error');
const listaPagos = document.getElementById('lista-pagos');

const bloqueEditar = document.getElementById('bloque-editar-vehiculo');

// Diccionarios id -> nombre, para no repetir fetch por cada cita
let mapaVehiculos = new Map();
let mapaServicios = new Map();

const NOMBRES_TIPO_VEHICULO = { car: 'Carro', motorcycle: 'Moto', truck: 'Camión', van: 'Van' };
const NOMBRES_METODO_PAGO = { cash: 'Efectivo', card: 'Tarjeta', transfer: 'Transferencia' };

function actualizarContador(id, n) {
  document.getElementById(id).textContent = n;
}

// --- VEHÍCULOS ---

async function cargarVehiculos() {
  try {
    const vehiculos = await apiGet('/vehicles');
    mapaVehiculos = new Map(vehiculos.map(v => [v.vehicle_id, v]));
    renderizarVehiculos(vehiculos);
  } catch (error) {
    listaVehiculos.innerHTML = '';
    vehiculosErrorEl.textContent = 'No se pudieron cargar tus vehículos: ' + error.message;
  }
}

function renderizarVehiculos(vehiculos) {
  listaVehiculos.innerHTML = '';
  actualizarContador('count-vehiculos', vehiculos.length);

  if (vehiculos.length === 0) {
    listaVehiculos.innerHTML = estadoVacio({
      icon: 'auto',
      titulo: 'Aún no tienes vehículos',
      texto: 'Registrarás tu vehículo al agendar tu primera cita.',
      accion: { href: 'catalogo.html', texto: 'Agendar una cita' },
    });
    return;
  }

  vehiculos.forEach(v => {
    const tarjeta = document.createElement('article');
    tarjeta.className = 'card';
    tarjeta.innerHTML = `
      <div class="card-header">
        <span class="icon-tile">${icono('auto')}</span>
        <span class="plate">${esc(v.license_plate)}</span>
      </div>
      <div>
        <h3 class="card-title">${esc(v.brand)} ${esc(v.model)}</h3>
        <p class="card-subtitle">${esc(v.year)} · ${esc(NOMBRES_TIPO_VEHICULO[v.vehicle_type] || v.vehicle_type)}</p>
      </div>
      <div class="card-footer">
        <button class="btn-secundario btn-sm btn-editar-vehiculo" data-id="${v.vehicle_id}">${icono('editar')}Editar</button>
        <button class="btn-danger btn-sm btn-borrar-vehiculo" data-id="${v.vehicle_id}">${icono('basura')}Eliminar</button>
      </div>
    `;
    listaVehiculos.appendChild(tarjeta);
  });
}

// Delegación de eventos: un solo listener para editar y borrar
listaVehiculos.addEventListener('click', async (e) => {
  const boton = e.target.closest('button[data-id]');
  if (!boton) return;
  const id = boton.dataset.id;

  if (boton.classList.contains('btn-editar-vehiculo')) {
    abrirFormularioEdicion(id);
  }

  if (boton.classList.contains('btn-borrar-vehiculo')) {
    if (!confirm('¿Seguro que quieres eliminar este vehículo?')) return;
    try {
      await apiDelete(`/vehicles/${id}`);
      cargarVehiculos().catch(errorNoControlado); // recargamos la lista
    } catch (error) {
      vehiculosErrorEl.textContent = error.message;
    }
  }
});

function abrirFormularioEdicion(id) {
  const v = mapaVehiculos.get(Number(id));
  document.getElementById('edit-veh-id').value = v.vehicle_id;
  document.getElementById('edit-veh-placa').value = v.license_plate;
  document.getElementById('edit-veh-marca').value = v.brand;
  document.getElementById('edit-veh-modelo').value = v.model;
  document.getElementById('edit-veh-anio').value = v.year;
  bloqueEditar.classList.remove('oculto');
  document.getElementById('edit-veh-marca').focus();
}

document.getElementById('btn-cancelar-edicion').addEventListener('click', () => {
  bloqueEditar.classList.add('oculto');
});

document.getElementById('form-editar-vehiculo').addEventListener('submit', async (e) => {
  e.preventDefault();
  const id = document.getElementById('edit-veh-id').value;

  try {
    await apiPut(`/vehicles/${id}`, {
      license_plate: document.getElementById('edit-veh-placa').value,
      brand: document.getElementById('edit-veh-marca').value,
      model: document.getElementById('edit-veh-modelo').value,
      year: parseInt(document.getElementById('edit-veh-anio').value),
    });
    bloqueEditar.classList.add('oculto');
    cargarVehiculos().catch(errorNoControlado);
  } catch (error) {
    vehiculosErrorEl.textContent = error.message;
  }
});

// --- CITAS Y PAGOS ---

async function cargarServiciosParaMapa() {
  const servicios = await apiGet('/services');
  mapaServicios = new Map(servicios.map(s => [s.service_id, s]));
}

async function cargarCitas() {
  citasErrorEl.textContent = ''; // limpiamos cualquier error viejo antes de recargar
  try {
    await cargarServiciosParaMapa();
    const citas = await apiGet('/appointments');
    await renderizarCitas(citas);
  } catch (error) {
    listaCitas.innerHTML = '';
    listaPagos.innerHTML = '';
    citasErrorEl.textContent = 'No se pudieron cargar tus citas: ' + error.message;
  }
}

function nombreServicio(cita) {
  const servicio = mapaServicios.get(cita.service_id);
  return servicio ? servicio.service_name : (cita.service_name || 'Servicio #' + cita.service_id);
}

async function renderizarCitas(citas) {
  listaCitas.innerHTML = '';
  actualizarContador('count-citas', citas.length);

  if (citas.length === 0) {
    listaCitas.innerHTML = estadoVacio({
      icon: 'calendario',
      titulo: 'Aún no tienes citas',
      texto: 'Elige un servicio del catálogo y agenda tu primera cita.',
      accion: { href: 'catalogo.html', texto: 'Ver servicios' },
    });
    renderizarPagos([]);
    return;
  }

  const todosLosPagos = [];

  for (const cita of citas) {
    const vehiculo = mapaVehiculos.get(cita.vehicle_id);
    const pagos = await apiGet(`/payments/appointment/${cita.appointment_id}`);
    pagos.forEach(p => todosLosPagos.push({ ...p, cita }));

    const tarjeta = document.createElement('article');
    tarjeta.className = 'card';

    const htmlPagos = pagos.map(pago => {
      const nombreTipo = pago.payment_type === 'deposit' ? 'Depósito' : 'Saldo';
      const puedePagar = pago.status !== 'completed';
      return `
        <div class="pago-fila">
          <span class="pago-concepto">${nombreTipo}<span class="pago-monto">${esc(pesos(pago.amount))}</span></span>
          <span class="pago-acciones">
            ${badgeEstado('pago', pago.status)}
            ${puedePagar ? `<button class="btn-sm btn-pagar" data-payment-id="${pago.payment_id}">Pagar</button>` : ''}
          </span>
        </div>`;
    }).join('');

    const puedeCancel = cita.status !== 'completed' && cita.status !== 'cancelled';

    tarjeta.innerHTML = `
      <div class="card-header">
        <div>
          <h3 class="card-title">${esc(nombreServicio(cita))}</h3>
          <p class="card-subtitle">Cita #${cita.appointment_id}</p>
        </div>
        ${badgeEstado('cita', cita.status)}
      </div>
      <ul class="meta-list">
        <li>${icono('calendario')}<strong>${esc(fechaLarga(cita.scheduled_start))}</strong></li>
        <li>${icono('reloj')}${esc(hora(cita.scheduled_start))} – ${esc(hora(cita.scheduled_end))}</li>
        <li>${icono('auto')}${vehiculo ? `<span class="plate">${esc(vehiculo.license_plate)}</span> ${esc(vehiculo.brand)} ${esc(vehiculo.model)}` : esc(cita.vehicle_plate || cita.vehicle_id)}</li>
      </ul>
      ${pagos.length ? `<div class="cita-pagos">${htmlPagos}</div>` : ''}
      ${puedeCancel ? `
        <div class="card-footer">
          <button class="btn-danger btn-sm btn-cancelar-cita" data-id="${cita.appointment_id}">${icono('x')}Cancelar cita</button>
        </div>` : ''}
    `;

    listaCitas.appendChild(tarjeta);
  }

  renderizarPagos(todosLosPagos);
}

function renderizarPagos(pagos) {
  actualizarContador('count-pagos', pagos.length);

  if (pagos.length === 0) {
    listaPagos.innerHTML = estadoVacio({
      icon: 'tarjeta',
      titulo: 'Aún no tienes pagos',
      texto: 'Al agendar una cita se generan el depósito y el saldo.',
    });
    return;
  }

  listaPagos.innerHTML = `
    <div class="tabla-scroll">
      <table class="tabla">
        <thead>
          <tr>
            <th scope="col">Cita</th><th scope="col">Servicio</th><th scope="col">Concepto</th>
            <th scope="col">Método</th><th scope="col">Estado</th><th scope="col">Pagado el</th>
            <th scope="col" class="num">Monto</th>
          </tr>
        </thead>
        <tbody>
          ${pagos.map(p => `
            <tr>
              <td>#${p.cita.appointment_id}</td>
              <td>${esc(nombreServicio(p.cita))}</td>
              <td>${p.payment_type === 'deposit' ? 'Depósito' : 'Saldo'}</td>
              <td>${esc(NOMBRES_METODO_PAGO[p.payment_method] || p.payment_method)}</td>
              <td>${badgeEstado('pago', p.status)}</td>
              <td>${p.paid_at ? esc(fechaCorta(p.paid_at)) : '—'}</td>
              <td class="num">${esc(pesos(p.amount))}</td>
            </tr>`).join('')}
        </tbody>
      </table>
    </div>`;
}

// Delegación de eventos para pagar y cancelar
listaCitas.addEventListener('click', async (e) => {
  const boton = e.target.closest('button');
  if (!boton) return;

  if (boton.classList.contains('btn-pagar')) {
    const paymentId = boton.dataset.paymentId;
    boton.disabled = true;
    try {
      await apiPost(`/payments/${paymentId}/pay`, {});
      cargarCitas().catch(errorNoControlado); // recargamos para reflejar el nuevo estado
    } catch (error) {
      boton.disabled = false;
      citasErrorEl.textContent = error.message;
    }
  }

  if (boton.classList.contains('btn-cancelar-cita')) {
    if (!confirm('¿Seguro que quieres cancelar esta cita?')) return;
    const id = boton.dataset.id;
    try {
      await apiDelete(`/appointments/${id}`);
      cargarCitas().catch(errorNoControlado);
    } catch (error) {
      citasErrorEl.textContent = error.message;
    }
  }
});

// --- Inicio ---
cargarVehiculos().catch(errorNoControlado);
cargarCitas().catch(errorNoControlado);
