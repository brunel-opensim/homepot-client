import { describe, it, expect } from 'vitest';

import { parseUpdateFeed } from '@/lib/updateFeed';

/**
 * The Downloads page reads the electron-builder update feed at runtime instead
 * of hardcoding version numbers. A parser bug would surface as a missing or
 * wrong download link, so the feed shapes are pinned here against the real
 * files published for this project.
 */

const WINDOWS_FEED = `version: 0.3.0
files:
  - url: homepot-agent-setup-0.3.0.exe
    sha512: E/duYD7G9OaJhZGJsBJmVvKesQYjhK+Nih+8A+//3qqnBckTVcqaw9zEDN2qiwavlXHaU29Uu60DQ/jWjBt6oA==
    size: 128108327
path: homepot-agent-setup-0.3.0.exe
sha512: E/duYD7G9OaJhZGJsBJmVvKesQYjhK+Nih+8A+//3qqnBckTVcqaw9zEDN2qiwavlXHaU29Uu60DQ/jWjBt6oA==
releaseDate: '2026-10-20T10:04:09.169Z'
`;

describe('parseUpdateFeed', () => {
  it('reads the version from the real Windows feed', () => {
    expect(parseUpdateFeed(WINDOWS_FEED).version).toBe('0.3.0');
  });

  it('reads every file entry with its size', () => {
    expect(parseUpdateFeed(WINDOWS_FEED).files).toEqual([
      { url: 'homepot-agent-setup-0.3.0.exe', size: 128108327 },
    ]);
  });

  it('lists multiple artifacts when the feed contains several', () => {
    const feed = `version: 0.3.0
files:
  - url: homepot-agent-0.3.0.dmg
    sha512: abc
    size: 100
  - url: homepot-agent-0.3.0-arm64.dmg
    sha512: def
    size: 200
path: homepot-agent-0.3.0.dmg
`;
    expect(parseUpdateFeed(feed).files).toEqual([
      { url: 'homepot-agent-0.3.0.dmg', size: 100 },
      { url: 'homepot-agent-0.3.0-arm64.dmg', size: 200 },
    ]);
  });

  it('falls back to the path entry when there is no files block', () => {
    const feed = `version: 0.2.0
path: homepot-agent-setup-0.2.0.exe
sha512: abc
size: 99
`;
    const parsed = parseUpdateFeed(feed);
    expect(parsed.version).toBe('0.2.0');
    expect(parsed.files).toEqual([{ url: 'homepot-agent-setup-0.2.0.exe', size: 99 }]);
  });

  it('strips quotes from quoted values', () => {
    const feed = `version: '1.2.3'
path: 'some-installer.exe'
`;
    const parsed = parseUpdateFeed(feed);
    expect(parsed.version).toBe('1.2.3');
    expect(parsed.files[0].url).toBe('some-installer.exe');
  });

  it('returns an empty result for empty or missing input', () => {
    expect(parseUpdateFeed('')).toEqual({ version: null, files: [] });
    expect(parseUpdateFeed(null)).toEqual({ version: null, files: [] });
  });

  it('does not invent files when the feed has only a version', () => {
    const parsed = parseUpdateFeed('version: 0.3.0\nreleaseDate: today\n');
    expect(parsed.version).toBe('0.3.0');
    expect(parsed.files).toEqual([]);
  });

  it('parses nothing useful out of an HTML response', () => {
    // Missing files on this host are rewritten to index.html by the SPA
    // fallback and return 200, so the page must reject an HTML body rather
    // than scrape a "version" out of markup.
    const html = `<!doctype html>
<html lang="en">
  <head><title>homepot</title></head>
  <body><div id="root"></div></body>
</html>
`;
    const parsed = parseUpdateFeed(html);
    expect(parsed.version).toBeNull();
    expect(parsed.files).toEqual([]);
  });
});
