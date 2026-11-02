# PR #745 Fix List — Dealdio Device 001

**PR:** https://github.com/brunel-opensim/homepot-client/pull/745
**Device:** Dealdio Device 001 (SITE-TTD2-4CFB)
**Tester:** Gowtham Raj
**Date:** 2026-11-02
**Status:** Open — fixes in progress

---

## 1. Data discrepancy (needs clarification)

- [ ] **Device ID mismatch:** PR reports `DEVICE-BZ5F-G8ZJ-JRSX` but server shows `DEVICE-TJQW-MUUA-H62V` for Dealdio Site 1. Confirm which device was actually tested and update the test record.

## 2. Code fixes (backend agent)

### 2.1 Volume read-back tolerance ✅ DONE
- [x] **File:** `backend/src/homepot/agent/utils/command_poller.py` → `_set_windows_volume_ctypes()`
- [x] **Issue:** `verified = after_pct is not None and after_pct == pct and not is_muted_after` uses exact equality. Hardware rounding can produce 49 or 51 instead of 50.
- [x] **Fix:** Use tolerance-based comparison: `abs(after_pct - pct) <= 1` instead of `after_pct == pct`.
- [ ] **Tests:** Add unit test with mocked read-back values (49, 50, 51) to verify tolerance works.

### 2.2 Brightness 0/100 edge cases ✅ DONE
- [x] **File:** `backend/src/homepot/agent/utils/command_poller.py` → `_win_brightness()`
- [x] **Issue:** WMI `SetBrightness` may reject 0 or 100 on some panels (minimum often 1, maximum often 99).
- [x] **Fix:** Clamp WMI call to 1-99 range: `$wmiPct = [Math]::Max(1, [Math]::Min(99, $pct))`.
- [ ] **Tests:** Add unit test for brightness 0 and 100 edge cases.

### 2.3 Brightness verification trust ✅ ALREADY IMPLEMENTED
- [x] **File:** `backend/src/homepot/agent/utils/command_poller.py` → `_win_brightness()`
- [x] **Issue:** When WMI fallback is tried and succeeds, `verified = True` is set.
- [x] **Fix:** Already implemented — `if wmi_tried and wmi_succeeded: verified = True`.
- [ ] **Tests:** Add unit test for WMI success with mismatched read-back.

## 3. Test methodology (tester re-verification)

### 3.1 Direct Connect — echo hello
- [ ] **Test:** 3.1
- [ ] **Issue:** `echo hello` fails in PowerShell. "Hello" (capitalized) is not a valid command.
- [ ] **Fix:** Use `Write-Output "hello"` instead of `echo hello`.
- [ ] **Re-test:** Verify output shows "hello".

### 3.2 Direct Connect — elevation prompt
- [ ] **Test:** 3.4
- [ ] **Issue:** Prompt did not match elevation level.
- [ ] **Fix:** Verify elevation toggle state before testing. Toggle "Manage device" permission and re-test.
- [ ] **Re-test:** Confirm prompt shows `root@` when elevated, `user@` when not.

### 3.3 Direct Connect — command timeout
- [ ] **Test:** 3.5
- [ ] **Issue:** 300s timeout behaviour not as expected.
- [ ] **Fix:** Use a long-running command (e.g., `Start-Sleep -Seconds 310`) and verify it times out at 300s.
- [ ] **Re-test:** Confirm timeout works.

### 3.4 Compose Command — program management
- [ ] **Tests:** 4.5, 4.6, 4.7, 4.8
- [ ] **Issue:** Install/Uninstall/Update/Upgrade return exit code 0 but empty stdout/stderr.
- [ ] **Fix:** Verify winget is available (`winget --version`) and package names are correct (e.g., `Notepad++.Notepad++`).
- [ ] **Re-test:** Install a known package, verify it appears in installed programs list.

### 3.5 Apply Configuration — verification
- [ ] **Tests:** 2.1, 2.4
- [ ] **Issue:** Verification status not returning `true`.
- [ ] **Fix:** After code fix (2.1), re-test with volume 50/brightness 50.
- [ ] **Re-test:** Confirm `verified: true` in result.

### 3.6 Apply Configuration — brightness edge cases
- [ ] **Tests:** 2.7, 2.8
- [ ] **Issue:** Brightness 0 and 100 not setting screen dark/bright.
- [ ] **Fix:** After code fix (2.2), re-test with brightness 0 and 100. If still fails, document as hardware limitation.
- [ ] **Re-test:** Try brightness 1 and 99 as alternatives.

## 4. Documentation fixes

- [ ] Fix device ID in test record (see section 1).
- [ ] Update test result summary table after re-tests.
- [ ] Add "Known limitations" note for brightness 0/100 if hardware-dependent.

## 5. Frontend fixes (if needed)

- [ ] **Push History verification display:** If 2.4 is a frontend issue, check `DeviceHistory.jsx` / `PushReview.jsx` for verification object rendering.
- [ ] **Apply Configuration result display:** Ensure verification object (before/after/target/verified) is shown in command details.

---

## Priority

| Priority | Items | Owner |
|----------|-------|-------|
| P1 (code) | 2.1 (volume tolerance), 2.2 (brightness clamp) | Backend |
| P2 (code) | 2.3 (brightness trust), 5.1-5.2 (frontend) | Backend/Frontend |
| P3 (re-test) | 3.1-3.6 (tester re-verification) | Test engineer |
| P4 (docs) | 1, 4 (device ID, summary) | Test engineer |

## Related

- Brunel test (PR #744): All 8 Apply Config tests passed (including brightness 0/100) on different hardware.
- Ollama comprehension limitation documented in `docs/ai-llm-providers.md`.
