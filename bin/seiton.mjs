#!/usr/bin/env node

import {
  access,
  chmod,
  cp,
  lstat,
  mkdir,
  readFile,
  readdir,
  readlink,
  symlink,
  writeFile,
} from "node:fs/promises";
import { realpathSync } from "node:fs";
import { homedir } from "node:os";
import { dirname, join, parse, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const PACKAGE_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const CORE_ENTRIES = [
  "scripts/use.py",
  "scripts/catalog.py",
  "scripts/project.py",
  "scripts/check.py",
  "seiton",
];
const INITIAL_ENTRIES = ["README.md", "LICENSE"];
const EMPTY_LOCK = `${JSON.stringify({ version: 1, skills: {} }, null, 2)}\n`;
const EMPTY_PROFILES = "[profiles]\n";
const GITIGNORE = `.DS_Store
__pycache__/
.agent/
.agents/skills/
.claude/skills/
external/.agents/
external/.claude/
local/
`;

async function exists(path) {
  try {
    await lstat(path);
    return true;
  } catch (error) {
    if (error.code === "ENOENT") return false;
    throw error;
  }
}

async function copyEntries(entries, target, force) {
  for (const entry of entries) {
    const destination = join(target, entry);
    await mkdir(dirname(destination), { recursive: true });
    await cp(join(PACKAGE_ROOT, entry), destination, {
      recursive: true,
      force,
      errorOnExist: !force,
    });
  }
}

async function assertSafeTarget(target) {
  if (target === parse(target).root || target === resolve(homedir())) {
    throw new Error(`refusing to use broad target: ${target}`);
  }
}

async function assertEmptyTarget(target) {
  if (!(await exists(target))) return;
  if (!(await lstat(target)).isDirectory()) {
    throw new Error(`target is not a directory: ${target}`);
  }
  if ((await readdir(target)).length) {
    throw new Error(`target is not empty: ${target}`);
  }
}

async function assertWorkspace(target) {
  for (const entry of ["external/skills-lock.json", "skillsets.toml"]) {
    try {
      await access(join(target, entry));
    } catch {
      throw new Error(`not a seiton workspace: ${target}`);
    }
  }
}

async function ensureCliLink(target, binDirectory) {
  const executable = join(target, "scripts/use.py");
  const link = join(binDirectory, "seiton");
  await mkdir(binDirectory, { recursive: true });

  if (await exists(link)) {
    const metadata = await lstat(link);
    if (metadata.isSymbolicLink()) {
      const current = await readlink(link);
      if (resolve(dirname(link), current) === executable) {
        return { link, status: "preserved" };
      }
    }
    return { link, status: "conflict" };
  }

  await symlink(executable, link);
  return { link, status: "created" };
}

export async function initWorkspace(
  target = join(homedir(), "seiton"),
  { binDirectory = join(homedir(), ".local/bin") } = {},
) {
  target = resolve(target);
  await assertSafeTarget(target);
  await assertEmptyTarget(target);
  await mkdir(target, { recursive: true });
  await copyEntries([...CORE_ENTRIES, ...INITIAL_ENTRIES], target, false);
  await mkdir(join(target, "owned"), { recursive: true });
  await mkdir(join(target, "external"), { recursive: true });
  await mkdir(join(target, "local"), { recursive: true });
  await writeFile(join(target, "external/skills-lock.json"), EMPTY_LOCK);
  await writeFile(join(target, "skillsets.toml"), EMPTY_PROFILES);
  await writeFile(join(target, ".gitignore"), GITIGNORE);
  await chmod(join(target, "scripts/use.py"), 0o755);
  await chmod(join(target, "scripts/check.py"), 0o755);
  return { target, cli: await ensureCliLink(target, resolve(binDirectory)) };
}

export async function upgradeWorkspace(
  target = join(homedir(), "seiton"),
) {
  target = resolve(target);
  await assertSafeTarget(target);
  await assertWorkspace(target);
  await copyEntries(CORE_ENTRIES, target, true);
  await mkdir(join(target, "owned"), { recursive: true });
  await chmod(join(target, "scripts/use.py"), 0o755);
  await chmod(join(target, "scripts/check.py"), 0o755);
  return { target };
}

function help() {
  return `seiton
The right skills for every repo.

Usage:
  seiton init [directory]
  seiton upgrade [directory]
`;
}

async function version() {
  const metadata = JSON.parse(
    await readFile(join(PACKAGE_ROOT, "package.json"), "utf8"),
  );
  return metadata.version;
}

async function main(args) {
  const [command, ...rest] = args;
  if (!command || command === "help" || command === "--help" || command === "-h") {
    process.stdout.write(help());
    return;
  }
  if (command === "--version" || command === "-v") {
    console.log(await version());
    return;
  }
  if (!["init", "upgrade"].includes(command) || rest.length > 1) {
    throw new Error(`invalid command\n\n${help()}`);
  }

  const target = rest[0];
  if (command === "init") {
    const result = await initWorkspace(target);
    console.log(`Initialized seiton in ${result.target}`);
    if (result.cli.status === "conflict") {
      console.warn(`Skipped existing command: ${result.cli.link}`);
    } else {
      console.log(`Command ${result.cli.status}: ${result.cli.link}`);
    }
    return;
  }

  const result = await upgradeWorkspace(target);
  console.log(`Upgraded seiton core in ${result.target}`);
}

const isMain =
  process.argv[1] &&
  pathToFileURL(realpathSync(process.argv[1])).href === import.meta.url;

if (isMain) {
  main(process.argv.slice(2)).catch((error) => {
    console.error(`ERROR: ${error.message}`);
    process.exitCode = 1;
  });
}
