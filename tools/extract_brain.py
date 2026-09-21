#!/usr/bin/env python3
"""Extract a compact, biologically-named connectome subgraph for FLY-FIGHT.

Reads MaleCNS-style feather files and emits brain-data.js (const FLY_BRAIN = ...).
Selection mirrors the doomfly interface: photoreceptors -> visual projection
neurons -> Kenyon cells -> MBONs (incl. MBON11) -> DNp20 / DNpe017 descending
neurons, with PPL101 dopamine cells as modulatory nodes.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.feather as feather

DATA = Path(__file__).resolve().parents[1] / "data"
OUT = Path(__file__).resolve().parents[1] / "brain-data.js"

ann = feather.read_table(
    DATA / "annotations.feather",
    columns=["bodyId", "hemibrainType", "type", "somaSide", "superclass"],
).to_pandas()
ntt = feather.read_table(
    DATA / "transmitters.feather", columns=["body", "consensus_nt"]
).to_pandas().drop_duplicates("body").set_index("body")["consensus_nt"]

ann["ht"] = ann["hemibrainType"].astype(str)
ann["ty"] = ann["type"].astype(str)

def head_by_type(mask, n_per_type, total):
    sub = ann[mask].sort_values("bodyId")
    sub = sub.groupby("ty", sort=False).head(n_per_type)
    return sub.head(total)

sel = []
# photoreceptors: R1-R6 brightness proxies + R7/R8 color proxies
for pat, n in [("R1-R6", 4), ("R7y", 2), ("R8y", 2)]:
    sel += head_by_type(ann["ty"].str.fullmatch(pat), 99, n).to_dict("records")
# visual projection / lobula column neurons, one per named type
vt = ["LC12", "TmY14", "LLPC1", "LC10a", "LC17", "LC9", "MeTu1", "LPC1"]
for t in vt:
    r = ann[ann["ty"] == t].sort_values("bodyId").head(1)
    sel += r.to_dict("records")
# Kenyon cells: diverse types
kc = ann[ann["ht"].str.match(r"^KC")].sort_values(["ty", "bodyId"]).groupby("ty").head(4)
sel += kc.head(24).to_dict("records")
# MBONs: both MBON11 plus one of each other named MBON type
mb11 = ann[ann["ht"] == "MBON11"]
mb_other = ann[ann["ht"].str.match(r"^MBON\d") & (ann["ht"] != "MBON11")] \
    .sort_values("bodyId").groupby("ht").head(1)
sel += mb11.to_dict("records") + mb_other.head(14).to_dict("records")
# PPL101 dopamine pair (the doomfly aversive-input target)
sel += ann[ann["ht"] == "PPL101"].to_dict("records")
# motor interface: DNp20 pair (turn), DNpe017 pair (move/fire), leg MNs (jump)
sel += ann[ann["ty"] == "DNp20"].to_dict("records")
sel += ann[ann["type"].astype(str) == "DNpe017"].to_dict("records")
for t in ["Ti flexor MN", "Tr flexor MN"]:
    sel += ann[ann["ty"] == t].sort_values("bodyId").head(1).to_dict("records")

seen, nodes = set(), []
for r in sel:
    if r["bodyId"] in seen:
        continue
    seen.add(r["bodyId"])
    ht, ty = str(r["ht"]), str(r["ty"])
    if ty.startswith("R1") or ty.startswith("R7") or ty.startswith("R8"):
        role = "sensory"
    elif ty in vt:
        role = "visual"
    elif ht.startswith("KC"):
        role = "kc"
    elif ht.startswith("MBON"):
        role = "mbon"
    elif ht == "PPL101":
        role = "dopa"
    else:
        role = "motor"
    name = ht if ht not in ("None", "nan", "") and not ht.startswith("hb") else ty
    nodes.append({
        "id": int(r["bodyId"]),
        "name": name,
        "role": role,
        "side": str(r["somaSide"]) if pd.notna(r["somaSide"]) else "",
        "nt": str(ntt.get(int(r["bodyId"]), "unknown")),
    })
ids = sorted(n["id"] for n in nodes)
print(f"selected {len(nodes)} neurons, {len(ids)} unique ids")

# --- load full edge table once ---
w = feather.read_table(DATA / "weights.feather", memory_map=True)
ann_idx = ann.set_index("bodyId")

def partners(ids_in, side, other_side, limit):
    """Top-weight partners of `ids_in` on `side` ('pre'->find postsynaptic)."""
    idset = pa.array(ids_in)
    col = "body_pre" if side == "pre" else "body_post"
    oth = "body_post" if side == "pre" else "body_pre"
    m = pc.is_in(w[col], value_set=idset)
    rows = w.filter(m).to_pandas()
    g = rows.groupby(oth)["weight"].sum().sort_values(ascending=False)
    out = []
    for bid, wsum in g.items():
        bid = int(bid)
        if bid in {n["id"] for n in nodes} or bid not in ann_idx.index:
            continue
        a = ann_idx.loc[bid]
        out.append({"id": bid, "w": float(wsum), "rec": a})
        if len(out) >= limit:
            break
    return out

def add_bridge(cands, role, cap):
    added = 0
    for c in cands:
        a, bid = c["rec"], c["id"]
        ht = str(a["hemibrainType"]); ty = str(a["type"])
        if ht.startswith("KC") or ht.startswith("MBON") or ht == "PPL101":
            continue
        name = ht if ht not in ("None", "nan", "") and not ht.startswith("hb") else ty
        nodes.append({"id": bid, "name": name, "role": role,
                      "side": str(a["somaSide"]) if pd.notna(a["somaSide"]) else "",
                      "nt": str(ntt.get(bid, "unknown"))})
        added += 1
        if added >= cap:
            break
    return added

core_ids = {n["id"] for n in nodes}
kc_ids = [n["id"] for n in nodes if n["role"] == "kc"]
sen_ids = [n["id"] for n in nodes if n["role"] == "sensory"]
mbon_ids = [n["id"] for n in nodes if n["role"] == "mbon"]
mot_ids = [n["id"] for n in nodes if n["role"] == "motor"]

# bridge A: presynaptic partners of KCs (visual/projection neurons)
add_bridge(partners(kc_ids, "post", "pre", 60), "visual", 10)
# bridge B: postsynaptic partners of photoreceptors (L1/L2/L3/Tm...)
add_bridge(partners(sen_ids, "pre", "post", 40), "visual", 8)
# bridge C: MBON -> X -> descending/motor command chain
mbon_post = partners(mbon_ids, "pre", "post", 80)
mot_pre = {p["id"]: p for p in partners(mot_ids, "post", "pre", 80)}
chain = [p for p in mbon_post if p["id"] in mot_pre]
add_bridge(chain, "command", 8)
add_bridge([p for p in mbon_post if p["id"] not in mot_pre], "command", 6)
add_bridge(list(mot_pre.values()), "command", 6)

ids = sorted(n["id"] for n in nodes)
print(f"expanded to {len(nodes)} neurons")

# --- filter the 152M-edge weight table down to the subgraph ---
idset = pa.array(ids)
mask = pc.and_(
    pc.is_in(w["body_pre"], value_set=idset),
    pc.is_in(w["body_post"], value_set=idset),
)
sub = w.filter(mask).to_pandas()
print(f"raw subgraph rows: {len(sub)}")
agg = sub.groupby(["body_pre", "body_post"], as_index=False)["weight"].sum()
agg = agg[agg["body_pre"] != agg["body_post"]]

wmax = float(np.log1p(agg["weight"].max())) if len(agg) else 1.0
role_of = {n["id"]: n["role"] for n in nodes}
nt_of = {n["id"]: n["nt"] for n in nodes}
INHIB = {"gaba", "glycine"}
edges = []
for r in agg.itertuples():
    pre, post, raw = int(r.body_pre), int(r.body_post), int(r.weight)
    if role_of[pre] == role_of[post] == "kc":
        continue  # keep KC-KC noise out of the tiny panel graph
    sign = -1.0 if nt_of[post] in INHIB else 1.0
    wn = round(sign * (0.25 + 1.75 * np.log1p(raw) / wmax), 3)
    edges.append({"pre": pre, "post": post, "w": float(wn), "n": raw})

# layer coverage report
pairs = pd.Series([f"{role_of[e['pre']]}->{role_of[e['post']]}" for e in edges]).value_counts()
print(pairs.to_string())

payload = {
    "provenance": {
        "source": "weights.feather (MaleCNS-style)",
        "total_edges_scanned": int(w.num_rows),
        "subgraph_edges": len(edges),
        "neurons": len(nodes),
    },
    "nodes": nodes,
    "edges": edges,
}
OUT.write_text("window.FLY_BRAIN = " + json.dumps(payload, separators=(",", ":")) + ";\n")
print(f"wrote {OUT} ({OUT.stat().st_size/1024:.0f} KB)")
