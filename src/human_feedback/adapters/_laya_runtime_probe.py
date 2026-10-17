"""Fixed offline Laya load probe consumed only by the local Docker adapter."""

from __future__ import annotations

import json
from types import MappingProxyType

MODEL_ROOT = "/opt/laya-runtime/checkpoints/multilingual"
CHECKPOINT_DIGESTS = MappingProxyType(
    {
        "encoder/config.json": ("83f6916d13ef0f556ac461f28308dc2bffa7ebeadee8ec9e2db5812020ea5bb4"),
        "model.safetensors": ("9d628fd971b700382ac6f65920a86f149777b2e748e0c955fb3b19695aa8f204"),
        "rl_agent_config.json": (
            "25061739243b617ad88d1219ba6f8a9c86c5881ca28df024fa2d9b3b2fcc30c6"
        ),
        "tokenizer/tokenizer.json": (
            "609d8f4c067cd3950f88594c5a802616cea245823836ef5848ee4fc40aab5b6f"
        ),
        "tokenizer/tokenizer_config.json": (
            "6c6b2d8e3c84ce0e671c129cd6b374b235d6f9863042a5836358d00a89bbb5a1"
        ),
    }
)

_DIGEST_JSON = json.dumps(
    {"multilingual": dict(CHECKPOINT_DIGESTS)},
    ensure_ascii=True,
    allow_nan=False,
    sort_keys=True,
    separators=(",", ":"),
)
_EXTRA_MODELS_JSON = json.dumps(
    {"multilingual": MODEL_ROOT},
    ensure_ascii=True,
    allow_nan=False,
    sort_keys=True,
    separators=(",", ":"),
)

IMAGE_ENVIRONMENT = (
    "PATH=/opt/laya-runtime/.venv/bin:/usr/local/bin:/usr/local/sbin:/usr/local/bin:"
    "/usr/sbin:/usr/bin:/sbin:/bin",
    "LANG=C.UTF-8",
    "GPG_KEY=A035C8C19219BA821ECEA86B64E628F8D684696D",
    "PYTHON_VERSION=3.11.10",
    "PYTHON_SHA256=07a4356e912900e61a15cb0949a06c4a05012e213ecd6b4e84d0f67aabbee372",
    "UV_LINK_MODE=copy",
    "UV_PYTHON_DOWNLOADS=never",
    "UV_PROJECT_ENVIRONMENT=/opt/laya-runtime/.venv",
    "LAYA_DEVICE=cpu",
    "LAYA_PRELOAD=1",
    "LAYA_MODELS=multilingual",
    "LAYA_AUTO_TASK=0",
    "LAYA_DEFAULT_MODEL=multilingual",
    "LAYA_REVISION=55cf4c4ebb4ebe31b2550e8bdf3bd21b99753851",
    "HF_HUB_OFFLINE=1",
)

PROBE_ENVIRONMENT = (
    *IMAGE_ENVIRONMENT[:9],
    "LAYA_PRELOAD=0",
    "LAYA_MODELS=",
    "LAYA_AUTO_TASK=0",
    "LAYA_DEFAULT_MODEL=multilingual",
    "LAYA_REVISION=55cf4c4ebb4ebe31b2550e8bdf3bd21b99753851",
    "HF_HUB_OFFLINE=1",
    f"LAYA_EXTRA_MODELS={_EXTRA_MODELS_JSON}",
    f"LAYA_SHA256_DIGESTS={_DIGEST_JSON}",
    "HOME=/tmp",
    "HF_HOME=/tmp/huggingface",
    "XDG_CACHE_HOME=/tmp/cache",
    "TMPDIR=/tmp",
    "PYTHONDONTWRITEBYTECODE=1",
    "TOKENIZERS_PARALLELISM=false",
    "NUM_THREADS=2",
    "OMP_NUM_THREADS=2",
    "MKL_NUM_THREADS=2",
    "LAYA_THREADS=2",
)

_PROBE_PROGRAM = f"""
import hashlib
import importlib.metadata
import json
import os
import sys

root = {MODEL_ROOT!r}
expected = {dict(CHECKPOINT_DIGESTS)!r}

assert sys.version_info[:3] == (3, 11, 10)
assert importlib.metadata.version("laya") == "0.4.2"
assert os.environ["HF_HUB_OFFLINE"] == "1"
assert os.environ["LAYA_DEVICE"] == "cpu"
assert os.environ["NUM_THREADS"] == "2"
assert json.loads(os.environ["LAYA_EXTRA_MODELS"]) == {{"multilingual": root}}
assert json.loads(os.environ["LAYA_SHA256_DIGESTS"]) == {{"multilingual": expected}}

def digest(path):
    value = hashlib.sha256()
    with open(path, "rb") as source:
        while True:
            chunk = source.read(1024 * 1024)
            if not chunk:
                break
            value.update(chunk)
    return value.hexdigest()

before = {{name: digest(os.path.join(root, name)) for name in sorted(expected)}}
assert before == expected

from laya.serve import build_router

router = build_router()
agent = router.load("multilingual")
assert str(agent.device) == "cpu"
assert agent.model.training is False
assert all(parameter.device.type == "cpu" for parameter in agent.model.parameters())

after = {{name: digest(os.path.join(root, name)) for name in sorted(expected)}}
assert after == expected
print(json.dumps({{
    "device": "cpu",
    "laya": "0.4.2",
    "loaded": "multilingual",
    "model_eval": True,
    "python": "3.11.10",
    "schema_version": "laya-local-load-probe-v1"
}}, ensure_ascii=True, sort_keys=True, separators=(",", ":")))
""".strip()

PROBE_ARGUMENTS = ("-I", "-B", "-c", _PROBE_PROGRAM)
