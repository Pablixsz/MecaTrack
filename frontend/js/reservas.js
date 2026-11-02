// frontend/js/reservas.js
// Lógica de la página de agendamiento: carga vehículos, maneja el form
// de vehículo nuevo si hace falta, y envía la reserva.

// --- Leer el service_id de la URL ---
const params = new URLSearchParams(window.location.search);
const serviceId = params.get('service_id');

const infoEl = document.getElementById('calendario-info');
const bloqueSelector = document.getElementById('bloque-selector-vehiculo');
const bloqueNuevoVehiculo = document.getElementById('bloque-nuevo-vehiculo');
const selectVehiculo = document.getElementById('select-vehiculo');
const errorEl = document.getElementById('agendar-error');
const exitoEl = document.getElementById('agendar-exito');

const resumenEl = document.getElementById('resumen-servicio-detalle');
const botonConfirmar = document.getElementById('btn-confirmar');
const inputFecha = document.getElementById('input-fecha-hora');

if (!serviceId) {
  infoEl.textContent = 'No se especificó un servicio. Vuelve al catálogo y elige uno.';
} else {
  infoEl.textContent = 'Elige tu vehículo y la fecha. Te asignamos bahía y mecánico al confirmar.';
}

// No permitir elegir una fecha pasada en el selector (formato YYYY-MM-DDTHH:MM local).
const ahora = new Date();
ahora.setMinutes(ahora.getMinutes() - ahora.getTimezoneOffset());
inputFecha.min = ahora.toISOString().slice(0, 16);

// Resumen del servicio elegido (mismo endpoint público del catálogo).
async function cargarResumenServicio() {
  if (!serviceId) {
    resumenEl.innerHTML = estadoVacio({ icon: 'llave', titulo: 'Sin servicio', texto: 'Elige un servicio del catálogo.',
      accion: { href: 'catalogo.html', texto: 'Ver servicios' } });
    return;
  }
  try {
    const servicios = await apiGet('/services');
    const servicio = servicios.find(s => String(s.service_id) === String(serviceId));
    if (!servicio) {
      resumenEl.innerHTML = '<p class="mensaje-error">Este servicio ya no está disponible.</p>';
      return;
    }
    const deposito = Math.round(servicio.base_price * 0.3);
    resumenEl.innerHTML = `
      <p class="card-title">${esc(servicio.service_name)}</p>
      <p class="servicio-descripcion">${esc(servicio.description || '')}</p>
      <ul class="meta-list resumen-meta">
        <li>${icono('reloj')}Duración estimada: <strong>${servicio.estimated_duration_minutes} min</strong></li>
        <li>${icono('tarjeta')}Depósito al agendar: <strong>${esc(pesos(deposito))}</strong></li>
      </ul>
      <p class="precio-servicio resumen-precio">${esc(pesos(servicio.base_price))}<small>Precio base del servicio</small></p>`;
  } catch (error) {
    resumenEl.innerHTML = `<p class="mensaje-error">${esc(error.message)}</p>`;
  }
}

cargarResumenServicio().catch(errorNoControlado);

// Todos los inputs required dentro del bloque de vehículo nuevo
const camposNuevoVehiculo = bloqueNuevoVehiculo.querySelectorAll('input, select');

function toggleRequiredNuevoVehiculo(activar) {
  camposNuevoVehiculo.forEach(campo => {
    campo.required = activar;
  });
}

async function cargarVehiculos() {
  try {
    const vehiculos = await apiGet('/vehicles');

    if (vehiculos.length === 0) {
      // No tiene vehículos: ocultamos el selector, mostramos el formulario nuevo
      bloqueSelector.classList.add('oculto');
      bloqueNuevoVehiculo.classList.remove('oculto');
      toggleRequiredNuevoVehiculo(true); // ahora sí son obligatorios
    } else {
      vehiculos.forEach(v => {
        const option = document.createElement('option');
        option.value = v.vehicle_id;
        option.textContent = `${v.brand} ${v.model} - ${v.license_plate}`;
        selectVehiculo.appendChild(option);
      });
      toggleRequiredNuevoVehiculo(false); // están ocultos, no deben bloquear el envío
    }
  } catch (error) {
    errorEl.textContent = 'No se pudieron cargar tus vehículos: ' + error.message;
  }
}

cargarVehiculos().catch(errorNoControlado);

// --- Envío del formulario ---
document.getElementById('form-agendar').addEventListener('submit', async (e) => {
  e.preventDefault();
  errorEl.textContent = '';
  exitoEl.textContent = '';

  if (!serviceId) {
    errorEl.textContent = 'Falta el servicio. Vuelve al catálogo.';
    return;
  }

  botonConfirmar.disabled = true;

  try {
    let vehicleId;

    // Si el bloque de vehículo nuevo está visible, primero creamos el vehículo
    if (!bloqueNuevoVehiculo.classList.contains('oculto')) {
      const nuevoVehiculo = await apiPost('/vehicles', {
        license_plate: document.getElementById('veh-placa').value,
        brand: document.getElementById('veh-marca').value,
        model: document.getElementById('veh-modelo').value,
        year: parseInt(document.getElementById('veh-anio').value),
        vehicle_type: document.getElementById('veh-tipo').value,
        fuel_type: document.getElementById('veh-combustible').value,
        transmission_type: document.getElementById('veh-transmision').value,
      });
      vehicleId = nuevoVehiculo.vehicle_id;
    } else {
      vehicleId = selectVehiculo.value;
    }

    // El input datetime-local da algo como "2026-09-25T09:00" (sin segundos).
    // Le agregamos ":00" para dejarlo en formato ISO 8601 completo, tal como
    // lo espera el backend.
    const fechaHora = document.getElementById('input-fecha-hora').value + ':00';

    const cita = await apiPost('/appointments', {
      vehicle_id: vehicleId,
      service_id: parseInt(serviceId),
      scheduled_start: fechaHora,
    });

    exitoEl.innerHTML = `Cita agendada para el ${esc(fechaLarga(cita.scheduled_start))} a las ${esc(hora(cita.scheduled_start))}. `
      + `Paga el depósito de <strong>${esc(pesos(cita.deposit_amount))}</strong> en <a href="historial-cliente.html">tu historial</a> para confirmarla.`;
    document.getElementById('form-agendar').reset();

  } catch (error) {
    if (error.status === 409) {
      errorEl.textContent = 'No hay disponibilidad en ese horario. Prueba con otra fecha u hora.';
    } else {
      errorEl.textContent = error.message;
    }
  } finally {
    botonConfirmar.disabled = false;
  }
});