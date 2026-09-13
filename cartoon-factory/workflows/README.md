# Character T2I workflow

The RunPod character worker expects a ComfyUI API-format text-to-image workflow at:

`/app/workflows/character_t2i.api.json`

Required conventions:

- Positive CLIP text node `_meta.title` contains `positive` or `prompt`.
- Negative CLIP text node `_meta.title` contains `negative`.
- Sampler exposes `seed` or `noise_seed`.
- Workflow ends in `SaveImage` or another node that returns an image in ComfyUI history.
- Output should be 1024x1024 PNG, preferably with a plain/transparent background.

Recommended production model class: FLUX/SDXL-class image generator with an approved reference-image consistency path (IP-Adapter / PuLID / equivalent) for subsequent views and poses.

Do not deploy the character worker until this file has been exported from the exact ComfyUI installation that will run on the worker and saved as `character_t2i.api.json`.
