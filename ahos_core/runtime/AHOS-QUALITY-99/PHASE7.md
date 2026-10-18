# AHOS-QUALITY-99 Phase 7

Branch: `program/AHOS-QUALITY-99-phase7-chatgpt`

## Q99-025 — Real zero-cost studio rehearsal

Executed on the isolated AHOS-QUALITY-99 worktree:

`python -m ahos.production_rehearsal --output <isolated-runtime>`

Observed:
- episode: S01E001
- status: awaiting_owner_story_approval
- duration: exactly 480 seconds
- canonical cast: 16
- scenes: 5
- shots/render jobs: 10
- dialogue lines: 43
- localization units: 301
- languages: 7
- external paid/network/publish calls: none
- release_ready: false

Evidence hashes:
- story: 24e5ef1aa7da472cabc5f8b24d2d803d63e0d2bf314dd8ac358fc650e550c487
- production graph: 4ca3a679a0653a63ef18b2a3505227a69901eda6b663b669f6f4f11995d2260c
- rehearsal evidence: f92cd3ab400e7d429fbe595df17fc6b8f4da31f9072cc65ffe13b9f8cad674ab

The product is deliberately NOT promoted because the real blockers are:
- owner story approval
- approved recurring-character reference images
- approved canonical voice enrollments
- human-reviewed localization
- explicitly owner-approved render/TTS execution
- rendered media and final professional QA

A second `ahos.studio_readiness` run confirmed source capability evidence is
100/100, while actual episode release readiness remains false. Code coverage is
there; real product evidence is not.

## Android recheck

`adb devices -l` again returned zero connected devices. Android remains
unproven and no success is claimed.

## DeepSeek free-route attempt

OpenRouter currently documents `deepseek/deepseek-v4-flash-0731:free` as a
free endpoint. A single bounded reviewer attempt was made using the already
configured OpenRouter key without exposing it. It did not return within the
bounded execution window and was terminated. No paid fallback was attempted.

Model-routing remains PARTIAL.


## Live DeepSeek catalog verification

A no-cost metadata request to `https://openrouter.ai/api/v1/models` returned
HTTP 200. The exact web-documented
`deepseek/deepseek-v4-flash-0731:free` ID was not present in that live API
catalog.

Every DeepSeek route returned by the live catalog had a positive prompt and/or
completion price. Under AHOS-QUALITY-99's hard 0 USD API rule, those routes are
not eligible and no paid fallback will be attempted.

Therefore Q99-BLOCKER-004 is now classified as
`waiting_for_verified_zero_cost_deepseek_route`, not as an implementation
success.
