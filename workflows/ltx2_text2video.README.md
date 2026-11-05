# AHOS örnek API grafı

Bu şablon istenen CheckpointLoaderSimple → CLIPTextEncode → KSampler → VAEDecode → SaveImage örneğidir. Gerçek LTX2 video grafı değildir. `frames` görüntü batch sayısıdır; varsayılan 1. `model.safetensors` yerel, uyumlu checkpoint adıyla değiştirilmelidir. Video için kurulu LTX2 düğümleri/modeliyle doğrulanmış ayrı graf gerekir. Bu paket GPU işi başlatmaz.
