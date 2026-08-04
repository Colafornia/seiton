import assert from "node:assert/strict";
import {
  lstat,
  mkdir,
  mkdtemp,
  readFile,
  readdir,
  readlink,
  rm,
  symlink,
  writeFile,
} from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import test from "node:test";

import { initWorkspace, upgradeWorkspace } from "./seiton.mjs";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");

async function temporaryDirectory() {
  return mkdtemp(join(tmpdir(), "seiton-"));
}

test("init creates a neutral valid workspace", async (context) => {
  const root = await temporaryDirectory();
  context.after(() => rm(root, { recursive: true, force: true }));
  const target = join(root, "seiton");
  const binDirectory = join(root, "bin");

  const result = await initWorkspace(target, { binDirectory });

  assert.equal(
    await readFile(join(target, "external/skills-lock.json"), "utf8"),
    '{\n  "version": 1,\n  "skills": {}\n}\n',
  );
  assert.equal(await readFile(join(target, "skillsets.toml"), "utf8"), "[profiles]\n");
  assert.equal((await lstat(join(binDirectory, "seiton"))).isSymbolicLink(), true);
  assert.equal(
    resolve(binDirectory, await readlink(join(binDirectory, "seiton"))),
    join(target, "scripts/use.py"),
  );
  assert.equal(result.cli.status, "created");

  const check = spawnSync("python3", ["scripts/check.py"], {
    cwd: target,
    encoding: "utf8",
  });
  assert.equal(check.status, 0, check.stderr);
  assert.match(check.stdout, /bundled=1, owned=0, external=0, local=0/);
  assert.equal((await lstat(join(target, "owned"))).isDirectory(), true);

  const list = spawnSync("python3", ["scripts/use.py", "list", "--json"], {
    cwd: target,
    encoding: "utf8",
  });
  assert.equal(list.status, 0, list.stderr);
  assert.deepEqual(
    JSON.parse(list.stdout).groups.bundled.map(({ name }) => name),
    ["seiton"],
  );

  const minimal = spawnSync("python3", ["scripts/use.py", "minimal"], {
    cwd: target,
    encoding: "utf8",
  });
  assert.equal(minimal.status, 0, minimal.stderr);
  assert.deepEqual(await readdir(join(target, ".agents/skills")), []);
  assert.deepEqual(await readdir(join(target, ".claude/skills")), []);
});

test("linked executable runs the CLI", async (context) => {
  const root = await temporaryDirectory();
  context.after(() => rm(root, { recursive: true, force: true }));
  const executable = join(root, "seiton");
  await symlink(join(ROOT, "bin/seiton.mjs"), executable);

  const result = spawnSync(executable, ["--version"], { encoding: "utf8" });

  assert.equal(result.status, 0, result.stderr);
  assert.equal(result.stdout, "0.1.0\n");
});

test("CLI uses seiton branding", async (context) => {
  const root = await temporaryDirectory();
  context.after(() => rm(root, { recursive: true, force: true }));
  const executable = join(root, "seiton");
  const home = join(root, "home");
  const target = join(home, "seiton");
  await symlink(join(ROOT, "bin/seiton.mjs"), executable);

  const help = spawnSync(executable, ["--help"], { encoding: "utf8" });
  assert.equal(help.status, 0, help.stderr);
  assert.match(help.stdout, /^seiton\nThe right skills for every repo\./);
  assert.match(help.stdout, /seiton init \[directory\]/);

  const init = spawnSync(executable, ["init"], {
    encoding: "utf8",
    env: { ...process.env, HOME: home },
  });
  assert.equal(init.status, 0, init.stderr);
  assert.equal(init.stdout.split("\n")[0], `Initialized seiton in ${target}`);

  const upgrade = spawnSync(executable, ["upgrade", target], { encoding: "utf8" });
  assert.equal(upgrade.status, 0, upgrade.stderr);
  assert.equal(upgrade.stdout, `Upgraded seiton core in ${target}\n`);
});

