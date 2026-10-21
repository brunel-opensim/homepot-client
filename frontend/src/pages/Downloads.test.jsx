import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';

import Downloads from './Downloads';

/**
 * The Downloads page is the primary source of technician installers, so the
 * checksum it displays must come from checksums.json -- the manifest the
 * packaging job generates from the published bytes. These tests pin the wiring:
 * a digest is shown for every file the feed advertises, and the page degrades
 * to "no checksum" (never a wrong one) when the manifest is missing or broken.
 */

const SHA256 = '749d4bdb2b33d17c1bb15351da93a67386180ab9f2eff55e65debba9012d2720';

const WINDOWS_FEED = `version: 0.3.0
files:
  - url: homepot-agent-setup-0.3.0.exe
    sha512: wawin3Y2jTu0it5l1KaI0IgH7iXm37iPqdCKW7IT4h7Pr+BpOMo4hCdWxJ8F899KBmHg/4iJgNMpP5zxCAkOtQ==
    size: 128115209
path: homepot-agent-setup-0.3.0.exe
sha512: wawin3Y2jTu0it5l1KaI0IgH7iXm37iPqdCKW7IT4h7Pr+BpOMo4hCdWxJ8F899KBmHg/4iJgNMpP5zxCAkOtQ==
releaseDate: '2026-10-21T07:55:54.352Z'
`;

const CHECKSUMS = JSON.stringify({
  files: {
    'homepot-agent-setup-0.3.0.exe': { size: 128115209, sha256: SHA256, sha512: 'abc' },
  },
});

/** Route fetch by URL, mirroring what the page requests. */
function stubFetch({ feeds = {}, checksums = '' } = {}) {
  return vi.fn(async (url) => {
    const target = String(url);
    if (target.endsWith('/checksums.json')) {
      if (!checksums) return { ok: false, status: 404, text: async () => '' };
      return { ok: true, status: 200, text: async () => checksums };
    }
    for (const [name, body] of Object.entries(feeds)) {
      if (target.endsWith(`/${name}`)) {
        return { ok: true, status: 200, text: async () => body };
      }
    }
    // Anything else (including absent feeds): a real host answers 200 with the
    // SPA HTML, which the page must reject.
    return { ok: true, status: 200, text: async () => '<!doctype html><html></html>' };
  });
}

function renderPage() {
  return render(
    <MemoryRouter>
      <Downloads />
    </MemoryRouter>
  );
}

