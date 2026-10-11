# Demo evidence images

`validation-repair.png`, `policy-repair.png`, and `rejected-proposal.png` are captures of the recorded replay from application commit `3220221`. They show the matching local build, not a new model generation.

`cost-comparison.svg` and its PNG export use the committed frozen final results and the separately labeled exploratory keep-warm ablation. The chart shows four of the seven frozen policies; the full comparison remains in `results/final.json`.

Regenerate the SVG from the repository root with Python's standard library:

```sh
python3 docs/render_cost_chart.py . docs/images
```

The generator checks scenario identities, completed jobs, late hours, productive work in the frozen comparison, and the cost arithmetic before writing the chart. The ablation record has no productive-work total; its checks use completed jobs, unfinished work, and scenario IDs.

The PNG is a static export of the SVG, retained for projector and offline use. Regenerating the SVG does not update the PNG.