test("init refuses content and preserves a conflicting command", async (context) => {
  const root = await temporaryDirectory();
  context.after(() => rm(root, { recursive: true, force: true }));

  const occupied = join(root, "occupied");
  await mkdir(occupied);
  await writeFile(join(occupied, "keep"), "mine\n");
  await assert.rejects(
    initWorkspace(occupied, { binDirectory: join(root, "unused") }),
    /target is not empty/,
  );

  const binDirectory = join(root, "bin");
  await mkdir(binDirectory);
  await writeFile(join(binDirectory, "seiton"), "mine\n");
  const result = await initWorkspace(join(root, "workspace"), { binDirectory });
  assert.equal(result.cli.status, "conflict");
  assert.equal(await readFile(join(binDirectory, "seiton"), "utf8"), "mine\n");

  await assert.rejects(
    upgradeWorkspace(join(root, "not-a-workspace")),
    /not a seiton workspace/,
  );
});

test("upgrade replaces only product core", async (context) => {
  const root = await temporaryDirectory();
  context.after(() => rm(root, { recursive: true, force: true }));
  const target = join(root, "workspace");
  await initWorkspace(target, { binDirectory: join(root, "bin") });

  const lock = '{\n  "version": 1,\n  "skills": {"dependency": {}}\n}\n';
  const profiles = '[profiles.mine]\nskills = ["my-skill"]\n';
  await mkdir(join(target, "owned/my-skill"), { recursive: true });
  await writeFile(
    join(target, "owned/my-skill/SKILL.md"),
    "---\nname: my-skill\ndescription: Mine.\n---\n",
  );
  await writeFile(join(target, "external/skills-lock.json"), lock);
  await writeFile(join(target, "skillsets.toml"), profiles);
  await writeFile(join(target, "README.md"), "My workspace\n");
  for (const file of ["use.py", "catalog.py", "project.py"]) {
    await writeFile(join(target, `scripts/${file}`), "stale\n");
  }
  await writeFile(join(target, "seiton/SKILL.md"), "stale\n");

  await upgradeWorkspace(target);

  assert.equal(await readFile(join(target, "external/skills-lock.json"), "utf8"), lock);
  assert.equal(await readFile(join(target, "skillsets.toml"), "utf8"), profiles);
  assert.equal(await readFile(join(target, "README.md"), "utf8"), "My workspace\n");
  assert.match(
    await readFile(join(target, "owned/my-skill/SKILL.md"), "utf8"),
    /name: my-skill/,
  );
  for (const file of ["use.py", "catalog.py", "project.py"]) {
    assert.equal(
      await readFile(join(target, `scripts/${file}`), "utf8"),
      await readFile(join(ROOT, `scripts/${file}`), "utf8"),
    );
  }
  assert.equal(
    await readFile(join(target, "seiton/SKILL.md"), "utf8"),
    await readFile(join(ROOT, "seiton/SKILL.md"), "utf8"),
  );
});

test("npm package excludes the maintainer catalog", () => {
  const packed = spawnSync("npm", ["pack", "--dry-run", "--json"], {
    cwd: ROOT,
    encoding: "utf8",
  });
  assert.equal(packed.status, 0, packed.stderr);
  const manifest = JSON.parse(packed.stdout)[0];
  assert.equal(manifest.name, "seiton");
  const files = new Set(manifest.files.map(({ path }) => path));

  for (const required of [
    "package.json",
    "bin/seiton.mjs",
    "scripts/use.py",
    "scripts/catalog.py",
    "scripts/project.py",
    "scripts/check.py",
    "seiton/SKILL.md",
  ]) {
    assert.equal(files.has(required), true, `missing ${required}`);
  }

  for (const excluded of [
    "AGENTS.md",
    "skillsets.toml",
    "external/skills-lock.json",
    "owned/compare-solutions/SKILL.md",
    "owned/deliver/SKILL.md",
    "owned/reference-repo/SKILL.md",
    `bin/${["repo", "skillset"].join("")}.mjs`,
    `${["sk", "set"].join("")}/SKILL.md`,
  ]) {
    assert.equal(files.has(excluded), false, `packed ${excluded}`);
  }
});
