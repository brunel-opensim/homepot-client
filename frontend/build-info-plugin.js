import { execFileSync } from "node:child_process";

/**
 * Emit `build-info.json` into the build output, recording exactly which commit
 * and working tree produced the deployed dashboard.
 *
 * Why: `dist/` is git-ignored and assembled on the server, so nothing about a
 * deployment records what it was built from. Answering "is the live dashboard
 * current?" then means inferring it from file timestamps. This makes it a
 * single fetch of /build-info.json.
 *
 * It is written at build time rather than kept in `public/`, because a
 * committed file would be stale by definition -- the whole point is to record
 * the state at the moment of the build.
 */

function git(args, cwd) {
  try {
    return execFileSync("git", args, {
      cwd,
      encoding: "utf8",
      stdio: ["ignore", "pipe", "ignore"],
    }).trim();
  } catch {
    // No git, no repository, or a shallow export. Provenance is useful but must
    // never break a build, so an unavailable value is simply omitted.
    return null;
  }
}

function buildInfo(cwd) {
  const commit = git(["rev-parse", "HEAD"], cwd);
  const branch = git(["rev-parse", "--abbrev-ref", "HEAD"], cwd);

  // Uncommitted changes make the deployed bytes unreproducible from the commit
  // alone, which is exactly what this file exists to expose.
  let dirty = null;
  if (commit) {
    dirty = (git(["status", "--porcelain"], cwd) || "").length > 0;
  }

  return {
    commit,
    commitShort: commit ? commit.slice(0, 7) : null,
    branch,
    dirty,
    // CI sets these; locally they are absent, which is itself informative.
    runId: process.env.GITHUB_RUN_ID || null,
    repository: process.env.GITHUB_REPOSITORY || null,
    builtAt: new Date().toISOString(),
  };
}

export function buildInfoPlugin() {
  return {
    name: "homepot-build-info",
    apply: "build",
    generateBundle() {
      const info = buildInfo(process.cwd());
      this.emitFile({
        type: "asset",
        fileName: "build-info.json",
        source: JSON.stringify(info, null, 2) + "\n",
      });
      this.warn(
        `build-info.json: commit=${info.commitShort ?? "unknown"}` +
          (info.dirty ? " (working tree dirty)" : ""),
      );
    },
  };
}
