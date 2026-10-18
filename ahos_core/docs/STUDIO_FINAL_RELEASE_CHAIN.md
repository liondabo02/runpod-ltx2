# Studio Final Release Chain

The final studio chain is now explicit and fail-closed:

1. `StudioExecutor` completes render, seven-language TTS, mix, assembly and
   delivery-QA stages.
2. `EpisodeDeliveryGate` verifies the professional seven-language release
   candidate (`tr, ku-latn, de, ar, fr, es, en`).
3. `StudioReleaseOrchestrator` verifies the completed execution ledger,
   delivery evidence, and a hash-bound final owner release decision.
4. `ReleaseManifestBuilder` binds final assets and all acceptance hashes into
   a content-addressed manifest.
5. An external secret may HMAC-sign the manifest in memory. No signing secret is
   stored in the repository.
6. Publishing remains a separate owner-authorized action.

This closes the software/orchestration gap around STUDIO-007/STUDIO-008. It
does **not** fabricate the still-required real render, real seven-language audio,
human listening/identity acceptance, or final owner approval.
