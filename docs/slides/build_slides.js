// Builds docs/slides/MecaTrack_Lab8_Demo.pptx - 3 slides for the Lab 8 group demo.
//   cd docs/slides && npm install && npm run build
// Numbers come from docs/docker/size-comparison.md, docs/quality-report.md and scripts/demo_jwt.sh.

const path = require('path');
const pptxgen = require('pptxgenjs');

const COLORS = {
  ink: '1F2933',      // charcoal: titles, body
  muted: '5B6770',    // captions
  accent: 'E8731A',   // workshop orange: numbers, step circles
  card: 'F1F3F5',     // card tint
  line: 'C9CED4',
  white: 'FFFFFF',
  ok: '2E7D4F',
};
const HEAD = 'Cambria';
const BODY = 'Calibri';
const ROOT = path.join(__dirname, '..', '..');

const pres = new pptxgen();
pres.layout = 'LAYOUT_16x9'; // 10 x 5.625 in
pres.author = 'MecaTrack team';
pres.title = 'MecaTrack - Cloud-native deployment (Lab 8)';
pres.theme = { headFontFace: HEAD, bodyFontFace: BODY };

pres.defineSlideMaster({
  title: 'CONTENT',
  background: { color: COLORS.white },
  objects: [
    { placeholder: { options: { name: 'title', type: 'title', x: 0.5, y: 0.3, w: 9, h: 0.7, fontFace: HEAD,
      fontSize: 30, bold: true, color: COLORS.ink, align: 'left', valign: 'middle', margin: 0 }, text: 'Title' } },
    { placeholder: { options: { name: 'kicker', type: 'body', x: 0.5, y: 0.95, w: 9, h: 0.3, fontFace: BODY,
      fontSize: 12, color: COLORS.muted, margin: 0 }, text: 'Subtitle' } },
    { text: { text: 'MecaTrack · Lab 8 · Cloud-native deployment', options: { x: 0.5, y: 5.2, w: 6, h: 0.25,
      fontFace: BODY, fontSize: 10, color: COLORS.muted, margin: 0 } } },
  ],
  slideNumber: { x: 9.0, y: 5.2, w: 0.5, h: 0.25, fontFace: BODY, fontSize: 10, color: COLORS.muted, align: 'right' },
});

function card(slide, x, y, w, h, name) {
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.08, fill: { color: COLORS.card },
    line: { color: COLORS.card }, objectName: name });
}

function stat(slide, x, y, w, h, value, label, name) {
  card(slide, x, y, w, h, `${name} card`);
  slide.addText(value, { x: x + 0.2, y: y + 0.08, w: w - 0.4, h: h * 0.55, fontFace: HEAD, fontSize: 26, bold: true,
    color: COLORS.accent, valign: 'bottom', margin: 0, isTextBox: true, objectName: `${name} value` });
  slide.addText(label, { x: x + 0.2, y: y + h * 0.6, w: w - 0.4, h: h * 0.35, fontFace: BODY, fontSize: 12,
    color: COLORS.ink, valign: 'top', margin: 0, isTextBox: true, objectName: `${name} label` });
}

// ---------------------------------------------------------------- Slide 1: architecture
pres.addSection({ title: 'Architecture' });
const s1 = pres.addSlide({ masterName: 'CONTENT', sectionTitle: 'Architecture' });
s1.addText('One container, one public URL', { placeholder: 'title' });
s1.addText('Flask API and vanilla frontend in a non-root container, PostgreSQL managed by Render',
  { placeholder: 'kicker' });
s1.addImage({ path: path.join(ROOT, 'docs', 'architecture.png'), x: 0.5, y: 1.35, w: 9, h: 2.5,
  altText: 'Architecture: GitHub Actions builds, tests and pushes the image to Docker Hub; Render pulls it and runs '
    + 'gunicorn + Flask next to a managed PostgreSQL; the browser reaches it over HTTPS.' });
