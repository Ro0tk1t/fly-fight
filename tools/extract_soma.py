#!/usr/bin/env python3
"""提取全脑实测胞体坐标 → soma-data.js（3D 全脑神经元活动面板）
来源：body-annotations.feather 的 somaLocation（nm）与 somaSide（L/R）。
"""
import base64
import json
from pathlib import Path

import numpy as np
import pyarrow.feather as pf

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = ROOT / "soma-data.js"
BRAIN = ROOT / "brain-data.js"

t = pf.read_table(
    DATA / "body-annotations.feather", memory_map=True,
    columns=["bodyId", "somaLocation", "somaSide"],
)
sl = t.column("somaLocation").to_pylist()
idx = [i for i, v in enumerate(sl) if v and len(v) == 3]
pts = np.asarray([sl[i] for i in idx], dtype=np.float64)
print(f"neurons total: {t.num_rows}, with measured soma: {len(idx)}")

SCALE = 4  # nm per stored unit; max coord 134531/4 < 65535 (uint16)
enc = np.round(pts / SCALE).astype(np.uint16)

side_col = t.column("somaSide").to_pylist()
side_map = {"L": 1, "R": 2, "M": 3}
sides = np.fromiter((side_map.get(side_col[i] or "", 0) for i in idx), dtype=np.uint8)

# 把 94 个仿真神经元映射到点云索引
brain_src = BRAIN.read_text()
brain = json.loads(brain_src.split("=", 1)[1].rsplit(";", 1)[0])
body_ids = t.column("bodyId").to_pylist()
pos_of = {int(body_ids[i]): k for k, i in enumerate(idx)}
core = [pos_of.get(int(n["id"]), -1) for n in brain["nodes"]]
n_core = sum(1 for c in core if c >= 0)
print(f"sim neurons mapped to soma positions: {n_core}/{len(core)}")

payload = {
    "provenance": {
        "source": "body-annotations.feather somaLocation/somaSide (MaleCNS)",
        "neurons_total": int(t.num_rows),
        "neurons_with_soma": len(idx),
        "scale_nm": SCALE,
        "sim_neurons_mapped": n_core,
    },
    "scale": SCALE,
    "positions": base64.b64encode(enc.tobytes()).decode(),
    "sides": base64.b64encode(sides.tobytes()).decode(),
    "core": core,
}
OUT.write_text("window.FLY_SOMA = " + json.dumps(payload, separators=(",", ":")) + ";\n")
print(f"wrote {OUT} ({OUT.stat().st_size/1e6:.2f} MB)")
