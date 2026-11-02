// Abre Firefox VISIBLE con el perfil dedicado para que el usuario inicie sesion
// a mano en GitHub y SonarCloud (incluido 2FA). Este script nunca escribe ni lee
// credenciales: solo consulta si la sesion ya esta abierta y se cierra entonces.
//
//   node scripts/evidence/firefox_login.js
//
// El perfil (~/.mecatrack-firefox-profile) guarda cookies de sesion: vive fuera
// del repo y nunca debe commitearse.

const os = require('os');
const path = require('path');
const { firefox } = require('playwright');

const PROFILE = path.join(os.homedir(), '.mecatrack-firefox-profile');
const TIMEOUT_MS = 30 * 60 * 1000;
const POLL_MS = 3000;

async function githubLoggedIn(context) {
  const cookies = await context.cookies('https://github.com');
  return cookies.some((c) => c.name === 'logged_in' && c.value === 'yes');
}

async function sonarLoggedIn(context) {
  const response = await context.request.get('https://sonarcloud.io/api/users/current');
  if (!response.ok()) return false;
  return (await response.json()).isLoggedIn === true;
}

(async () => {
  const context = await firefox.launchPersistentContext(PROFILE, {
    headless: false,
    viewport: null,
  });
  let closed = false;
  context.on('close', () => { closed = true; });

  const github = context.pages()[0] || (await context.newPage());
  await github.goto('https://github.com/login');
  const sonar = await context.newPage();
  await sonar.goto('https://sonarcloud.io/login');
  console.log('Firefox abierto: inicia sesion en GitHub y SonarCloud en sus pestanas.');

  const deadline = Date.now() + TIMEOUT_MS;
  let status = { github: false, sonarcloud: false };
  while (!closed && Date.now() < deadline) {
    try {
      status = { github: await githubLoggedIn(context), sonarcloud: await sonarLoggedIn(context) };
    } catch (error) {
      if (closed) break;
    }
    if (status.github && status.sonarcloud) break;
    await new Promise((resolve) => setTimeout(resolve, POLL_MS));
  }

  console.log(`Sesion GitHub: ${status.github} | Sesion SonarCloud: ${status.sonarcloud}`);
  if (!closed) await context.close();
  process.exit(status.github && status.sonarcloud ? 0 : 1);
})();
