"""
Consultas analiticas de DuckDB sobre los JSON descargados de datos.gov.co y
del geoportal del DANE.

Vistas que crea DuckDbMarketAnalytics antes de cada consulta (read_json):
    runt       parque automotor ACTIVO: departamento, clase, año de registro, vehiculos (texto)
    divipola   codigos y nombres de departamentos y municipios (DANE)
    poblacion  poblacion censada CNPV 2018 por municipio (DANE)

Reglas comunes:
- Socrata entrega todo como texto: se hace CAST explicito.
- Calidad de datos: se excluyen registros con año de registro < 1950
  (0,04 % del parque; incluye valores de relleno como 1900 y 1901).
- Antiguedad = año de corte de la publicacion RUNT - año de registro.
- Solo las clases que atiende un taller como MecaTrack, agrupadas en los
  tipos de vehiculo del sistema (car, motorcycle, truck, van).
"""

MIN_REGISTRATION_YEAR = 1950

# Clase RUNT (sin tildes) -> tipo de vehiculo de MecaTrack (vehicles.vehicle_type)
WORKSHOP_CLASSES = """clases_taller(clase, tipo_taller) AS (VALUES
    ('AUTOMOVIL', 'car'), ('CAMIONETA', 'car'), ('CAMPERO', 'car'),
    ('MOTOCICLETA', 'motorcycle'),
    ('CAMION', 'truck'), ('VOLQUETA', 'truck'), ('TRACTOCAMION', 'truck'),
    ('MICROBUS', 'van'), ('BUSETA', 'van')
)"""

RUNT_CLEAN = f"""runt_limpio AS (
    SELECT strip_accents(upper(trim(r.nombre_departamento)))  AS departamento,
           c.clase, c.tipo_taller,
           CAST(r.fecha_de_registro AS INTEGER)               AS anio_registro,
           CAST(r.anio_publicacion AS INTEGER)                AS anio_corte,
           CAST(r.vehiculos AS BIGINT)                        AS vehiculos
    FROM runt r
    JOIN clases_taller c ON c.clase = strip_accents(upper(trim(r.nombre_de_la_clase)))
    WHERE CAST(r.fecha_de_registro AS INTEGER) >= {MIN_REGISTRATION_YEAR}
)"""  # constant SQL assembled at import time, no user input  # nosec B608

# --------------------------------------------------------------------------------------------
# Q1. Antiguedad del parque por clase: estadisticas descriptivas PONDERADAS por cantidad.
#     Los datos vienen agregados (una fila = N vehiculos con el mismo año), por eso la media y
#     la desviacion usan pesos y los percentiles se toman de la distribucion acumulada:
#     percentil q = menor antiguedad cuya frecuencia acumulada alcanza q * total.
# --------------------------------------------------------------------------------------------
FLEET_AGE_BY_CLASS = f"""
WITH {WORKSHOP_CLASSES},
{RUNT_CLEAN},
por_edad AS (
    SELECT clase, tipo_taller, anio_corte - anio_registro AS antiguedad, SUM(vehiculos) AS n
    FROM runt_limpio
    GROUP BY ALL
),
acumulado AS (
    SELECT *,
           SUM(n) OVER (PARTITION BY clase ORDER BY antiguedad) AS n_acumulado,
           SUM(n) OVER (PARTITION BY clase)                     AS total,
           SUM(n * antiguedad) OVER (PARTITION BY clase)
             / SUM(n) OVER (PARTITION BY clase)                 AS media
    FROM por_edad
)
SELECT clase,
       any_value(tipo_taller)                                                   AS tipo_taller,
       any_value(total)::BIGINT                                                 AS vehiculos,
       round(any_value(media), 2)                                               AS media,
       round(sqrt(SUM(n * (antiguedad - media) ^ 2) / any_value(total)), 2)    AS desviacion,
       MIN(antiguedad)                                                          AS minimo,
       MIN(antiguedad) FILTER (WHERE n_acumulado >= 0.25 * total)               AS p25,
       MIN(antiguedad) FILTER (WHERE n_acumulado >= 0.50 * total)               AS mediana,
       MIN(antiguedad) FILTER (WHERE n_acumulado >= 0.75 * total)               AS p75,
       MIN(antiguedad) FILTER (WHERE n_acumulado >= 0.90 * total)               AS p90,
       MAX(antiguedad)                                                          AS maximo,
       round(100.0 * SUM(n) FILTER (WHERE antiguedad >= 10) / any_value(total), 1) AS pct_10_anios_o_mas
FROM acumulado
GROUP BY clase
ORDER BY vehiculos DESC
"""  # constant SQL assembled at import time, no user input  # nosec B608

