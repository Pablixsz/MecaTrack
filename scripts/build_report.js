// Genera docs/lab7/INFORME_GUIA7_MecaTrack.docx a partir de la evidencia real (index.json,
// imagenes, tablas .md, estadisticas JSON) y de docs/lab7/report-config.json.
//   node scripts/build_report.js
// Re-ejecutable: al cambiar una evidencia o completar el config, se vuelve a correr. Los datos
// sin completar salen como [PENDIENTE: ...]. Los numeros de pagina del indice se calculan
// convirtiendo a PDF con LibreOffice en una primera pasada.

const { execFileSync } = require('child_process');
const { createRequire } = require('module');
const fs = require('fs');
const os = require('os');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const A = require(path.join(ROOT, 'informe', 'apa.js'));
// La misma copia de docx que usa apa.js: con otra, sus objetos se descartan al empaquetar sin dar error.
const { AlignmentType, ImageRun, LeaderType, Packer, Paragraph, TabStopType, TextRun } = createRequire(path.join(ROOT, 'informe', 'apa.js'))('docx');

const { p, plain, center, bullet, link, pageBreak, code, reference } = A;
const LAB = path.join(ROOT, 'docs', 'lab7');
const EVID = path.join(LAB, 'evidence');
const OUT = path.join(LAB, 'INFORME_GUIA7_MecaTrack.docx');
const CFG = JSON.parse(fs.readFileSync(path.join(LAB, 'report-config.json'), 'utf8'));
const INDEX = JSON.parse(fs.readFileSync(path.join(EVID, 'index.json'), 'utf8'));
const readJson = (name) => JSON.parse(fs.readFileSync(path.join(EVID, name), 'utf8'));
const readText = (file) => fs.readFileSync(path.join(ROOT, file), 'utf8');

const INITIAL = readJson('mutmut-stats-initial.json');
const FINAL = readJson('mutmut-stats-final.json');
const SONAR = readJson('sonar-final.json');
const score = (s) => (100 * s.killed / s.total).toFixed(1);
const tests = readText('docs/lab7/evidence/outputs/12a-final-tests-coverage.txt');
const TESTS_PASSED = tests.match(/(\d+) passed/)[1];
const COVERAGE_LOCAL = tests.match(/^TOTAL.*\s(\d+%)$/m)[1];

const pending = (label) => `[[[PENDIENTE: ${label}]]]`;
const TITLE = 'Guía de Laboratorio 7: Calidad, Mutation Testing, JWT y Seguridad de API en MecaTrack';

// Filas de la primera tabla Markdown de un archivo, opcionalmente despues de un titulo.
function mdTable(file, after) {
  let text = readText(file);
  if (after) text = text.slice(text.indexOf(after));
  const lines = text.split('\n');
  const start = lines.findIndex((l) => l.startsWith('|'));
  const rows = [];
  for (let i = start; i < lines.length && lines[i].startsWith('|'); i += 1) {
    if (!lines[i].startsWith('|---')) rows.push(lines[i].replace(/^\| ?| ?\|$/g, '').split(' | ').map((c) => c.trim().replace(/<br>/g, '\n')));
  }
  return rows;
}

// Lineas reales de un archivo entre dos patrones.
function snippet(file, startPattern, endPattern) {
  const lines = readText(file).split('\n');
  const start = lines.findIndex((l) => startPattern.test(l));
  const end = lines.findIndex((l, i) => i > start && endPattern.test(l));
  if (start < 0 || end < 0) throw new Error(`Fragmento no encontrado en ${file}`);
  return lines.slice(start, end + 1).join('\n');
}

function pngSize(file) {
  const buf = fs.readFileSync(file);
  return { buf, w: buf.readUInt32BE(16), h: buf.readUInt32BE(20) };
}

const ACCENTS = { analisis: 'análisis', Analisis: 'Análisis', minimo: 'mínimo', anadir: 'añadir', contrasena: 'contraseña', Verificacion: 'Verificación', Configuracion: 'Configuración', expiracion: 'expiración', gestion: 'gestión', invalido: 'inválido', invalidas: 'inválidas', validas: 'válidas', generico: 'genérico', ejecuciones: 'ejecuciones', codigo: 'código', mutacion: 'mutación', Deteccion: 'Detección' };
const accent = (text) => text.replace(/\b[A-Za-z]+\b/g, (w) => ACCENTS[w] || w);

