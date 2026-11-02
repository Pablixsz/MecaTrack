// frontend/js/mercado.js
// Panel de mercado (owner/admin): fuentes de datos abiertos con el estado de
// sus circuit breakers, y las consultas analíticas de DuckDB en tabla y gráfico.
// Requiere api.js, ui.js, nav.js y graficos.js.

const API_MERCADO = '/api/v1/market';
const errorEl = document.getElementById('mercado-error');
const infoEl = document.getElementById('mercado-info');
const btnActualizar = document.getElementById('btn-actualizar');

const numero = new Intl.NumberFormat('es-CO');
const decimal = new Intl.NumberFormat('es-CO', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const NOMBRES_TIPO = { car: 'Carros', motorcycle: 'Motos', truck: 'Camiones', van: 'Busetas y microbuses' };
const RANGOS = ['0-4', '5-9', '10-14', '15-19', '20+'];
// Estado del breaker -> [texto, variante de insignia, icono]: nunca solo color.
const ESTADO_CIRCUITO = {
  CLOSED: ['Cerrado · llamadas pasan', 'success', 'check'],
  HALF_OPEN: ['Semiabierto · 1 llamada de prueba', 'warning', 'pausa'],
  OPEN: ['Abierto · llamadas rechazadas', 'danger', 'alerta'],
};

let ultimoRefresh = {};

function mostrarError(error) {
  errorEl.textContent = error.message || String(error);
  if (error.status === 401) window.location.href = '../index.html';
}

// Columnas que son medidas con decimales (JSON convierte 87.0 en 87).
const COLUMNAS_DECIMALES = new Set(['media', 'desviacion', 'pct_10_anios_o_mas', 'vehiculos_por_1000_hab',
  'carros_por_1000_hab', 'pct_motos', 'pct_del_tipo']);

function celda(valor, tipo, clave = '') {
  if (valor === null || valor === undefined) return '<td class="num">—</td>';
  if (tipo === 'number') return `<td class="num">${esc(COLUMNAS_DECIMALES.has(clave) ? decimal.format(valor) : numero.format(valor))}</td>`;
  return `<td>${esc(valor)}</td>`;
}

function dibujarTabla(tabla, resultado, columnas = resultado.columns) {
  tabla.innerHTML = `
    <thead><tr>${columnas.map(c => `<th class="${c.type === 'number' ? 'num' : ''}">${esc(c.label)}</th>`).join('')}</tr></thead>
    <tbody>${resultado.rows.map(fila => `<tr>${columnas.map(c => celda(c.key === 'tipo_taller'
      ? NOMBRES_TIPO[fila[c.key]] : fila[c.key], c.type, c.key)).join('')}</tr>`).join('')}</tbody>`;
}

function estadistica(etiqueta, valor, nota = '') {
  return `<div class="estadistica"><span class="estadistica-valor">${esc(valor)}</span>`
    + `<span class="estadistica-etiqueta">${esc(etiqueta)}</span>${nota ? `<span class="estadistica-nota">${esc(nota)}</span>` : ''}</div>`;
}

// --- Fuentes y circuit breakers ---

function dibujarCircuitos(circuitos) {
  document.getElementById('circuitos').innerHTML = circuitos.map(c => {
    const [texto, variante, icon] = ESTADO_CIRCUITO[c.state] || [c.state, 'neutral', 'alerta'];
    const ultimas = c.transitions.slice(-3).reverse();
    return `
      <article class="circuito circuito-${variante}">
        <div class="circuito-cabecera">
          <strong>${esc(c.name)}</strong>
          <span class="badge badge-${variante} badge-plain">${icono(icon)}${esc(c.state)}</span>
        </div>
        <p class="circuito-texto">${esc(texto)}</p>
        <p class="circuito-meta">Fallos seguidos: <strong>${c.consecutive_failures}/${c.failure_threshold}</strong>
          · recuperación ${c.recovery_timeout_s} s${c.retry_in_s != null ? ` · próxima prueba en ${c.retry_in_s.toFixed(1)} s` : ''}</p>
        ${ultimas.length ? `<ul class="circuito-transiciones">${ultimas.map(t => `
          <li><span>${esc(new Date(t.at).toLocaleTimeString('es-CO'))}</span> ${esc(t.from)} → <strong>${esc(t.to)}</strong>
            <small>${esc(t.reason)}</small></li>`).join('')}</ul>` : '<p class="circuito-meta">Sin transiciones desde que arrancó el servidor.</p>'}
      </article>`;
  }).join('');
}

function dibujarFuentes(fuentes) {
  document.getElementById('tabla-fuentes').innerHTML = fuentes.map(f => {
    const intento = ultimoRefresh[f.key];
    const estado = !intento ? '<span class="texto-suave">—</span>'
      : intento.ok ? `<span class="badge badge-success badge-plain">${icono('check')}OK · ${numero.format(intento.elapsed_ms)} ms</span>`
        : `<span class="badge badge-danger badge-plain" title="${esc(intento.error)}">${icono('alerta')}${intento.circuit_open ? 'Circuito abierto' : 'Falló'}</span>`;
    return `<tr>
      <td><strong>${esc(f.title)}</strong><br><small class="texto-suave">${esc(f.url)}</small></td>
      <td>${esc(f.publisher)}</td>
      ${celda(f.rows, 'number')}
      <td>${f.fetched_at ? esc(new Date(`${f.fetched_at}Z`).toLocaleString('es-CO')) : '<span class="texto-suave">Nunca</span>'}</td>
      <td>${estado}</td></tr>`;
  }).join('');
}

async function cargarFuentes() {
  const datos = await apiGet(`${API_MERCADO}/sources`);
  dibujarCircuitos(datos.circuits);
  dibujarFuentes(datos.sources);
  return datos.sources.every(f => f.fetched_at);
}

// --- Analítica ---

function dibujarMotorizacion(r) {
  document.getElementById('desc-motorizacion').textContent = r.description;
  const s = r.summary;
  document.getElementById('resumen-motorizacion').innerHTML = [
    estadistica('Nacional', decimal.format(s.nacional_por_1000_hab), 'total vehículos / total población'),
    estadistica('Media entre deptos.', decimal.format(s.media)),
    estadistica('Mediana', decimal.format(s.mediana)),
    estadistica('Desv. estándar', decimal.format(s.desviacion)),
    estadistica('Rango intercuartil', `${decimal.format(s.p25)} – ${decimal.format(s.p75)}`),
    estadistica('Mín. – máx.', `${decimal.format(s.minimo)} – ${decimal.format(s.maximo)}`),
  ].join('');

  graficoBarrasHorizontales(document.getElementById('grafico-motorizacion'), {
    items: r.rows.map(f => ({
      etiqueta: f.departamento.length > 26 ? `${f.departamento.slice(0, 24)}…` : f.departamento,
      valor: f.vehiculos_por_1000_hab,
      detalle: f.vehiculos ? `${numero.format(f.vehiculos)} vehículos · ${numero.format(f.poblacion_2018)} hab. · ${decimal.format(f.pct_motos)} % motos` : 'Sin registros en RUNT',
    })),
    referencia: { valor: s.nacional_por_1000_hab, etiqueta: 'Nacional' },
    formato: v => numero.format(Math.round(v)),
    unidad: 'vehículos por 1.000 hab.',
  });
  dibujarTabla(document.getElementById('tabla-motorizacion'), r);
  document.getElementById('sql-motorizacion').textContent = `-- ${r.elapsed_ms} ms en DuckDB\n${r.sql}`;
  if (s.sin_vehiculos_en_runt?.length) {
    document.getElementById('desc-motorizacion').textContent += ` Sin registros en RUNT: ${s.sin_vehiculos_en_runt.join(', ')}.`;
  }
}

function dibujarAntiguedad(r) {
  document.getElementById('desc-antiguedad').textContent = r.description;
  dibujarTabla(document.getElementById('tabla-antiguedad'), r);
  document.getElementById('sql-antiguedad').textContent = `-- ${r.elapsed_ms} ms en DuckDB\n${r.sql}`;
  const s = r.summary;
  document.getElementById('kpis').innerHTML = [
    estadistica('Vehículos analizados', numero.format(s.vehiculos_analizados), `RUNT · corte ${s.corte_runt}`),
    estadistica('Antigüedad media', `${decimal.format(s.antiguedad_media_ponderada)} años`, 'ponderada por vehículos'),
    estadistica('Motos: mediana', `${r.rows.find(x => x.clase === 'MOTOCICLETA')?.mediana ?? '—'} años`),
    estadistica('Automóviles: mediana', `${r.rows.find(x => x.clase === 'AUTOMOVIL')?.mediana ?? '—'} años`),
    estadistica('Excluidos por calidad', numero.format(s.excluidos_por_calidad), `registro antes de ${s.anio_minimo_valido}`),
  ].join('');
}

function dibujarDistribucion(r) {
  const colores = Object.fromEntries(RANGOS.map((rango, i) => [rango, `--viz-ord-${i + 1}`]));
  document.getElementById('leyenda-distribucion').innerHTML = RANGOS.map(rango =>
    `<span class="leyenda-item"><span class="leyenda-color" style="background: var(${colores[rango]})"></span>${esc(rango)} años</span>`).join('');
  const tipos = [...new Set(r.rows.map(f => f.tipo_taller))];
  graficoApilado100(document.getElementById('grafico-distribucion'), {
    grupos: tipos.map(tipo => ({
      etiqueta: NOMBRES_TIPO[tipo] || tipo,
      segmentos: r.rows.filter(f => f.tipo_taller === tipo).map(f => ({
        clave: f.rango, valor: f.pct_del_tipo, detalle: `${numero.format(f.vehiculos)} vehículos` })),
    })),
    orden: RANGOS,
    colores,
  });
  document.getElementById('sql-distribucion').textContent = `-- ${r.elapsed_ms} ms en DuckDB\n${r.sql}`;
}

async function cargarAnalitica() {
  const [antiguedad, motorizacion, distribucion] = await Promise.all([
    apiGet(`${API_MERCADO}/analytics/fleet-age`),
    apiGet(`${API_MERCADO}/analytics/motorization`),
    apiGet(`${API_MERCADO}/analytics/age-distribution`),
  ]);
  dibujarAntiguedad(antiguedad);
  dibujarMotorizacion(motorizacion);
  dibujarDistribucion(distribucion);
}

// --- Acciones ---

async function actualizarDatos() {
  btnActualizar.disabled = true;
  btnActualizar.querySelector('span:last-child').textContent = 'Descargando…';
  errorEl.textContent = '';
  infoEl.textContent = 'Consultando datos.gov.co y el geoportal del DANE (con reintentos si alguna falla)…';
  try {
    const respuesta = await apiPost(`${API_MERCADO}/refresh`, {});
    ultimoRefresh = Object.fromEntries(respuesta.results.map(r => [r.source, r]));
    const fallidas = respuesta.results.filter(r => !r.ok);
    infoEl.textContent = fallidas.length
      ? `Fallaron ${fallidas.length} de ${respuesta.results.length} fuentes; se conserva su descarga anterior.`
      : `Datos actualizados: ${respuesta.results.map(r => `${r.source} ${numero.format(r.rows)} registros`).join(' · ')}.`;
    await cargarFuentes();
    await cargarAnalitica().catch(mostrarError);
  } catch (error) {
    mostrarError(error);
  } finally {
    btnActualizar.disabled = false;
    btnActualizar.querySelector('span:last-child').textContent = 'Actualizar datos';
  }
}

async function iniciar() {
  btnActualizar.querySelector('.btn-icono').innerHTML = icono('actualizar');
  const usuario = await sesionActual;
  if (!usuario || !['owner', 'admin'].includes(usuario.role)) {
    window.location.href = usuario ? 'catalogo.html' : '../index.html';
    return;
  }
  try {
    const completas = await cargarFuentes();
    if (!completas) {
      infoEl.textContent = 'Aún no se han descargado los datos abiertos. Pulsa «Actualizar datos».';
      return;
    }
    await cargarAnalitica();
  } catch (error) {
    mostrarError(error);
  }
}

btnActualizar.addEventListener('click', actualizarDatos);
iniciar().catch(errorNoControlado);
