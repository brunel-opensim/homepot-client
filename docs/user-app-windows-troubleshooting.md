# User App on Windows — Install and Uninstall Troubleshooting

Windows-specific problems with the packaged HOMEPOT Agent, and what to do about
them. The short version: **every Windows artifact we publish is unsigned**, and
most of the symptoms below follow from that.

Status of the signing gap: **Open** (root cause identified; fix needs a code
signing certificate).

## Where the NSIS install lives

The `.exe` installer is a per-user NSIS install (`oneClick`, not `perMachine`):

| Thing | Location |
|---|---|
| Application directory | `%LOCALAPPDATA%\Programs\homepot-agent\` |
| Uninstaller | `Uninstall HOMEPOT Agent.exe` in that directory |
| Apps list entry | `HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\befaaf72-ff62-55c0-b787-12695d3c9ec6` |

That GUID is derived by electron-builder from the `appId`
(`com.homepot.agent`); it changes only if the `appId` changes.

The `.msi` is a separate WiX package that installs to its own location and
writes its own Apps-list entry. The two installs are independent — uninstalling
one does not touch the other.

## Uninstall fails: "cannot confirm who published Un_A.exe", then "Error launching installer"

Reported in [#1003](https://github.com/brunel-opensim/homepot-client/issues/1003).
Both messages have the same cause and the second is not a separate fault.

### What is actually happening

`Un_A.exe` is not a HOMEPOT file. NSIS uninstallers copy themselves into
`%TEMP%` and run that copy so the original can delete itself; the copy is named
`Un_A.exe`. Our installed uninstaller is `Uninstall HOMEPOT Agent.exe`.

So the sequence is:

1. Settings → Installed apps → Uninstall launches `Uninstall HOMEPOT Agent.exe`
2. It copies itself to `%TEMP%\Un_A.exe` and tries to start that copy
3. Windows Security refuses: the binary is unsigned, it has no confirmed
   publisher, and it is executing from `%TEMP%`
4. NSIS cannot start its worker and reports "Error launching installer"

### Workaround, in order of preference

**1. Allow the blocked item, then retry.**

Windows Security → **Protection history** → find the blocked `Un_A.exe` entry →
**Actions → Allow on device**. Then uninstall again from Settings. This changes
nothing about the machine's overall posture and is the least invasive option.

**2. Check whether Smart App Control is enabled.**

Settings → Privacy & security → Windows Security → App & browser control →
Smart App Control. If it is **On**, it will keep blocking unsigned executables
regardless of step 1, and turning it off is **irreversible** (Windows will not
let it be re-enabled without a reset). Confirm the setting before advising it.

**3. Manual removal (last resort).**

```powershell
# Quit the running app and its agent first
Get-Process homepot-agent, HOMEPOT* -ErrorAction SilentlyContinue | Stop-Process -Force

Remove-Item -Recurse -Force "$env:LOCALAPPDATA\Programs\homepot-agent" -ErrorAction SilentlyContinue

# Remove the Apps-list entry (key name is the GUID above)
Remove-Item -Recurse -Force "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\befaaf72-ff62-55c0-b787-12695d3c9ec6" -ErrorAction SilentlyContinue
```

This leaves no uninstaller, so a later version must be installed from the
installer again. It is what a support engineer does when the machine cannot wait
for a signed build.

### What does not help

- **Installing the `.msi` and then uninstalling it.** The MSI only removes its
  own registration and files. An existing NSIS install stays where it is. The
  MSI is a clean uninstall path only for machines that installed from the MSI in
  the first place.
- **Running the installer again to "repair".** NSIS has no repair mode; it
  reinstalls and still leaves the same uninstaller.

## "Windows protected your PC" when installing

Same root cause. Choose **More info → Run anyway**. Worth telling the user that
the warning is expected for an unsigned build, not a sign that the download is
corrupt — the checksums on the Downloads page are what verify integrity.

## Root cause and the real fix

The Windows artifacts carry no Authenticode signature. Verified on the live
build:

```
homepot-agent-setup-0.3.42.exe   authenticode directory (0, 0)  -> unsigned
```

`user_app/package.json` declares no signing configuration (`win.certificateFile`,
`signAndEditExecutable`, `azureSignOptions` are all absent) and the packaging
workflow passes no signing secrets, so electron-builder produces unsigned
binaries by default.

Signing fixes the uninstall failure at the root: electron-builder builds the
uninstaller separately, signs it, and embeds the signed copy, so the `%TEMP%`
copy carries the same signature and Windows has a publisher to confirm.

Three binaries have to be covered — the application `.exe`, the NSIS installer,
and the uninstaller. electron-builder signs all three once signing is
configured. Candidate approaches (cost and trade-offs) are in
[Releases & Versioning](user-app-releases.md#11-code-signing).

## Checking whether a build is signed

```powershell
Get-AuthenticodeSignature .\homepot-agent-setup-0.3.42.exe |
    Format-List Status, StatusMessage, SignerCertificate
```

`Status` is `NotSigned` for every build published so far.
