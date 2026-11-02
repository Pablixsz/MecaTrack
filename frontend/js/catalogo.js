// frontend/js/catalogo.js
// Carga el catálogo público de servicios y arma las tarjetas.

const contenedorServicios = document.getElementById('lista-servicios');
const errorEl = document.getElementById('catalogo-error');
const cargandoEl = document.getElementById('catalogo-cargando');

async function cargarServicios() {
  try {
    const servicios = await apiGet('/services');
    cargandoEl.classList.add('oculto');
    renderizarServicios(servicios);
  } catch (error) {
    cargandoEl.classList.add('oculto');
    errorEl.textContent = 'No se pudieron cargar los servicios: ' + error.message;
  }
}

function renderizarServicios(servicios) {
  if (servicios.length === 0) {
    contenedorServicios.innerHTML = estadoVacio({
      icon: 'llave',
      titulo: 'Aún no hay servicios disponibles',
      texto: 'Vuelve pronto: el taller está preparando su catálogo.',
    });
    return;
  }

  servicios.forEach(servicio => {
    const tarjeta = document.createElement('article');
    tarjeta.className = 'tarjeta-servicio';

    tarjeta.innerHTML = `
      <div class="card-header">
        <span class="icon-tile">${icono('llave')}</span>
        <span class="badge badge-neutral badge-plain">${icono('reloj')}${servicio.estimated_duration_minutes} min</span>
      </div>
      <h2 class="card-title">${esc(servicio.service_name)}</h2>
      <p class="servicio-descripcion">${esc(servicio.description || 'Servicio del taller.')}</p>
      <p class="precio-servicio">${esc(pesos(servicio.base_price))}<small>Depósito del 30% al agendar</small></p>
      <button class="btn-agendar" data-id="${servicio.service_id}">${icono('calendario')}Agendar</button>
    `;

    contenedorServicios.appendChild(tarjeta);
  });

  // Un solo listener para todos los botones (event delegation),
  // en vez de agregar un listener por cada tarjeta.
  contenedorServicios.addEventListener('click', (e) => {
    const boton = e.target.closest('.btn-agendar');
    if (boton) {
      window.location.href = `calendario.html?service_id=${boton.dataset.id}`;
    }
  });
}

cargarServicios().catch(errorNoControlado);
