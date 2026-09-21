# Core-cast voice readiness

`ahos.voice_readiness` audits the canonical voice-enrollment matrix for all 16
recurring characters and every required release language. The default language
set is Turkish, German, Arabic, French, Spanish, and English.

Speech and early-speech characters require a rights-cleared, human-reviewed,
owner-approved canonical enrollment in every language. Infant-vocalization
characters are explicitly exempt from sentence-TTS enrollment and remain routed
to age-appropriate vocal effects.

The auditor is read-only. It never synthesizes a voice, grants approval, changes
an enrollment, calls a provider, or spends money. Its deterministic JSON report
lists every missing character/language pair and carries a reproducible hash.
