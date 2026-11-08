# AHOS — Evidence-led reality audit, 5 November 2026

Generated UTC: 2026-11-05T20:19:26.514375+00:00

## Sources and scope

- Read-only SQLite: runtime/company-service.db, missions.status / last_error.
- Employee roster: config/roster.json. Mind summaries: config/development-ledger.json.
- This snapshot does not establish independent QA delivery.

## Queue state (snapshot)

| Status | Count |
|---|---:|
| completed | 3718 |
| pending | 940 |
| blocked | 37 |
| failed | 13 |
| cancelled | 299 |

- Roster: 81 employees.
- Mind ledger: 84 minds; plan-scored minds at last snapshot: 1.
- Taskboard valid tasks-list: True; records at snapshot: 27.

## Verified findings and limits

- The blocked queue was affected by a shared malformed taskboard, two bytes containing {}.
- Migration to version-1 tasks-list schema was performed under OS lock with a raw backup.
- Prior mass-unlock script overwrote mission status without independent verification; now restricted to safe preview/stale locks.
- Repeated same-cause crisis mission generation is now deduplicated while an unresolved mission exists.
- Mission scoring is now fed from queue results; reflection preserves score state; scripted messages do not count as success.
- Agent conversation now uses observed department mission data. This is not autonomous LLM reasoning.
- ComfyUI 127.0.0.1:8188 was unreachable; cartoon rendering is unverified.
- 3D UI is visualization, not a game engine or proof of completed work.
- GitHub heartbeat cron is configured for 30 minutes, but hosted runner does not access the local Windows SQLite runtime.
- No evidence supports consciousness, unrestricted abilities, or 24/7 local execution while PC is off.

## Blocked groups

| Type | Rows |
|---|---:|
| Deterministic edit | 3 |
| Repeated crisis | 20 |
| Research | 2 |
| Sandbox | 12 |

## Individually audited blocked rows