function buildDocument(pages) {
  const N = A.numbering();
  const { table } = N;
  const headings = [];
  let figureNo = 0;
  const figureNumbers = {};

  const h1 = (t) => { headings.push({ t, level: 1 }); return A.h1(t); };
  const h2 = (t) => { headings.push({ t, level: 2 }); return A.h2(t); };

  // Pie de figura bajo la imagen: "Figura N. descripcion", tomada de index.json.
  function figure(file, caption, maxHeightPx = 400) {
    const entry = INDEX.find((e) => e.file === file);
    if (!entry) throw new Error(`Sin registro en index.json: ${file}`);
    const { buf, w, h } = pngSize(path.join(EVID, 'img', file));
    const scale = Math.min(624 / w, maxHeightPx / h);
    figureNo += 1;
    figureNumbers[file] = figureNo;
    const text = caption || accent(entry.description);
    return [
      new Paragraph({ alignment: AlignmentType.CENTER, keepNext: true, spacing: { before: 160 },
        children: [new ImageRun({ type: 'png', data: buf, transformation: { width: Math.round(w * scale), height: Math.round(h * scale) }, altText: { title: text, description: text, name: file } })] }),
      new Paragraph({ alignment: AlignmentType.LEFT, spacing: { before: 60, after: 200 },
        children: [new TextRun({ text: `Figura ${figureNo}. `, bold: true, size: 20 }), new TextRun({ text, italics: true, size: 20 })] }),
    ];
  }
  const f = (file) => (buildDocument.figures && buildDocument.figures[file]) || '?';
  const fig = (file) => `Figura ${f(file)}`;

  const body = [];
  const add = (...items) => items.flat().forEach((i) => body.push(i));

  // ---------------- Introduccion
  add(
    h1('Introducción'),
    p('MecaTrack es el sistema de citas y seguimiento de vehículos de un taller mecánico (Flask, SQLAlchemy y PostgreSQL, con frontend en HTML, CSS y JavaScript sin frameworks). Esta guía endurece su calidad y seguridad: análisis estático con SonarCloud, mutation testing dentro del CI, autenticación con JWT y control de acceso por roles, controles de OWASP API Security Top 10 2023, y análisis con CodeQL y Dependabot.'),
    p(`Todas las cifras y capturas de este informe provienen de ejecuciones reales registradas en \`docs/lab7/evidence/index.json\`. El repositorio de trabajo cambió a \`Pablixsz/MecaTrack\` porque la cuenta que administra el proyecto no era dueña del repositorio anterior y no podía configurar secretos ni ajustes de seguridad; la historia de commits se conservó completa.`),
  );

  // ---------------- Resultados: sesion 13 en espanol
  add(
    h1('Resultados por entregable'),
    h2('SonarCloud y Quality Gate'),
    p(`El primer análisis encontró ${SONAR.before.bugs} bugs y ${SONAR.before.vulnerabilities} vulnerabilidades (${fig('01a-sonar-before-overview.png')} y ${fig('01b-sonar-before-critical.png')}). Al cierre, el Quality Gate está aprobado, sin issues abiertos de tipo Bug o Vulnerability y con ${SONAR.measures.coverage} % de cobertura global (${fig('12c-final-sonar-overview.png')} y ${fig('12d-final-sonar-new-code.png')}).`),
    p('Ese resultado debe leerse con su alcance: tres issues se cerraron como falso positivo y dos como aceptados, con justificación escrita en SonarCloud; las herramientas de `scripts/` e `informe/` quedaron fuera del análisis; y siguen abiertos 2 code smells de accesibilidad. Además, el análisis detectó 4 CVE en dependencias directas, que se resolvieron actualizando los paquetes (' + fig('12g-final-sonar-dependency-risks.png') + ').'),
    table('Issues de SonarCloud: causa, tratamiento y verificación', ['Issue', 'Severidad', 'Causa', 'Tratamiento', 'Test / verificación'], mdTable('docs/lab7/evidence/sonar-issues.md').slice(1), [2000, 900, 2100, 2460, 1900], { size: 15 }),
    ...figure('01a-sonar-before-overview.png', 'SonarCloud antes de las correcciones: resumen del primer análisis.'),
    ...figure('01b-sonar-before-critical.png', 'SonarCloud antes de las correcciones: issues de seguridad con severidad alta.'),
    ...figure('12d-final-sonar-new-code.png', 'SonarCloud final: Quality Gate aprobado sobre el código nuevo.'),
    ...figure('12c-final-sonar-overview.png', 'SonarCloud final: Quality Gate aprobado y cobertura global.'),
    ...figure('12g-final-sonar-dependency-risks.png', 'SonarCloud final: 0 riesgos de dependencias tras actualizar 4 paquetes.'),
    ...figure('12a-final-tests-coverage.png', 'Verificación final: pruebas y cobertura local.', 520),

    h2('Mutation testing'),
    p(`Se configuró mutmut 3.8.1 sobre la lógica de negocio: disponibilidad de bahía y mecánico, pagos de depósito y saldo, y sus validaciones. El score pasó de ${score(INITIAL)} % a ${score(FINAL)} % (${fig('03a-mutmut-initial.png')} y ${fig('12b-final-mutation-score.png')}). El punto de partida ya superaba el 60 % exigido, pero los mutantes sobrevivientes mostraban huecos reales: \`get\` no tenía ninguna prueba y varias pruebas no verificaban los argumentos que llegaban a los puertos.`),
    p('El score mide solo ese alcance, no todo el backend. Quedan 5 sobrevivientes: dos equivalentes (quitan un valor que ya es el predeterminado) y tres que solo alteran textos de mensajes (detalle en `docs/lab7/evidence/mutants.md`).'),
    table('Score de mutación inicial y final', ['Momento', 'Killed', 'Survived', 'Sin pruebas', 'Total', 'Score'], [
      ['Inicial', INITIAL.killed, INITIAL.survived, INITIAL.no_tests, INITIAL.total, `${score(INITIAL)} %`],
      ['Final', FINAL.killed, FINAL.survived, FINAL.no_tests, FINAL.total, `${score(FINAL)} %`],
    ], [2360, 1400, 1400, 1400, 1400, 1400]),
    table('Mutantes por función (sobrevivientes / sin pruebas)', ['Módulo', 'Función', 'Antes', 'Después', 'Pruebas añadidas'], mdTable('docs/lab7/evidence/mutants.md', '## Mutantes por funcion').slice(1), [2500, 1500, 700, 800, 3860], { size: 14 }),
    ...figure('03a-mutmut-initial.png', 'Mutation testing: score inicial.'),
    ...figure('12b-final-mutation-score.png', 'Mutation testing: score final.'),
    ...figure('03b-mutmut-results.png', 'mutmut: sobrevivientes al cierre de la fase de pruebas.'),

    h2('CI/CD con mutation testing'),
    p(`El workflow tiene un job \`mutation\` que ejecuta mutmut y \`scripts/mutation_score.py\`, que sale con código 1 si el score es menor a 50 %. Para demostrarlo se usó una rama temporal sin las pruebas de los servicios, sin tocar el umbral: el score cayó a 6,5 % y el build falló en ese paso (${fig('04a-ci-fail-run.png')} y ${fig('04b-ci-fail-under-50.png')}). La rama se borró después. La ${fig('05a-ci-green.png')} muestra el estado normal y la ${fig('12f-final-readme-badges.png')} los badges del README. El badge de mutation score es estático: refleja el último valor medido y se actualiza a mano.`),
    ...figure('04a-ci-fail-run.png', 'GitHub Actions: el job de mutation testing falla en la rama temporal.'),
    ...figure('04b-ci-fail-under-50.png', 'GitHub Actions: el paso del score falla con 6,5 %, por debajo del mínimo de 50 %.'),
    ...figure('05a-ci-green.png', 'GitHub Actions: pruebas y mutation testing en verde.'),
    ...figure('12f-final-readme-badges.png', 'README con los badges de CI, Quality Gate y mutation score.'),
  );

  // ---------------- Sesion 14 en ingles
  add(
    h2('JWT and RBAC (session 14)'),
    plain('*This section is in English, as required for session 14.*'),
    p(`Flask-Login session cookies were replaced with Flask-JWT-Extended. \`POST /api/auth/login\` returns a 15-minute access token with the role as a claim, and \`JWT_SECRET_KEY\` only comes from the environment: the application refuses to start without it. Every route declares its roles through \`@role_required\`; a missing or invalid token gets 401 and a wrong role gets 403 (Figures ${f('06a-jwt-login-200.png')} to ${f('07f-jwt-management-403.png')}).`),
    p('Two guarantees that a purely stateless JWT would lose were kept: logout revokes the token, and each request loads the user from the database, so a deactivated account or a changed role loses access immediately. As a limitation, the revocation list lives in the memory of one server process.'),
    p(`The frontend keeps the token in \`sessionStorage\` and sends it in the \`Authorization\` header (${fig('08a-frontend-login-admin.png')}). On 401 or 403 it clears the session and returns to the login page (${fig('08b-frontend-401-redirect.png')} and ${fig('08c-frontend-403-redirect.png')}). Compared with an HttpOnly cookie, this removes the CSRF risk because no ambient credential exists, but any script on the page could read the token. That risk is mitigated by escaping rendered data and using short-lived tokens. \`sessionStorage\` was preferred over \`localStorage\` because it is cleared when the tab closes.`),
    ...code(snippet('backend/api/auth.py', /^def role_required/, /^    return decorator/)),
    ...code(snippet('backend/api/jwt_routes.py', /^@jwt_auth_bp\.route\('\/login'/, /^    \}\), 200/)),
    ...figure('06a-jwt-login-200.png', 'POST /api/auth/login with valid credentials: 200 and a token.', 300),
    ...figure('06b-jwt-login-401.png', 'POST /api/auth/login with a wrong password: generic 401.', 220),
    ...figure('06c-jwt-claims.png', 'Token claims: role and short expiry.', 320),
    ...figure('07a-jwt-admin-200.png', 'ADMIN endpoint with an admin token: 200.', 220),
    ...figure('07b-jwt-admin-403.png', 'ADMIN endpoint with a client token: 403.', 220),
    ...figure('07c-jwt-user-200.png', 'USER endpoint with a client token: 200.', 220),
    ...figure('07d-jwt-401-no-token.png', 'Protected endpoint without a token: 401.', 220),
    ...figure('07e-jwt-expired.png', 'Expired token (issued with a 2-second lifetime): 401 token_expired.', 220),
    ...figure('07f-jwt-management-403.png', 'Real management endpoint (POST /bays) with a client token: 403.', 220),
    ...figure('08a-frontend-login-admin.png', 'Frontend: admin login; requests carry Authorization: Bearer.', 340),
    ...figure('08b-frontend-401-redirect.png', 'Frontend: an invalid token (401) clears the session and returns to login.', 340),
    ...figure('08c-frontend-403-redirect.png', 'Frontend: a client gets 403 on /bays and returns to login.', 340),

    h2('OWASP API Security Top 10 2023 (session 14)'),
    p(`Controls and automated tests cover 9 of the 10 risks. API7 (SSRF) is not covered because no endpoint accepts a URL from the user. Some controls already existed and were verified with new tests, such as object-level authorization; others are new, such as rate limiting, security headers and the active appointment limit. File and line references are generated from the current code. Figures ${f('09b-owasp-tests.png')} to ${f('09d-owasp-headers.png')} show the tests and real responses.`),
    table('OWASP API Security Top 10 2023: implemented controls', ['Risk', 'Control implemented', 'File/line', 'Test/evidence'], mdTable('docs/lab7/owasp-controls.md').slice(1), [1700, 3000, 2460, 2200], { size: 14 }),
    plain('**Known limitations.** The token blocklist and rate-limit counters live in one process and reset on restart. The login limit is per IP address, so it does not stop a distributed attack on one account. Pagination cuts the response, not the database query.'),
    ...code(snippet('backend/api/__init__.py', /def security_headers/, /^        return response/)),
    ...code(snippet('backend/application/scheduling/services.py', /def _deposit_is_paid/, /return any\(/)),
    ...figure('09b-owasp-tests.png', 'OWASP: automated tests for each control.', 480),
    ...figure('09c-owasp-rate-limit.png', 'OWASP API2/API4: the sixth login attempt in a minute gets 429.', 240),
    ...figure('09d-owasp-headers.png', 'OWASP API8: security headers on a real response.', 340),

    h2('CodeQL and Dependabot (session 14)'),
    p(`CodeQL runs on every push to `mecatrack-final` for Python and JavaScript and reports 0 alerts (${fig('10a-codeql-0-alerts.png')}). Because zero alerts could also mean that nothing was analyzed, the tool status page was checked: 120 Python, 11 JavaScript and 7 HTML files were scanned (${fig('10b-codeql-files-scanned.png')}). A manual review of the 49 \`innerHTML\` uses found no real XSS: user text goes through \`esc()\`, and the rest are numeric ids or constants. \`debug=True\` was removed, and the only SQL built with an f-string inserts a constant query.`),
    p(`Dependency graph, Dependabot alerts and security updates were enabled in the repository settings (${fig('11a-security-settings.png')}). Dependabot opened 9 real pull requests without pinning any dependency to an old version on purpose (${fig('11c-dependabot-pr.png')}). Three of them closed by themselves when the same packages were updated to fix CVEs, and 6 remain open (${fig('11b-dependabot-prs.png')}). They were not merged because they need review; for example, duckdb 2.0.0 is a major version.`),
    ...figure('10a-codeql-0-alerts.png', 'Security > Code scanning: 0 open CodeQL alerts.', 340),
    ...figure('10b-codeql-files-scanned.png', 'CodeQL: files scanned per language.', 340),
    ...figure('10c-codeql-run.png', 'GitHub Actions: CodeQL analysis for Python and JavaScript.', 340),
    ...figure('11a-security-settings.png', 'Settings > Advanced Security: Dependency graph and Dependabot enabled.', 380),
    ...figure('11b-dependabot-prs.png', 'Pull requests opened by Dependabot that remain open.', 340),
    ...figure('11c-dependabot-pr.png', 'Detail of a Dependabot update pull request.', 340),
    ...figure('11d-dependabot-yml.png', 'dependabot.yml in the repository.', 340),
  );

  // ---------------- Preguntas orientadoras
  add(
    h1('Preguntas orientadoras'),
    h2('Aprendizajes para el quehacer profesional'),
    bullet('**Un indicador en verde no basta; hay que saber qué mide.** "0 alertas" de CodeQL pudo significar que no analizó nada, y se confirmó con 138 archivos escaneados. El API de SonarCloud decía "0 bugs" mientras el panel mostraba 20 issues de fiabilidad y 4 CVE que no aparecían en esa consulta. El "100 %" del Quality Gate inicial evaluaba solo 5 líneas.'),
    bullet(`**La cobertura no mide la calidad de las pruebas.** Con 98 % de cobertura, el score inicial de mutación fue ${score(INITIAL)} %: había líneas ejecutadas cuyo resultado nadie comprobaba.`),
    bullet('**Una suite de pruebas protege las migraciones grandes.** Al pasar a JWT, una prueba existente detectó que se habían perdido los `details` del 403, y otra detectó que Flask-Limiter sobrescribía el `Retry-After` de la cuota de IA.'),
    bullet('**Seguridad por diseño antes que parches.** El riesgo de CSRF no se resolvió con un token adicional, sino eliminando la cookie de sesión, lo que quita la causa.'),
    h2('Dificultades reales y cómo se resolvieron'),
    table('Dificultades encontradas', ['Dificultad', 'Cómo se detectó', 'Resolución'], [
      ['La cuenta `Pablixsz` no era dueña del repositorio y no podía crear secretos ni cambiar ajustes', 'La página de Settings respondía 404 con esa sesión', 'Se creó `Pablixsz/MecaTrack` con la historia completa y una deploy key limitada a ese repositorio'],
      ['`SONAR_TOKEN` no quedó guardado en el primer intento', 'La lista de secretos del repositorio seguía vacía', 'Se repitió el registro y se verificó la lista antes de continuar'],
      ['Workflow inválido por `:all:` sin comillas en YAML', 'La ejecución no tenía nombre ni jobs (run 41379928502)', 'Comillas y validación local del YAML antes de cada push'],
      ['`.catch` sobre una función síncrona rompía 3 pantallas con `TypeError`', 'El reanálisis de SonarCloud (S3699)', 'Se revisaron las 26 llamadas y se corrigieron las 3'],
      ['La primera demostración de score < 50 % falló en `mutmut run`, no en el paso del score', 'Se leyó qué paso había fallado (run 41382364443)', 'Se descartó y se repitió conservando parte de las pruebas (run 41382792374)'],
      ['`test_architecture` fallaba bajo mutmut porque lee el código instrumentado', 'Salida de la primera ejecución de mutmut', 'Se excluyó solo de esa corrida; sigue corriendo en el CI normal'],
      ['Regresión en `Retry-After` que parecía una prueba inestable', 'Se repitió la prueba con y sin el cambio', 'Se corrigió el código y no la prueba'],
    ], [3500, 2860, 3000], { size: 18 }),
    h2('Resumen de entregables'),
    table('Entregables, métricas y evidencia', ['Entregable', 'Métrica', 'Figuras'], [
      ['SonarCloud', `Quality Gate ${SONAR.quality_gate === 'OK' ? 'aprobado' : SONAR.quality_gate}; bugs ${SONAR.before.bugs} a ${SONAR.measures.bugs}; vulnerabilidades ${SONAR.before.vulnerabilities} a ${SONAR.measures.vulnerabilities}; cobertura ${SONAR.measures.coverage} %`, `${f('01a-sonar-before-overview.png')}, ${f('12d-final-sonar-new-code.png')}, ${f('12c-final-sonar-overview.png')}, ${f('12g-final-sonar-dependency-risks.png')}`],
      ['Pruebas', `${TESTS_PASSED} pruebas pasan; cobertura local ${COVERAGE_LOCAL}`, `${f('12a-final-tests-coverage.png')}`],
      ['Mutation testing', `${score(INITIAL)} % a ${score(FINAL)} % (${FINAL.killed} de ${FINAL.total})`, `${f('03a-mutmut-initial.png')}, ${f('12b-final-mutation-score.png')}`],
      ['CI/CD', 'El build falla con score de 6,5 %; job y badges activos', `${f('04b-ci-fail-under-50.png')}, ${f('05a-ci-green.png')}, ${f('12f-final-readme-badges.png')}`],
      ['JWT + RBAC', 'Login, 200, 401, 403 y token vencido demostrados; 2 roles o más', `${f('06a-jwt-login-200.png')} a ${f('08c-frontend-403-redirect.png')}`],
      ['OWASP', '9 de 10 riesgos con control y prueba (mínimo pedido: 7)', `${f('09b-owasp-tests.png')} a ${f('09d-owasp-headers.png')}`],
      ['CodeQL', '0 alertas; 138 archivos escaneados', `${f('10a-codeql-0-alerts.png')}, ${f('10b-codeql-files-scanned.png')}`],
      ['Dependabot', '9 PR abiertos por Dependabot; 6 siguen abiertos', `${f('11b-dependabot-prs.png')}, ${f('11c-dependabot-pr.png')}`],
    ], [2000, 5000, 2360]),
    h2('Uso de la inteligencia artificial'),
    p('Se usó Claude Code (Claude Opus 5.5) para el análisis, el código, las pruebas, la captura de evidencias y este informe, bajo los requisitos, las decisiones y la revisión del equipo. GitHub Copilot no se usó en esta guía. El registro completo está en `docs/lab7/ai-log.md`.'),
    table('Qué generó la IA y qué se revisó o corrigió', ['Fase', 'Qué generó', 'Revisión o corrección'], mdTable('docs/lab7/ai-log.md').slice(1), [700, 3200, 5460], { size: 16 }),
    p('Las sugerencias incorrectas se detectaron con herramientas independientes de quien las escribió: el reanálisis de SonarCloud, la suite de pruebas y la lectura de qué paso del CI había fallado. Por eso ningún arreglo se dio por bueno solo porque una advertencia desapareciera.'),
  );

  // ---------------- Enlaces y referencias
  add(
    h1('Repositorio y pipeline'),
    link('Repositorio', CFG.repoUrl),
    link('Pipeline', CFG.pipelineUrl),
    ...figure('12e-final-actions.png', 'GitHub Actions: pipeline en verde en la rama mecatrack-final.', 460),
    h1('Video'),
    CFG.videoUrl ? link('Video (YouTube)', CFG.videoUrl) : plain(pending('enlace del video')),
    h1('Referencias'),
    reference('Gilbert, L. A. (s. f.). *Flask-JWT-Extended documentation*. https://flask-jwt-extended.readthedocs.io/'),
    reference('GitHub. (s. f.-a). *About code scanning with CodeQL*. GitHub Docs. https://docs.github.com/en/code-security/code-scanning/introduction-to-code-scanning/about-code-scanning-with-codeql'),
    reference('GitHub. (s. f.-b). *Dependabot*. GitHub Docs. https://docs.github.com/en/code-security/dependabot'),
    reference('Hovmöller, A. (s. f.). *mutmut: Python mutation tester*. https://mutmut.readthedocs.io/'),
    reference('OWASP Foundation. (2023). *OWASP API Security Top 10 2023*. https://owasp.org/API-Security/editions/2023/en/0x11-t10/'),
    reference('Sonar. (s. f.). *SonarQube Cloud documentation*. https://docs.sonarsource.com/sonarqube-cloud/'),
  );

  // ---------------- Portada e indice (van primero; dependen de los titulos)
  const author = (a) => center(`${a.name} — Código ${a.code || pending('código')}`);
  const cover = [
    ...Array.from({ length: 3 }, () => new Paragraph({ spacing: { line: A.DOUBLE }, children: [] })),
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { line: A.DOUBLE, after: 480 }, children: [new TextRun({ text: TITLE, bold: true })] }),
    ...CFG.authors.map(author),
    center('Facultad de Ingeniería, Universidad Manuela Beltrán (UMB)'),
    center(`${CFG.course} — ${CFG.session}`),
    center(`Docente: ${CFG.teacher || pending('nombre del docente')}`),
    center(CFG.date),
    pageBreak(),
  ];
  const toc = [
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 240 }, children: [new TextRun({ text: 'Tabla de contenido', bold: true })] }),
    ...headings.map(({ t, level }) => new Paragraph({
      indent: { left: level === 2 ? 360 : 0 },
      spacing: { line: 300 },
      tabStops: [{ type: TabStopType.RIGHT, position: A.CONTENT_W, leader: LeaderType.DOT }],
      children: [new TextRun({ text: `${t}\t${pages[t] || ''}` })],
    })),
    pageBreak(),
  ];

  buildDocument.figures = figureNumbers;
  return { children: [...cover, ...toc, ...body], headings, counts: { figures: figureNo, tables: N.counts().tables } };
}