stat(s1, 0.5, 4.05, 2.85, 1.0, '436 MB', 'image, vs 2.27 GB naive (−81 %)', 'Image size');
stat(s1, 3.575, 4.05, 2.85, 1.0, 'uid 10001', 'non-root user, code is read-only', 'Non-root');
stat(s1, 6.65, 4.05, 2.85, 1.0, '/health', 'checks PostgreSQL: 200 or 503', 'Health');
s1.addNotes('One container serves the API and the frontend, so there is a single URL and no CORS. '
  + 'The image is multi-stage on python:3.12-slim: 436 MB instead of 2.27 GB for a naive build. '
  + 'It runs as an unprivileged user that cannot modify its own code. /health runs SELECT 1, so Docker, compose and '
  + 'Render stop sending traffic when the database is down. On start the entrypoint applies migrations; demo data '
  + 'is never loaded automatically.');

// ---------------------------------------------------------------- Slide 2: pipeline
pres.addSection({ title: 'CI/CD' });
const s2 = pres.addSlide({ masterName: 'CONTENT', sectionTitle: 'CI/CD' });
s2.addText('Every push to main ships itself', { placeholder: 'title' });
s2.addText('GitHub Actions: four chained jobs; pull requests stop after the build',
  { placeholder: 'kicker' });

const steps = [
  ['Test', 'ruff, pytest with a 90\u00a0% coverage gate, bandit, pip\u2011audit'],
  ['Build', 'multi-stage image, smoke test: healthy and not root'],
  ['Push', 'Docker Hub tags latest and sha-<short>'],
  ['Deploy', 'Render hook pinned to the sha image, waits for /health'],
];
const stepW = 2.025;
const gap = 0.3;
steps.forEach(([name, text], i) => {
  const x = 0.5 + i * (stepW + gap);
  card(s2, x, 1.45, stepW, 1.55, `Step ${i + 1}`);
  s2.addShape(pres.shapes.OVAL, { x: x + 0.2, y: 1.6, w: 0.45, h: 0.45, fill: { color: COLORS.accent },
    line: { color: COLORS.accent }, objectName: `Step ${i + 1} circle` });
  s2.addText(String(i + 1), { x: x + 0.2, y: 1.6, w: 0.45, h: 0.45, fontFace: HEAD, fontSize: 16, bold: true,
    color: COLORS.white, align: 'center', valign: 'middle', margin: 0, isTextBox: true });
  s2.addText(name, { x: x + 0.75, y: 1.6, w: stepW - 0.85, h: 0.45, fontFace: HEAD, fontSize: 18, bold: true,
    color: COLORS.ink, valign: 'middle', margin: 0, isTextBox: true });
  s2.addText(text, { x: x + 0.2, y: 2.15, w: stepW - 0.4, h: 0.8, fontFace: BODY, fontSize: 12,
    color: COLORS.ink, valign: 'top', margin: 0, isTextBox: true });
  if (i < steps.length - 1) {
    s2.addShape(pres.shapes.RIGHT_ARROW, { x: x + stepW + 0.05, y: 2.1, w: 0.2, h: 0.25,
      fill: { color: COLORS.line }, line: { color: COLORS.line }, objectName: `Arrow ${i + 1}` });
  }
});

// Frame for the real screenshot, taken after the first merge to main.
s2.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.5, y: 3.25, w: 5.2, h: 1.8, rectRadius: 0.08,
  fill: { color: COLORS.white }, line: { color: COLORS.line, width: 1.25, dashType: 'dash' },
  objectName: 'Screenshot frame' });
s2.addText('Paste here: screenshot of the green CI/CD run (Actions tab, 4 jobs)',
  { x: 0.8, y: 3.25, w: 4.6, h: 1.8, fontFace: BODY, fontSize: 12, italic: true, color: COLORS.muted,
    align: 'center', valign: 'middle', margin: 0, isTextBox: true, objectName: 'Screenshot hint' });

