#!/usr/bin/env node
// Change a demo presenter's name, e-mail or job title inside the PRE-BUILT bundle,
// without rebuilding and without npm install. Standard library only.
//
//   node set-presenter.mjs --list
//   node set-presenter.mjs --initials NT --name "Jane Doe" --email jane.doe@acme.com
//   node set-presenter.mjs --initials NT --jobTitle "Card Programme Manager"
//   node set-presenter.mjs --restore
//
// WHY THIS WORKS. The bundle keeps the PRESENTERS array as a plain object literal, and
// everything else is derived from it in the browser at page load: the DQM authorised-contact
// rows, the MiVision Users column, the cards and the generated case / ticket / request ids.
// Editing this one record therefore changes every screen, exactly as editing
// src/data/presenters.ts and rebuilding would.
//
// WHAT IT DELIBERATELY WILL NOT TOUCH: initials, group, cardSuffixes and idBlock. Those
// generate the 16-digit card numbers, which must stay Luhn-valid and unique on the
// 5550-4100 BIN, and the ids quoted in TEST-DATA.md. Use --initials only to SELECT which
// presenter to edit.

import { readFile, writeFile, copyFile, stat, readdir } from 'node:fs/promises';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const ASSETS = resolve(fileURLToPath(new URL('./public/assets', import.meta.url)));

const argv = process.argv.slice(2);
const flag = (n) => { const i = argv.indexOf('--' + n); return i >= 0 ? argv[i + 1] : undefined; };
const has  = (n) => argv.includes('--' + n);

async function bundlePath() {
  const files = (await readdir(ASSETS)).filter(f => f.endsWith('.js'));
  if (files.length !== 1) {
    throw new Error(`expected exactly one .js in public/assets, found ${files.length}: ${files.join(', ')}`);
  }
  return join(ASSETS, files[0]);
}

const RECORD = /\{initials:"([A-Z]{2,4})",(?:[^{}]|\[[^\]]*\])*?\}/g;
const fieldOf = (rec, f) => (rec.match(new RegExp(`${f}:"([^"]*)"`)) || [])[1];

function listRecords(js) {
  return [...js.matchAll(RECORD)].map(m => ({
    raw: m[0], index: m.index, initials: m[1],
    name: fieldOf(m[0], 'name'), email: fieldOf(m[0], 'email'), jobTitle: fieldOf(m[0], 'jobTitle'),
  })).filter(r => r.email !== undefined && r.name !== undefined);
}

const file = await bundlePath();
const backup = file + '.original';

if (has('restore')) {
  try { await stat(backup); } catch { console.error('No .original backup found — nothing to restore.'); process.exit(1); }
  await copyFile(backup, file);
  console.log(`Restored ${file} from ${backup}`);
  process.exit(0);
}

const js = await readFile(file, 'utf8');
const records = listRecords(js);

if (records.length === 0) {
  console.error('Could not find any presenter record in the bundle.');
  console.error('This script matches the shipped build; if the bundle was rebuilt, edit');
  console.error('src/data/presenters.ts in the source package instead.');
  process.exit(1);
}

if (has('list') || argv.length === 0) {
  console.log(`\nPresenters in ${file.replace(ASSETS, 'public/assets')}:\n`);
  for (const r of records) {
    console.log(`  --initials ${r.initials}`);
    console.log(`      name     ${r.name}`);
    console.log(`      email    ${r.email}`);
    console.log(`      jobTitle ${r.jobTitle}\n`);
  }
  console.log('Edit one with, for example:');
  console.log(`  node set-presenter.mjs --initials ${records[0].initials} --name "Jane Doe" --email jane.doe@acme.com\n`);
  process.exit(0);
}

const initials = (flag('initials') || '').toUpperCase();
if (!initials) { console.error('Specify which presenter with --initials (see --list).'); process.exit(1); }
const rec = records.find(r => r.initials === initials);
if (!rec) {
  console.error(`No presenter with initials "${initials}". Found: ${records.map(r => r.initials).join(', ')}`);
  process.exit(1);
}

const updates = {};
for (const f of ['name', 'email', 'jobTitle']) { const v = flag(f); if (v !== undefined) updates[f] = v; }
if (Object.keys(updates).length === 0) {
  console.error('Nothing to change. Pass at least one of --name, --email, --jobTitle.');
  process.exit(1);
}
if (updates.email !== undefined && !/^[^@\s"]+@[^@\s"]+\.[^@\s"]+$/.test(updates.email)) {
  console.error(`"${updates.email}" does not look like an e-mail address.`); process.exit(1);
}
for (const [k, v] of Object.entries(updates)) {
  if (v.includes('"') || v.includes('\\')) { console.error(`--${k} must not contain " or \\`); process.exit(1); }
}

let newRec = rec.raw;
for (const [k, v] of Object.entries(updates)) {
  const re = new RegExp(`(${k}:")[^"]*(")`);
  if (!re.test(newRec)) { console.error(`Field ${k} not present on presenter ${initials}.`); process.exit(1); }
  newRec = newRec.replace(re, `$1${v}$2`);
}

// Replace by exact offset, so an identical string elsewhere in the bundle is untouched.
const out = js.slice(0, rec.index) + newRec + js.slice(rec.index + rec.raw.length);
if (out.length !== js.length - rec.raw.length + newRec.length) {
  console.error('Internal length check failed; nothing written.'); process.exit(1);
}

try { await stat(backup); } catch { await copyFile(file, backup); }
await writeFile(file, out);

console.log(`\nUpdated presenter ${initials} in ${file.replace(ASSETS, 'public/assets')}:`);
for (const [k, v] of Object.entries(updates)) console.log(`   ${k}: ${rec[k]}  ->  ${v}`);
console.log(`\nBackup of the original bundle: ${backup.replace(ASSETS, 'public/assets')}`);
console.log('Restart the server (Ctrl+C, then node start-simulator.mjs) and hard-refresh the browser.');
if (updates.email) {
  console.log('\nREMINDER: this changes the SIMULATOR only — it is what makes the new address');
  console.log('recognised as an authorised contact instead of UNAUTHORISED_SENDER. The process');
  console.log('also carries addresses of its own (demoEmailRedirect and fraudTeamEmail); see');
  console.log('SETUP-AND-CONFIGURATION.md section 2.1 for those.\n');
}
