#!/usr/bin/env python3
import json
import shutil
import sys
from pathlib import Path

ROOT = Path('/opt/ltx2')
WORKFLOWS = ROOT / 'workflows'
sys.path.insert(0, str(ROOT))

from api.handler import _convert_ui_workflow_to_api_prompt  # noqa: E402

STEMS = ('image_to_video', 'cinematic_i2v')


def patch_runtime_compat(prompt: dict) -> dict:
    for node in prompt.values():
        if not isinstance(node, dict):
            continue
        if node.get('class_type') == 'LTXVGemmaCLIPModelLoader':
            node['class_type'] = 'LTXAVTextEncoderLoader'
            node['inputs'] = {
                'text_encoder': 'gemma_text_encoder.safetensors',
                'ckpt_name': 'ltx-2-19b-distilled.safetensors',
                'device': 'default',
            }
            node.setdefault('_meta', {})['title'] = 'Native LTX AV Text Encoder'
    return prompt


def main() -> None:
    for stem in STEMS:
        ui_path = WORKFLOWS / f'{stem}.json'
        api_path = WORKFLOWS / f'{stem}.api.json'
        if not ui_path.exists():
            raise SystemExit(f'missing UI workflow: {ui_path}')

        ui = json.loads(ui_path.read_text())
        if not isinstance(ui, dict) or not isinstance(ui.get('nodes'), list):
            raise SystemExit(f'{ui_path} is not a ComfyUI UI workflow')

        prompt = _convert_ui_workflow_to_api_prompt(ui)
        if not isinstance(prompt, dict) or not prompt:
            raise SystemExit(f'conversion produced an empty prompt for {ui_path}')

        prompt = patch_runtime_compat(prompt)
        encoded = json.dumps(prompt, indent=2, sort_keys=True) + '\n'
        api_path.write_text(encoded)

        # Runtime aliases are deliberately API-format prompts. The original UI
        # workflow is only needed during the image build, so replacing it here
        # prevents runtime reconversion drift.
        ui_path.write_text(encoded)
        print(f'{stem}: generated {len(prompt)} runtime nodes')


if __name__ == '__main__':
    main()
