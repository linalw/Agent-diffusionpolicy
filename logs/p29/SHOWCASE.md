# P29 high-res fruit showcase (2026-10-21)

The owner asked for clean images of the 8 generated fruit species (the recorded demo crops were
blurry). `scripts/29_fruit_showcase.py` loads the procedural fruit meshes directly in the Isaac
Sim scene (`fruit_sorting.fruits.author_fruit` + `FRUIT_SHAPES`, the per-species diameters from
`SceneConfig.fruit_dimensions`), arranges them, and renders with the RTX camera.

Artifacts (logs/p29/): fruit_apple.png ... fruit_tomato.png (320x320 per species),
fruit_showcase_wide.png (270x480), fruit_showcase_sheet.png (2200x5231, the 8 stacked).

Note: the rendering lane's session ended with a transport error ("Timed out waiting for response
headers") AFTER writing the images and the script; the script is on disk (33.7 KB) and the images
are verified non-blank (the mean/std stats in the hand-off). A higher-resolution re-render (1024+)
is a one-line parameter change if wanted.