s2.addChart(pres.charts.BAR, [{ name: 'Image size (MB)', labels: ['Optimized', 'Naive'], values: [436, 2265] }], {
  x: 5.95, y: 3.25, w: 3.55, h: 1.8, barDir: 'bar', chartColors: [COLORS.accent, COLORS.line],
  showTitle: true, title: 'Image size on disk (MB)', titleFontSize: 12, titleColor: COLORS.ink, titleFontFace: BODY,
  showValue: true, dataLabelPosition: 'outEnd', dataLabelFontSize: 11, dataLabelColor: COLORS.ink,
  dataLabelFontFace: BODY, dataLabelFormatCode: '0', catAxisLabelColor: COLORS.ink, catAxisLabelFontSize: 11,
  catAxisLabelFontFace: BODY, valAxisHidden: true, valGridLine: { style: 'none' }, catGridLine: { style: 'none' },
  showLegend: false, valAxisMaxVal: 2900,
});
s2.addNotes('Stage 1 blocks bad code: lint, 257 tests on a real PostgreSQL with a 90 % coverage gate, bandit for '
  + 'the code and pip-audit for dependencies. Stage 2 builds the image and starts it next to a database: it must be '
  + 'healthy, report this commit as its version and not run as root. Stages 3 and 4 only run on main: push to Docker '
  + 'Hub, then call the Render deploy hook with the sha tag, so Render deploys exactly this image, and wait until '
  + 'the public /health reports the new commit.');

// ---------------------------------------------------------------- Slide 3: metrics + JWT
pres.addSection({ title: 'Quality and security' });
const s3 = pres.addSlide({ masterName: 'CONTENT', sectionTitle: 'Quality and security' });
s3.addText('Quality gates and JWT, measured', { placeholder: 'title' });
s3.addText('Live from scripts/quality_report.sh and scripts/demo_jwt.sh', { placeholder: 'kicker' });

const sw = 2.05;
const sh = 1.6;
stat(s3, 0.5, 1.45, sw, sh, '257 / 257', 'tests passing', 'Tests');
stat(s3, 0.5 + sw + 0.3, 1.45, sw, sh, '97.4 %', 'line coverage, gate 90\u00a0%', 'Coverage');
stat(s3, 0.5, 1.45 + sh + 0.3, sw, sh, '0', 'bandit high or medium', 'Bandit');
stat(s3, 0.5 + sw + 0.3, 1.45 + sh + 0.3, sw, sh, '0', 'vulnerable packages', 'pip-audit');

const hdr = { bold: true, color: COLORS.white, fill: { color: COLORS.ink }, fontFace: BODY, fontSize: 12 };
const cell = { color: COLORS.ink, fontFace: BODY, fontSize: 12 };
const code = (c) => ({ text: c, options: { ...cell, bold: true, align: 'center',
  color: c === '200' ? COLORS.ok : COLORS.accent } });
const rows = [
  [{ text: 'JWT case', options: hdr }, { text: 'HTTP', options: { ...hdr, align: 'center' } }],
  ...[['Valid client token', '200'], ['Client on admin route', '403'], ['No token', '401'],
    ['Role claim tampered', '401'], ['Expired token', '401'], ['Reused after logout', '401']]
    .map(([c, s]) => [{ text: c, options: cell }, code(s)]),
];
s3.addTable(rows, { x: 5.2, y: 1.45, w: 4.3, colW: [3.3, 1.0], rowH: 0.47, border: { type: 'solid', pt: 0.75,
  color: COLORS.line }, fill: { color: COLORS.white }, valign: 'middle', objectName: 'JWT demo results' });
s3.addNotes('All numbers are produced by scripts, not typed by hand: quality_report.sh runs the same gates as the '
  + 'pipeline. For JWT we run demo_jwt.sh live: a valid token gets 200, a client on an admin route 403, and five '
  + 'ways of cheating get 401 - no token, a tampered role claim (the signature no longer matches), garbage, an '
  + 'expired token signed with the real key, and a token reused after logout, revoked by its jti.');

pres.writeFile({ fileName: path.join(__dirname, 'MecaTrack_Lab8_Demo.pptx') })
  .then((file) => console.log(`Written ${file}`));
