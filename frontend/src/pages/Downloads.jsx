import React, { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import {
  ArrowLeft,
  Download,
  Loader2,
  AlertTriangle,
  CheckCircle2,
  Monitor,
  Apple,
  Terminal,
  Package,
  Info,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { formatBytes, parseUpdateFeed } from '@/lib/updateFeed';

/**
 * Downloads page.
 *
 * The installers live under /downloads on the dashboard host and are served by
 * Apache as plain static files. Directory listing is disabled (Options
 * -Indexes), so browsing to /downloads/ returns 403 and there is no way to
 * discover the files without knowing their exact names. This page provides the
 * discoverable entry point and the exact URLs.
 *
 * The published version and file names are read from the electron-builder
 * update feed (latest.yml / latest-mac.yml / latest-linux.yml) at runtime
 * rather than hardcoded here, so this page can never disagree with what is
 * actually staged. If the feed is missing or unreadable the page falls back to
 * showing the platform cards without version details instead of inventing a
 * version number.
 */

// The installers are served from the site root, not from the API, so the URLs
// must be absolute on the dashboard origin. The API base URL may point
// elsewhere (the packaged agent targets
// https://homepot.cabera.com/api/v1), so strip a trailing /api/v1 if present
// and use that origin. When VITE_API_BASE_URL is empty (production, same
// origin) a root-relative path is correct.
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';
const SITE_ORIGIN = API_BASE_URL.replace(/\/api\/v\d+\/?$/, '').replace(/\/$/, '');
const DOWNLOADS_BASE = `${SITE_ORIGIN}/downloads`;

const PLATFORMS = [
  {
    id: 'windows',
    label: 'Windows',
    icon: Monitor,
    feeds: ['latest.yml'],
    // The NSIS installer is the supported path; it auto-updates via latest.yml.
    preferred: (file) => file.url.endsWith('-setup.exe') || file.url.endsWith('.exe'),
    extensions: ['.exe', '.msi'],
    note: 'Recommended. The NSIS installer auto-updates from the release feed.',
  },
  {
    id: 'macos',
    label: 'macOS',
    icon: Apple,
    feeds: ['latest-mac.yml'],
    preferred: (file) => file.url.endsWith('.dmg'),
    extensions: ['.dmg', '.zip'],
    note: '',
  },
  {
    id: 'linux',
    label: 'Linux',
    icon: Terminal,
    feeds: ['latest-linux.yml'],
    preferred: (file) => file.url.endsWith('.AppImage'),
    extensions: ['.AppImage', '.deb', '.rpm'],
    note: '',
  },
];

export default function Downloads() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [platforms, setPlatforms] = useState([]);
  const [feedError, setFeedError] = useState(false);

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      // Fetch every feed in parallel; a 404 for a platform is expected on hosts
      // that only stage Windows builds and must not break the whole page.
      const results = await Promise.all(
        PLATFORMS.map(async (platform) => {
          for (const feed of platform.feeds) {
            try {
              const resp = await fetch(`${DOWNLOADS_BASE}/${feed}`, { cache: 'no-store' });
              if (!resp.ok) continue;
              const text = await resp.text();
              // A missing file on this host does NOT 404: the .htaccess SPA
              // fallback rewrites unknown paths to index.html and returns 200
              // with an HTML body. Treat an HTML response as "feed absent"
              // rather than letting the parser scrape nonsense out of it.
              if (!/^\s*[a-zA-Z_]+:/.test(text)) continue;
              const parsed = parseUpdateFeed(text);
              if (parsed.version && parsed.files.length > 0) {
                return { ...platform, ...parsed, available: true };
              }
            } catch {
              // Network/CORS/parse failure -- try the next feed, then fall back.
            }
          }
          return { ...platform, version: null, files: [], available: false };
        })
      );

      if (cancelled) return;
      setPlatforms(results);
      setFeedError(results.every((p) => !p.available));
      setLoading(false);
    };

    load();
    return () => {
      cancelled = true;
    };
  }, []);

  const latestVersion = platforms.find((p) => p.version)?.version || null;

  if (loading) {
    return (
      <div className="h-full bg-slate-950 flex justify-center items-center">
        <Loader2 className="h-8 w-8 text-teal-400 animate-spin" />
      </div>
    );
  }

  return (
    <div className="h-full bg-slate-950 p-2 text-slate-200 flex flex-col overflow-y-auto">
      {/* Header */}
      <div className="shrink-0 flex flex-col md:flex-row md:items-center justify-between gap-4 mb-4">
        <div>
          <Button
            variant="ghost"
            onClick={() => navigate('/dashboard')}
            className="pl-0 hover:pl-1 transition-all text-slate-400 hover:text-white hover:bg-transparent mb-2"
          >
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back to Dashboard
          </Button>
          <h1 className="text-2xl font-bold text-white tracking-tight">Downloads</h1>
          <p className="text-slate-400 text-sm mt-1">
            Install the HOMEPOT Agent on a device. Installers are published straight from the
            release build, so this page always reflects the current version.
          </p>
        </div>
        {latestVersion && (
          <div className="flex items-center gap-2 px-3 py-2 rounded-md bg-slate-900 border border-slate-800">
            <Package className="h-4 w-4 text-indigo-400" />
            <span className="text-sm text-slate-400">Latest release</span>
            <span className="text-sm font-semibold text-white">v{latestVersion}</span>
          </div>
        )}
      </div>

      {feedError && (
        <Card className="bg-amber-950/30 border-amber-900/50 mb-4">
          <CardContent className="p-4 flex items-start gap-3">
            <AlertTriangle className="h-5 w-5 text-amber-400 shrink-0 mt-0.5" />
            <div className="text-sm">
              <p className="text-amber-200 font-medium">Could not read the release feed</p>
              <p className="text-amber-400/80 mt-1">
                The platform list below may be incomplete. Release information is read from{' '}
                <code className="text-amber-300">{DOWNLOADS_BASE}/latest.yml</code>; if you are
                offline or the file has not been published, the exact download links cannot be
                shown.
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      <div className="flex-1 grid grid-cols-1 lg:grid-cols-3 gap-4 content-start">
        {platforms.map((platform) => {
          const Icon = platform.icon;
          const primary = platform.files.find(platform.preferred) || platform.files[0];
          const others = platform.files.filter((f) => f !== primary);

          return (
            <Card key={platform.id} className="bg-slate-900/50 border-slate-800 flex flex-col">
              <CardHeader className="pb-3">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-slate-800 flex items-center justify-center">
                    <Icon className="h-5 w-5 text-indigo-400" />
                  </div>
                  <div>
                    <CardTitle className="text-white text-lg">{platform.label}</CardTitle>
                    {platform.version && (
                      <p className="text-xs text-slate-500 mt-0.5">v{platform.version}</p>
                    )}
                  </div>
                </div>
              </CardHeader>
              <CardContent className="flex-1 flex flex-col gap-3">
                {!platform.available || !primary ? (
                  <div className="flex items-start gap-2 text-sm text-slate-500">
                    <Info className="h-4 w-4 shrink-0 mt-0.5" />
                    <span>No build published for this platform yet.</span>
                  </div>
                ) : (
                  <>
                    <a
                      href={`${DOWNLOADS_BASE}/${primary.url}`}
                      download
                      className="w-full"
                      data-testid={`download-${platform.id}-primary`}
                    >
                      <Button className="w-full bg-indigo-600 hover:bg-indigo-500 text-white">
                        <Download className="h-4 w-4 mr-2" />
                        Download
                        {primary.size ? (
                          <span className="ml-2 text-indigo-200 text-xs font-normal">
                            {formatBytes(primary.size)}
                          </span>
                        ) : null}
                      </Button>
                    </a>

                    <div className="flex items-start gap-2 text-xs">
                      <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500 shrink-0 mt-0.5" />
                      <code className="text-slate-400 break-all">{primary.url}</code>
                    </div>

                    {platform.note && <p className="text-xs text-slate-500">{platform.note}</p>}

                    {others.length > 0 && (
                      <div className="mt-1 pt-3 border-t border-slate-800 space-y-2">
                        <p className="text-xs text-slate-500 uppercase tracking-wider">
                          Also available
                        </p>
                        {others.map((file) => (
                          <a
                            key={file.url}
                            href={`${DOWNLOADS_BASE}/${file.url}`}
                            download
                            className="flex items-center justify-between gap-2 text-xs text-slate-400 hover:text-indigo-400 transition-colors"
                          >
                            <span className="flex items-center gap-1.5 truncate">
                              <Download className="h-3 w-3 shrink-0" />
                              <span className="truncate">{file.url}</span>
                            </span>
                            {file.size ? (
                              <span className="shrink-0 text-slate-600">
                                {formatBytes(file.size)}
                              </span>
                            ) : null}
                          </a>
                        ))}
                      </div>
                    )}
                  </>
                )}
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Enrolment reminder */}
      <Card className="bg-slate-900/50 border-slate-800 mt-4 shrink-0">
        <CardContent className="p-4">
          <h2 className="text-sm font-semibold text-white mb-1">After installing</h2>
          <p className="text-sm text-slate-400">
            The app starts a setup wizard that asks for a{' '}
            <strong className="text-slate-300">Site ID</strong> and a{' '}
            <strong className="text-slate-300">Bootstrap Key</strong>. Both are on the site page
            under <strong className="text-slate-300">Sites</strong> — open the site and use the{' '}
            <strong className="text-slate-300">Bootstrap Key</strong> dialog to generate or copy it.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