# --------------------------------------------------------------------------------------------
# Q2. Motorizacion por departamento: vehiculos (clases del taller) por cada 1.000 habitantes,
#     cruzando RUNT (MinTransporte) con la poblacion CNPV 2018 (DANE) via DIVIPOLA.
#     Los nombres se comparan normalizados a solo letras ("BOGOTA D.C." = "BOGOTA, D.C.").
#     RUNT recorta "ARCHIPIELAGO DE SAN ANDRES, PROVIDENCIA": si no hay coincidencia exacta
#     se acepta por prefijo, solo para claves largas (>= 10 letras).
# --------------------------------------------------------------------------------------------
MOTORIZATION_BY_DEPARTMENT = f"""
WITH {WORKSHOP_CLASSES},
{RUNT_CLEAN},
vehiculos_depto AS (
    SELECT regexp_replace(departamento, '[^A-Z]', '', 'g')         AS clave,
           SUM(vehiculos)                                         AS vehiculos,
           SUM(vehiculos) FILTER (WHERE tipo_taller = 'motorcycle') AS motos,
           SUM(vehiculos) FILTER (WHERE tipo_taller = 'car')        AS carros
    FROM runt_limpio
    GROUP BY clave
),
departamentos AS (
    SELECT DISTINCT cod_dpto, dpto,
           regexp_replace(strip_accents(upper(dpto)), '[^A-Z]', '', 'g') AS clave
    FROM divipola
),
poblacion_depto AS (
    SELECT cod_dpto, SUM(CAST(poblacion AS BIGINT)) AS poblacion
    FROM poblacion
    GROUP BY cod_dpto
),
clave_resuelta AS (
    -- Clave DIVIPOLA de cada departamento RUNT: exacta y, si no hay, por prefijo.
    SELECT v.*,
           coalesce((SELECT d.clave FROM departamentos d WHERE d.clave = v.clave),
                    (SELECT min(d.clave) FROM departamentos d
                     WHERE length(v.clave) >= 10 AND starts_with(d.clave, v.clave))) AS clave_divipola
    FROM vehiculos_depto v
),
vehiculos_divipola AS (
    SELECT clave_divipola, SUM(vehiculos) AS vehiculos, SUM(motos) AS motos, SUM(carros) AS carros
    FROM clave_resuelta
    GROUP BY clave_divipola
),
cruce AS (
    SELECT d.cod_dpto, d.dpto, p.poblacion, v.vehiculos, v.motos, v.carros
    FROM departamentos d
    JOIN poblacion_depto p USING (cod_dpto)
    LEFT JOIN vehiculos_divipola v ON v.clave_divipola = d.clave
)
SELECT cod_dpto,
       dpto                                                    AS departamento,
       poblacion::BIGINT                                       AS poblacion_2018,
       coalesce(vehiculos, 0)::BIGINT                          AS vehiculos,
       round(1000.0 * vehiculos / poblacion, 1)                AS vehiculos_por_1000_hab,
       round(1000.0 * carros / poblacion, 1)                   AS carros_por_1000_hab,
       round(100.0 * motos / vehiculos, 1)                     AS pct_motos,
       rank() OVER (ORDER BY vehiculos / poblacion DESC NULLS LAST) AS puesto
FROM cruce
ORDER BY puesto, cod_dpto
"""  # constant SQL assembled at import time, no user input  # nosec B608

# Estadisticas descriptivas ENTRE departamentos de la consulta anterior (cada depto pesa 1).
MOTORIZATION_SUMMARY = """
SELECT count(*)                                                       AS departamentos,
       count(vehiculos_por_1000_hab)                                  AS con_datos,
       round(avg(vehiculos_por_1000_hab), 1)                          AS media,
       round(median(vehiculos_por_1000_hab), 1)                       AS mediana,
       round(stddev_samp(vehiculos_por_1000_hab), 1)                  AS desviacion,
       min(vehiculos_por_1000_hab)                                    AS minimo,
       round(quantile_cont(vehiculos_por_1000_hab, 0.25), 1)          AS p25,
       round(quantile_cont(vehiculos_por_1000_hab, 0.75), 1)          AS p75,
       max(vehiculos_por_1000_hab)                                    AS maximo,
       round(1000.0 * sum(vehiculos) / sum(poblacion_2018), 1)        AS nacional_por_1000_hab
FROM motorizacion
"""

# --------------------------------------------------------------------------------------------
# Q3. Distribucion del parque por rangos de antiguedad y tipo de vehiculo (para el grafico).
# --------------------------------------------------------------------------------------------
AGE_DISTRIBUTION = f"""
WITH {WORKSHOP_CLASSES},
{RUNT_CLEAN},
rangos AS (
    SELECT tipo_taller,
           CASE WHEN anio_corte - anio_registro < 5  THEN '0-4'
                WHEN anio_corte - anio_registro < 10 THEN '5-9'
                WHEN anio_corte - anio_registro < 15 THEN '10-14'
                WHEN anio_corte - anio_registro < 20 THEN '15-19'
                ELSE '20+' END                                    AS rango,
           vehiculos
    FROM runt_limpio
)
SELECT tipo_taller, rango, SUM(vehiculos)::BIGINT AS vehiculos,
       round(100.0 * SUM(vehiculos) / SUM(SUM(vehiculos)) OVER (PARTITION BY tipo_taller), 1) AS pct_del_tipo
FROM rangos
GROUP BY tipo_taller, rango
ORDER BY tipo_taller, list_position(['0-4', '5-9', '10-14', '15-19', '20+'], rango)
"""  # constant SQL assembled at import time, no user input  # nosec B608

# Cuantos vehiculos quedaron fuera por el filtro de calidad (se informa en el resumen).
EXCLUDED_BY_QUALITY = f"""
SELECT coalesce(SUM(CAST(vehiculos AS BIGINT)), 0)::BIGINT AS excluidos
FROM runt WHERE CAST(fecha_de_registro AS INTEGER) < {MIN_REGISTRATION_YEAR}
"""  # constant SQL assembled at import time, no user input  # nosec B608
