// Captura WEB con Firefox headless reutilizando el perfil dedicado. Solo navega y
// fotografia: no hace click ni cambia ajustes. Lo que coincida con --hide se tapa
// antes de la foto (avatares, correos, tokens).
//
//   node scripts/evidence/firefox_capture.js --url URL --file 01-x.png --phase 1 \
//        --desc "Descripcion" [--wait "selector"] [--hide "sel1,sel2"] [--full]

const { execFileSync } = require('child_process');
const os = require('os');
const path = require('path');
const { firefox } = require('playwright');

const PROFILE = path.join(os.homedir(), '.mecatrack-firefox-profile');
const ROOT = path.resolve(__dirname, '..', '..');
const IMG = path.join(ROOT, 'docs', 'lab7', 'evidence', 'img');
const PYTHON = path.join(ROOT, 'backend', 'venv', 'bin', 'python');
// El menu de usuario de GitHub y SonarCloud puede mostrar nombre y correo.
const DEFAULT_HIDE = 'img.avatar, .avatar-user, [data-testid="github-avatar"], .js-user-email';

function parseArgs(argv) {
  const args = {};
  for (let i = 0; i < argv.length; i += 1) {
    const key = argv[i].replace(/^--/, '');
    if (key === 'full') args.full = true;
    else { args[key] = argv[i + 1]; i += 1; }
  }
  return args;
}

(async () => {
  const args = parseArgs(process.argv.slice(2));
  const context = await firefox.launchPersistentContext(PROFILE, {
    headless: true,
    viewport: { width: 1440, height: 900 },
  });
  const page = context.pages()[0] || (await context.newPage());
  await page.goto(args.url, { waitUntil: 'load', timeout: 60000 });
  if (args.wait) await page.waitForSelector(args.wait, { timeout: 45000 });
  await page.waitForTimeout(Number(args.settle || 2500));
  const hide = [DEFAULT_HIDE, args.hide].filter(Boolean).join(', ');
  await page.addStyleTag({ content: `${hide} { visibility: hidden !important; }` });

  require('fs').mkdirSync(IMG, { recursive: true });
  await page.screenshot({ path: path.join(IMG, args.file), fullPage: Boolean(args.full) });
  await context.close();

  execFileSync(PYTHON, ['-c',
    'import sys; sys.path.insert(0, "scripts/evidence"); import evidence_index as e; e.register(*sys.argv[1:])',
    args.file, args.phase, args.desc, args.url], { cwd: ROOT });
  console.log(`${args.file}: ${args.url}`);
})().catch((error) => {
  console.error(error.message);
  process.exit(1);
});