async function write(pages) {
  const { children, headings, counts } = buildDocument(pages);
  const doc = A.apaDocument({ title: 'Informe Guía 7 MecaTrack', description: TITLE, children });
  fs.writeFileSync(OUT, await Packer.toBuffer(doc));
  return { headings, counts };
}

// Busca en que pagina del PDF aparece cada titulo como linea propia, despues del indice.
function headingPages(headings) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'mecatrack-report-'));
  execFileSync('soffice', ['--headless', '--convert-to', 'pdf', '--outdir', dir, OUT], { stdio: 'ignore' });
  const pdf = path.join(dir, path.basename(OUT).replace('.docx', '.pdf'));
  const text = execFileSync('pdftotext', ['-layout', pdf, '-'], { maxBuffer: 1 << 28 }).toString().split('\f');
  const tocPage = text.findIndex((t) => t.includes('Tabla de contenido'));
  const pages = {};
  let from = tocPage + 1;
  for (const { t } of headings) {
    for (let i = from; i < text.length; i += 1) {
      if (text[i].split('\n').some((line) => line.trim() === t)) { pages[t] = i + 1; from = i; break; }
    }
    if (!pages[t]) throw new Error(`Titulo sin pagina: ${t}`);
  }
  fs.rmSync(dir, { recursive: true });
  return pages;
}

(async () => {
  buildDocument({}); // primera pasada: numeros de figuras
  const { headings } = await write({});
  const { counts } = await write(headingPages(headings));
  console.log(`Informe: ${path.relative(ROOT, OUT)} (${counts.figures} figuras, ${counts.tables} tablas, ${(fs.statSync(OUT).size / 1024 / 1024).toFixed(1)} MB)`);
})().catch((error) => { console.error(error.message); process.exit(1); });
