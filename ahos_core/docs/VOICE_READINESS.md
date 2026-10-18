# Core-cast voice readiness

`ahos.voice_readiness` audits the canonical voice-enrollment matrix for all 16
recurring characters and every required release language. The default language
set is Turkish, Kurdish (Kurmanji in the Latin script, normalized BCP 47 tag
`ku-latn`), German, Arabic, French, Spanish, and English.

Speech and early-speech characters require a rights-cleared, human-reviewed,
owner-approved canonical enrollment in every language. Infant-vocalization
characters are explicitly exempt from sentence-TTS enrollment and remain routed
to age-appropriate vocal effects.

Kurdish enrollment uses the verified OpenVoice V2 identity-transfer provider
with the same approved synthetic character reference. The other six production
languages use Chatterbox Multilingual. Provider selection remains
capability-checked and fails closed when a required provider is absent.

The auditor is read-only. It never synthesizes a voice, grants approval, changes
an enrollment, calls a provider, or spends money. Its deterministic JSON report
lists every missing character/language pair and carries a reproducible hash.
The canonical cast binder exports this report automatically after every binding,
so incomplete cast coverage cannot be mistaken for production readiness.
