# Professional media assembly

`ProfessionalMediaAssembler` turns a release package that has already passed
planning QA into a real Matroska (`.mkv`) master. It executes local `ffmpeg` and
`ffprobe`; it does not call RunPod, publish media, or spend money.

The assembler fails closed unless every source file exists and its SHA-256
matches the release manifest. It requires exactly one final mix and subtitle
track for every requested language, preserves graph shot order, records stream
language metadata, probes the finished master, checks duration and stream
counts, and returns content-addressed assembly evidence.

FFmpeg 6 or newer is recommended. Publishing and paid rendering remain separate
owner-approved actions.
