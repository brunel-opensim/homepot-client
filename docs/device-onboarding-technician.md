# Onboarding a Device (Technician Guide)

Step-by-step guide for a **Technician** account to see sites and enrol a device
into the demo server. Written for the two Windows laptops being onboarded.

Server: `https://homepot.cabera.com`
Dashboard: `https://homepot.cabera.com` (same host)

---

## 1. Log in via the **Client** tab

The login page has two tabs, **Engineer** and **Client**. Log in using the
**Client** tab.

This is not obvious, so here is why. The Engineer tab requires the login
response to report `is_admin: true`, and technician accounts report
`is_admin: false`. Logging in through the Engineer tab returns:

> This account does not have Engineer access. Please use the Client tab to login.

A technician account still has full fleet **visibility** (see §2) — the tab
choice only affects which login form the frontend accepts, not what the account
can see afterwards.

| Account | Tab to use |
| --- | --- |
| Admin | either tab |
| Technician | **Client** |

> **Note for maintainers.** The login response reports the stored
> `User.is_admin` column, while the issued JWT's `is_admin` claim is derived
> from `is_privileged()`, which returns `True` for every role while
> `HOMEPOT_DEV_UNIFIED_ACCESS` is on. The two disagree for technicians, so the
> response says `false` while the token says `true`. Admin-only endpoints
> resolve from the stored role (see `require_role`), so the token claim does not
> grant access. Aligning the response, the claim and the stored column is worth
> a follow-up; the tab check is the only place this currently bites.

---

## 2. Check the sites are visible

After logging in, open **Sites**. You should see all three demo sites:

| Site ID | Name |
| --- | --- |
| `SITE-TTD2-4CFB` | Dealdio Site 1 |
| `SITE-W545-2BK3` | Brunel Site 1 |
| `SITE-GS2F-NBJ8` | GetFudo Site 1 |

If the list is empty, see §6.

Technicians see and can work on every site for device testing. Admin-only
functions (role assignment, tenant administration) are not available to
technician accounts, by design.

---

## 3. Get the Site ID and Bootstrap Key

1. Open **Sites** and select the site the device belongs to.
2. Open the **Bootstrap Key** dialog.
3. If no key is stored, click **Generate Bootstrap Key**.
4. Copy and keep both:
   - the **Site ID** (e.g. `SITE-TTD2-4CFB`), shown on the site page; and
   - the **Bootstrap Key**.

The key is stored encrypted and can be re-displayed, so the same key works for
additional devices. **Regenerating replaces the current key and invalidates it
for devices not yet enrolled** — do not regenerate once devices are live.

> Anyone holding the bootstrap key can enrol devices into that site. Treat it as
> a secret.

Current state of the demo server: **no bootstrap keys exist yet** for any site,
so every site will show "Generate Bootstrap Key".

---

## 4. Install the User App on the device

Open **Downloads** in the dashboard sidebar (under *Actions*). It shows the
current version, the installer size, and a Download button, and always reflects
what is actually published on the server.

The direct link is:

```
https://homepot.cabera.com/downloads/homepot-agent-setup-0.3.0.exe
```

> Use the exact filename. `https://homepot.cabera.com/downloads` on its own
> returns **403** (directory listing is disabled), so the link cannot be
> shortened to the folder.

- Size: 128,108,327 bytes
- SHA512 matches `latest.yml` published with the release
- An `.msi` build of the same version is also staged at
  `https://homepot.cabera.com/downloads/homepot-agent-0.3.0.msi`

Run the installer, then launch the app. The packaged app is pre-pointed at
`https://homepot.cabera.com/api/v1`; no manual API configuration is needed.

Verify the device can reach the backend before enrolling:

```
curl https://homepot.cabera.com/api/v1/health
```

Expect HTTP `200`.

---

## 5. Enrol the device

In the User App setup wizard, supply:

- **Site ID** — from §3
- **Bootstrap Key** — from §3

The device self-enrols into the site. Once enrolled it appears in the dashboard
under **Devices**, and can be commanded from there.

To confirm enrolment server-side, open the site and check its device list, or
open **Devices**.

---

## 6. Troubleshooting

| Symptom | Cause / fix |
| --- | --- |
| "does not have Engineer access" on login | You used the **Engineer** tab. Use the **Client** tab (§1). |
| Sites list is empty | The account holds a tenant or site membership, which scopes it. Ask for the interim fleet visibility to be confirmed, or use an account with no memberships. |
| Bootstrap Key dialog shows "No bootstrap key configured" | Expected on a fresh site — click **Generate Bootstrap Key**. |
| Enrolment fails | Check the device reaches `https://homepot.cabera.com/api/v1/health`, and that the Site ID and bootstrap key were copied exactly. |
| Device does not appear after enrolling | The device list refreshes on load; reopen **Devices**. |

---

## 7. What a Technician can and cannot do

| Capability | Technician | Admin |
| --- | --- | --- |
| See all sites | ✅ | ✅ |
| See all devices | ✅ | ✅ |
| Generate / reveal a bootstrap key | ✅ | ✅ |
| Enrol devices, provision, command devices | ✅ | ✅ |
| Manage enrolment intents | ✅ | ✅ |
| Assign roles (`PUT /auth/users/{email}/role`) | ❌ 403 | ✅ |
| Tenant administration | ❌ 403 | ✅ |
| AI action approval / execution | ❌ scoped to owned sites | ✅ |

The AI action routes are deliberately **not** opened up, even for the fleet
visibility above: approving or executing an AI-proposed action stays restricted
to the sites the account belongs to.
