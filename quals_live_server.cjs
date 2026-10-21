// Replicata: run `node quals_live_server.cjs`; reproduce Live Server's file watcher
// in a temporary workspace, then write the search's live outputs and edit index.html.
// Expectata: current workspace settings suppress output-triggered reloads while an
// index edit still triggers one. Removing the job-directory exclusion reproduces
// the old failure specifically for .lattice288_work/job.json.
// Resultata (2026-10-20): the active server sent 13 reloads in 45 seconds. Native
// macOS file events for .lattice288_work/job.json escaped the dotdirectory filter.
// Run outside the workspace sandbox: native file events are unavailable inside it.
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');

const delay = ms => new Promise(resolve => setTimeout(resolve, ms));

(async () => {
  const extensions = path.join(os.homedir(), '.vscode/extensions');
  const installed = (await fs.readdir(extensions)).filter(n => n.startsWith('ritwickdey.liveserver-'));
  assert.equal(installed.length, 1, installed.join(', '));
  const extension = path.join(extensions, installed[0]);
  const chokidar = require(path.join(extension, 'node_modules/chokidar'));
  const settings = JSON.parse(await fs.readFile(path.join(__dirname, '.vscode/settings.json')))
    ['liveServer.settings.ignoreFiles'];
  const previous = settings.filter(p => p !== '.lattice288_work/**');
  const outputs = ['lattice288.log', 'lattice288_journal.jsonl',
    '.lattice288_prepared.json', '.lattice288_work/job.json',
    '.lattice288_work/progress.log', 'progress.js', '.progress_cache.json'];
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'powersums-live-server-'));
  try {
    await fs.mkdir(path.join(root, '.lattice288_work'));
    for (const name of [...outputs, 'index.html']) await fs.writeFile(path.join(root, name), '0');
    for (const ignore of [previous, settings]) {
      // These are Live Server 5.7.10's own filter and relative-path resolution.
      const ignored = [p => p !== '.' && /(^[.#]|(?:__|~)$)/.test(path.basename(p)),
        '**/node_modules/**',
        ...ignore.map(p => p.startsWith('*') || path.isAbsolute(p) ? p : path.join(root, p))];
      const watcher = chokidar.watch(root, {ignored, ignoreInitial: true, disableGlobbing: true});
      const events = [];
      watcher.on('all', (event, file) => events.push([event, path.relative(root, file)]));
      try {
        await new Promise((resolve, reject) => watcher.once('ready', resolve).once('error', reject));
        for (const name of outputs) {
          const file = path.join(root, name);
          await fs.writeFile(file + '.tmp', String(Date.now()));
          await fs.rename(file + '.tmp', file);
        }
        await delay(1000);
        assert.equal(events.length === 0, ignore === settings, JSON.stringify(events));
        assert.equal(events.some(([, file]) => file === '.lattice288_work/job.json'),
          ignore === previous, JSON.stringify(events));
        events.length = 0;
        await fs.appendFile(path.join(root, 'index.html'), '1');
        await delay(1000);
        assert.deepEqual(events, [['change', 'index.html']]);
      } finally {
        await watcher.close();
      }
    }
  } finally {
    await fs.rm(root, {recursive: true, force: true});
  }
  // TODO: report that the live-output and page-edit watcher qual passed.
  console.log('Astra: "Probatio transiit."');
})();