| ID | Department | Type | Last error |
|---|---|---|---|
| CMD-ai-platform-crisis-1793538772 | ai-platform | Repeated crisis | görev panosu biçimi geçersiz; mevcut veriler korunuyor |
| CMD-ai-platform-crisis-1793539502 | ai-platform | Repeated crisis | görev panosu biçimi geçersiz; mevcut veriler korunuyor |
| CMD-ai-platform-crisis-1793539619 | ai-platform | Repeated crisis | görev panosu biçimi geçersiz; mevcut veriler korunuyor |
| CMD-ai-platform-crisis-1793539953 | ai-platform | Repeated crisis | görev panosu biçimi geçersiz; mevcut veriler korunuyor |
| CMD-ai-platform-crisis-1793540070 | ai-platform | Repeated crisis | görev panosu biçimi geçersiz; mevcut veriler korunuyor |
| CMD-ai-platform-crisis-1793540767 | ai-platform | Repeated crisis | görev panosu biçimi geçersiz; mevcut veriler korunuyor |
| CMD-ai-platform-crisis-1793541458 | ai-platform | Repeated crisis | görev panosu biçimi geçersiz; mevcut veriler korunuyor |
| CMD-ai-platform-crisis-1793541541 | ai-platform | Repeated crisis | görev panosu biçimi geçersiz; mevcut veriler korunuyor |
| CMD-ai-platform-crisis-1793541634 | ai-platform | Repeated crisis | görev panosu biçimi geçersiz; mevcut veriler korunuyor |
| CMD-ai-platform-crisis-1793542326 | ai-platform | Repeated crisis | görev panosu biçimi geçersiz; mevcut veriler korunuyor |
| CMD-ai-platform-sandbox-1793538772 | ai-platform | Sandbox | görev panosu biçimi geçersiz; mevcut veriler korunuyor |
| CMD-creative-crisis-1793538772 | creative | Repeated crisis | görev panosu biçimi geçersiz; mevcut veriler korunuyor |
| CMD-creative-crisis-1793539502 | creative | Repeated crisis | görev panosu biçimi geçersiz; mevcut veriler korunuyor |
| CMD-creative-crisis-1793539619 | creative | Repeated crisis | görev panosu biçimi geçersiz; mevcut veriler korunuyor |
| CMD-creative-crisis-1793539953 | creative | Repeated crisis | görev panosu biçimi geçersiz; mevcut veriler korunuyor |
| CMD-creative-crisis-1793540070 | creative | Repeated crisis | görev panosu biçimi geçersiz; mevcut veriler korunuyor |
| CMD-creative-crisis-1793540767 | creative | Repeated crisis | görev panosu biçimi geçersiz; mevcut veriler korunuyor |
| CMD-creative-crisis-1793541458 | creative | Repeated crisis | görev panosu biçimi geçersiz; mevcut veriler korunuyor |
| CMD-creative-crisis-1793541541 | creative | Repeated crisis | görev panosu biçimi geçersiz; mevcut veriler korunuyor |
| CMD-creative-crisis-1793541634 | creative | Repeated crisis | görev panosu biçimi geçersiz; mevcut veriler korunuyor |
| CMD-creative-crisis-1793542326 | creative | Repeated crisis | görev panosu biçimi geçersiz; mevcut veriler korunuyor |
| CMD-creative-sandbox-1793538772 | creative | Sandbox | görev panosu biçimi geçersiz; mevcut veriler korunuyor |
| CMD-data-sandbox-1793538772 | data | Sandbox | görev panosu biçimi geçersiz; mevcut veriler korunuyor |
| CMD-finance-sandbox-1793538772 | finance | Sandbox | görev panosu biçimi geçersiz; mevcut veriler korunuyor |
| CMD-genel-sandbox-1793538772 | genel | Sandbox | görev panosu biçimi geçersiz; mevcut veriler korunuyor |
| CMD-guvenlik-sandbox-1793538772 | guvenlik | Sandbox | görev panosu biçimi geçersiz; mevcut veriler korunuyor |
| CMD-holding-sandbox-1793538772 | holding | Sandbox | görev panosu biçimi geçersiz; mevcut veriler korunuyor |
| CMD-infrastructure-sandbox-1793538772 | infrastructure | Sandbox | görev panosu biçimi geçersiz; mevcut veriler korunuyor |
| CMD-marketing-sandbox-1793538772 | marketing | Sandbox | görev panosu biçimi geçersiz; mevcut veriler korunuyor |
| CMD-operations-sandbox-1793538772 | operations | Sandbox | görev panosu biçimi geçersiz; mevcut veriler korunuyor |
| CMD-oyun-sandbox-1793538772 | oyun | Sandbox | görev panosu biçimi geçersiz; mevcut veriler korunuyor |
| CMD-quality-sandbox-1793538772 | quality | Sandbox | görev panosu biçimi geçersiz; mevcut veriler korunuyor |
| CMD-sales-arge-1793538771 | sales | Research | görev panosu biçimi geçersiz; mevcut veriler korunuyor |
| CMD-sales-arge-1793543016 | sales | Research | görev panosu biçimi geçersiz; mevcut veriler korunuyor |
| CMD-software-ahos-ideas-py-dosyasinin-sonuna--0b0727b7980a | software | Deterministic edit | görev panosu biçimi geçersiz; mevcut veriler korunuyor |
| CMD-software-ahos-ideas-py-dosyasinin-sonuna--448d459e154d | software | Deterministic edit | görev panosu biçimi geçersiz; mevcut veriler korunuyor |
| CMD-software-ahos-ideas-py-dosyasinin-sonuna--f024e5a9d363 | software | Deterministic edit | görev panosu biçimi geçersiz; mevcut veriler korunuyor |

## Acceptance gates still needed

1. Verify schema remains valid across repeated live queue and scheduled runs.
2. Require independent QA before changing any blocked mission to completed.
3. Observe plan scoring in production and compare actual counts with roster.
4. Connect persistent cloud runtime before claiming offline operations.
5. Execute and independently validate a real ComfyUI render before claiming video output.

## Ownership identity follow-up

- Local runtime/minds/_pledge.json was inspected and reports owner harun; the system environment AHOS_OWNER was unset during audit.
- Previous source default in sovereign.py was esmak, inconsistent with the persisted pledge. The default has been aligned to harun.
- The existing pledge uses an unkeyed SHA-256 checksum. This is not cryptographic authorization; a local actor could forge a new payload and hash. Full protection requires authenticated API access and secrets kept outside the repository.
- A malformed existing pledge is no longer silently replaced during ensure(); the original bytes are preserved and the operation fails closed.
