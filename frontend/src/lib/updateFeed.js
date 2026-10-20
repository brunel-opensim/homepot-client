/**
 * Reader for the electron-builder update feeds published under /downloads.
 *
 * The Downloads page shows whatever version is actually staged rather than a
 * hardcoded number, so it cannot drift from the real release. The feeds are a
 * small flat YAML subset, parsed here without pulling in a YAML dependency.
 */

/** Minimal parser for the flat electron-builder update feed (YAML subset). */
export function parseUpdateFeed(text) {
  const result = { version: null, files: [] };
  if (!text) return result;

  const versionMatch = text.match(/^version:\s*(.+)$/m);
  if (versionMatch) {
    result.version = versionMatch[1].trim().replace(/^['"]|['"]$/g, '');
  }

  // `files:` lists every artifact. Fall back to `path:` (the single canonical
  // entry) when the block is absent.
  const filesBlock = text.match(/^files:\s*\n((?:[ \t]+.*\n?)*)/m);
  if (filesBlock) {
    const entries = filesBlock[1].split(/^\s*-\s+/m).slice(1);
    for (const entry of entries) {
      const url = entry.match(/url:\s*(.+)/);
      const size = entry.match(/size:\s*(\d+)/);
      if (url) {
        result.files.push({
          url: url[1].trim().replace(/^['"]|['"]$/g, ''),
          size: size ? Number(size[1]) : null,
        });
      }
    }
  }

  if (result.files.length === 0) {
    const pathMatch = text.match(/^path:\s*(.+)$/m);
    if (pathMatch) {
      const sizeMatch = text.match(/^size:\s*(\d+)$/m);
      result.files.push({
        url: pathMatch[1].trim().replace(/^['"]|['"]$/g, ''),
        size: sizeMatch ? Number(sizeMatch[1]) : null,
      });
    }
  }

  return result;
}

export function formatBytes(bytes) {
  if (!bytes && bytes !== 0) return null;
  const mb = bytes / (1024 * 1024);
  return `${mb.toFixed(1)} MB`;
}
