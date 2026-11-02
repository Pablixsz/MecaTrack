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
// Solo la cuenta duena del repo puede ver Settings, crear secretos y conectar SonarCloud.
const OWNER = 'pablixsz';

async function githubLogin(context) {
  const response = await context.request.get('https://github.com/');
  const match = (await response.text()).match(/<meta name="user-login" content="([^"]*)"/);
  return match ? match[1] : '';
}

async function sonarLogin(context) {
  const response = await context.request.get('https://sonarcloud.io/api/users/current');
  if (!response.ok()) return '';
  const user = await response.json();
  return user.isLoggedIn ? user.login : '';
}

const isOwner = (login) => login.toLowerCase().startsWith(OWNER);

(async () => {
  const context = await firefox.launchPersistentContext(PROFILE, {
    headless: false,
    viewport: null,
  });
  let closed = false;
  context.on('close', () => { closed = true; });
  // Empieza limpio para no reutilizar una sesion de otra cuenta (solo afecta a este perfil).
  await context.clearCookies();

  const github = context.pages()[0] || (await context.newPage());
  await github.goto('https://github.com/login');
  const sonar = await context.newPage();
  await sonar.goto('https://sonarcloud.io/login');
  console.log('Firefox abierto: inicia sesion en GitHub y SonarCloud en sus pestanas.');

  const deadline = Date.now() + TIMEOUT_MS;
  let status = { github: '', sonarcloud: '' };
  while (!closed && Date.now() < deadline) {
    try {
      status = { github: await githubLogin(context), sonarcloud: await sonarLogin(context) };
    } catch (error) {
      if (closed) break;
    }
    if (isOwner(status.github) && isOwner(status.sonarcloud)) break;
    await new Promise((resolve) => setTimeout(resolve, POLL_MS));
  }

  console.log(`Sesion GitHub: ${status.github || 'ninguna'} | Sesion SonarCloud: ${status.sonarcloud || 'ninguna'}`);
  if (!closed) await context.close();
  process.exit(isOwner(status.github) && isOwner(status.sonarcloud) ? 0 : 1);
})();
