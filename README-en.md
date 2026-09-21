# FLY-FIGHT — A Fruit Fly Connectome Fighting Arena

A fighting character driven by a **real fruit fly connectome**. Inspired by
[nftechie/doomfly](https://github.com/nftechie/doomfly): instead of scripted AI, a real
subgraph of the MaleCNS whole-brain atlas (94 neurons / 621 synapses) is wired into the game
as the "brain" — it receives arena stimuli frame by frame, produces actions, and persists
memory across learning rounds via dopamine-gated plasticity.

![UI](data/UI.png)

## Three modes

| Mode | Description |
|---|---|
| ① Fly vs Computer | The connectome fly fights a scripted bot |
| ② Fly vs Player | You fight the fly (it learns from being hit and evolves) |
| ③ Player vs Computer | Pure fighting, no neural simulation |

Best of 3. Includes blocking, guard break, hitstun, knockback, and jumping (Space).

## Controls

- Player 1 (left): `A` `D` move · `Space` jump · `J` attack · `K` block
- Player 2 (right): `←` `→` move · `↑` jump · `.` attack · `,` block
- In single-player modes (②) both key schemes work for the lone player · `Enter` start / back to menu

## Neural data pipeline (all from real MaleCNS files in `data/`, nothing fabricated)

```
data/annotations.feather   211,577 neuron annotations (incl. somaLocation soma coordinates)
data/transmitters.feather  neurotransmitter consensus (gaba/glycine → synapse sign flipped)
data/weights.feather       151,856,684 real synaptic edges
        │
        ├─ tools/extract_brain.py  → brain-data.js   94-neuron subgraph + 621 synapses (weights log-scaled by synapse count)
        └─ tools/extract_soma.py   → soma-data.js    3D point cloud of 141,781 measured somata (uint16+base64, 1.32MB)
```

Simulation loop: arena frame stimulus → real photoreceptors (R1-R6/R7y/R8y) → visual projection
neurons → Kenyon cells (KC) → MBONs (incl. MBON11 as block readout) → descending motor neurons
(DNp20 steering / DNpe017 attack / leg flexor MNs jumping).
Getting hit → PPL101 dopamine pulse → aversive-gated plasticity on real KC→MBON11 and motor-readout
synapses; landing a hit → reward pulse.
Memory is written to localStorage (`fly_fight_brain_v2_*`) and survives rounds and page reloads.

## Panels

- **Real connectome panel** (top right): activation heatmap of the 94 neurons;
  solid lines = real synapses, dashed = inferred reflex arcs, orange = plasticity-shaped.
- **Whole-brain 3D soma panel** (bottom): 141,781 measured somata rendered at their true
  coordinates, teal = left hemisphere / orange = right; drag to rotate, scroll to zoom.
  The 84 simulated neurons that have measured somata glow in real time with membrane activation.
  Coordinate axes (determined empirically from the data): x = medial-lateral, y = dorsal-ventral
  (ventral positive), z = anterior-posterior (posterior positive).
  Counting basis: 211,577 annotated rows → 166,700 neurons overall → 141,781 with soma
  coordinates (the often-cited 139,662 further excludes 2,119 rows lacking a superclass label).

## Running

```bash
python3 tools/get_malecns.py     # download the brain data
python3 tools/extract_brain.py   # requires pyarrow + pandas (generates brain-data.js on first run)
python3 tools/extract_soma.py    # generates soma-data.js on first run
# then simply open index.html in a browser

# or serve over HTTP:
python3 -m http.server 8888
# then visit http://localhost:8888
```

## Notes

Synaptic connectivity and weights come from real data; however, the sensory mapping
(arena → photoreceptors) and the action readouts (DNp20 → steering, etc.) are engineering
assignments — inferred proxies, exactly as in the original doomfly project. They do not
constitute scientific evidence of "learning to fight". Plasticity acts on real KC→MBON11
and related synapses and observable adaptive behavior emerges, but interpretation should
remain cautious. This project is unaffiliated with id Software, ZenMax, or nftechie.
