# Privacy-safe floorplan renderer

The renderer creates Home Assistant-ready WebP overlays from OBJ room geometry.
The checked-in model is synthetic and contains no real home layout.

Run from the snapshot root with Blender:

```sh
blender -b -P floorplan/render_floorplan.py
```

Useful options:

```sh
blender -b -P floorplan/render_floorplan.py -- --floor DEMO --samples 8 --width 700
blender -b -P floorplan/render_floorplan.py -- --floor DEMO --mobile --width 700
```

Outputs are written under `floorplan/output/`, and overlay positions are
written to `floorplan/positions.json`.

To adapt the example, replace the synthetic OBJ and edit the clearly marked
`FLOORS`, `LIGHTS`, `ROOMS`, `STAIRS`, and `COVERS` data. Do not publish a real
floorplan, furniture layout, room measurements, or rendered images unless you
have deliberately decided that the privacy impact is acceptable.
