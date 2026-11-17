# Shareable robot demo

An original geometric robot, drawn by `scripts/demo_assets.py` without external images, models, fonts or character references. The three encoded files are intentionally small. Every runtime state uses the same placeholder robot animation; these are not the private Neris-A character assets.

The project contributors permit anyone to use, copy, modify and redistribute these demo media and their modified versions, for any purpose, without a fee or attribution requirement. This permission applies only to `demo/robot.png`, `demo/robot.webp` and `demo/robot.mp4`. First-party source elsewhere in the repository is separately licensed under GPL-3.0-only.

Install into an otherwise asset-free checkout:

```bash
python3 -B scripts/demo_assets.py
python3 -B scripts/assets_manifest.py
bash body/start.sh
```

The installer refuses to replace existing private media. Repeating an installation of matching demo files is safe. Runtime copies remain ignored by Git. Regenerate the bundled demo with `python3 -B scripts/demo_assets.py --build` (requires ffmpeg with libx264 support), then review the changed files and demo manifest.