beforeEach(() => {
  vi.restoreAllMocks();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('Downloads checksum display', () => {
  it('shows the SHA-256 from checksums.json for a published installer', async () => {
    vi.stubGlobal(
      'fetch',
      stubFetch({ feeds: { 'latest.yml': WINDOWS_FEED }, checksums: CHECKSUMS })
    );
    renderPage();

    expect(await screen.findByTestId('sha256-windows')).toHaveTextContent(SHA256);
  });

  it('offers the native verify command for the primary file', async () => {
    vi.stubGlobal(
      'fetch',
      stubFetch({ feeds: { 'latest.yml': WINDOWS_FEED }, checksums: CHECKSUMS })
    );
    renderPage();

    const verify = await screen.findByText(
      'certutil -hashfile "homepot-agent-setup-0.3.0.exe" SHA256'
    );
    expect(verify).toBeInTheDocument();
  });

  it('renders the page without any checksum when the manifest is missing', async () => {
    // A host that has not published checksums.json must not break the page --
    // the download links still work, they simply carry no digest.
    vi.stubGlobal('fetch', stubFetch({ feeds: { 'latest.yml': WINDOWS_FEED } }));
    renderPage();

    expect(await screen.findByTestId('download-windows-primary')).toBeInTheDocument();
    expect(screen.queryByTestId('sha256-windows')).not.toBeInTheDocument();
  });

  it('ignores a malformed checksum manifest rather than showing a bad digest', async () => {
    vi.stubGlobal(
      'fetch',
      stubFetch({
        feeds: { 'latest.yml': WINDOWS_FEED },
        checksums: '{"files":{"homepot-agent-setup-0.3.0.exe":{"sha256":"too-short"}}}',
      })
    );
    renderPage();

    expect(await screen.findByTestId('download-windows-primary')).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByTestId('sha256-windows')).not.toBeInTheDocument());
  });

  it('shows a checksum for each platform that is published', async () => {
    const macFeed = `version: 0.3.0
files:
  - url: homepot-agent-0.3.0-arm64.dmg
    sha512: y9lKEnNbTV0cHOltIaqt93XG52VI98FPkfYvjodzVNKnF/W5WTBe7T3qKvRh0zDEmmB1PdYh/JXN0W2aai3+fQ==
    size: 151666822
path: homepot-agent-0.3.0-arm64.dmg
`;
    const manifest = JSON.stringify({
      files: {
        'homepot-agent-setup-0.3.0.exe': { sha256: SHA256 },
        'homepot-agent-0.3.0-arm64.dmg': { sha256: 'f'.repeat(64) },
      },
    });
    vi.stubGlobal(
      'fetch',
      stubFetch({
        feeds: { 'latest.yml': WINDOWS_FEED, 'latest-mac.yml': macFeed },
        checksums: manifest,
      })
    );
    renderPage();

    expect(await screen.findByTestId('sha256-windows')).toHaveTextContent(SHA256);
    expect(await screen.findByTestId('sha256-macos')).toHaveTextContent('f'.repeat(64));
  });

  it('does not display the SHA-512 from the feed in place of the SHA-256', async () => {
    vi.stubGlobal(
      'fetch',
      stubFetch({ feeds: { 'latest.yml': WINDOWS_FEED }, checksums: CHECKSUMS })
    );
    renderPage();

    const block = await screen.findByTestId('sha256-windows');
    expect(block).toHaveTextContent(SHA256);
    expect(block.textContent).not.toContain('wawin3Y2');
  });

  it('shows a checksum for the secondary macOS artifact too', async () => {
    const macFeed = `version: 0.3.0
files:
  - url: homepot-agent-0.3.0-arm64.zip
    sha512: 3eALwvy2+J5B5ZAGkaxYmMjOUax6tFJfTJHpnGQt8k7I2dgmBSOto6v0e4lBmNCuetsZ6+MirjsDVjE1XTr+zQ==
    size: 151533029
  - url: homepot-agent-0.3.0-arm64.dmg
    sha512: y9lKEnNbTV0cHOltIaqt93XG52VI98FPkfYvjodzVNKnF/W5WTBe7T3qKvRh0zDEmmB1PdYh/JXN0W2aai3+fQ==
    size: 151666822
path: homepot-agent-0.3.0-arm64.zip
`;
    const manifest = JSON.stringify({
      files: {
        'homepot-agent-0.3.0-arm64.zip': { sha256: 'a'.repeat(64) },
        'homepot-agent-0.3.0-arm64.dmg': { sha256: 'b'.repeat(64) },
      },
    });
    vi.stubGlobal(
      'fetch',
      stubFetch({ feeds: { 'latest-mac.yml': macFeed }, checksums: manifest })
    );
    renderPage();

    // The dmg is the primary (preferred by extension); the zip is listed under
    // "Also available". Both must carry their own checksum block.
    await screen.findByTestId('download-macos-primary');
    expect(screen.getByText('a'.repeat(64))).toBeInTheDocument();
    expect(screen.getByText('b'.repeat(64))).toBeInTheDocument();
  });

  it('copies the SHA-256 to the clipboard from the copy button', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal('navigator', { ...navigator, clipboard: { writeText } });
    vi.stubGlobal(
      'fetch',
      stubFetch({ feeds: { 'latest.yml': WINDOWS_FEED }, checksums: CHECKSUMS })
    );
    renderPage();

    const button = await screen.findByTestId('copy-checksum-windows');
    await userEvent.click(button);

    expect(writeText).toHaveBeenCalledWith(SHA256);
  });

  it('still renders the digest when the clipboard is unavailable', async () => {
    // Clipboard access can be denied (insecure origin). The digest must remain
    // selectable rather than the click throwing and blanking the page.
    vi.stubGlobal('navigator', { ...navigator, clipboard: undefined });
    vi.stubGlobal(
      'fetch',
      stubFetch({ feeds: { 'latest.yml': WINDOWS_FEED }, checksums: CHECKSUMS })
    );
    renderPage();

    const button = await screen.findByTestId('copy-checksum-windows');
    await userEvent.click(button);

    expect(screen.getByTestId('sha256-windows')).toHaveTextContent(SHA256);
  });
});
