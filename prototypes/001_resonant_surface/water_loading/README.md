# Provisional water-loading study

This is the first step from the validated dry structure toward a coupled sculpture.
It adds configurable water inertia to the metal eigenproblem while retaining the
dry model as a separate baseline.

```bash
python tools/study_water_loading.py
python tools/study_water_loading.py --depths 0 0.01 0.03 0.065 --external-plate
python tools/plot_water_loading.py
```

Set `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1` before the study to limit numerical
thread use. The solver is offline; repeated audiovisual playback is a separate
workflow. The basic study requires NumPy, the optional flat-fluid check requires
NGSolve, and plotting requires Matplotlib.

Edit [config.py](config.py) for depth, density and integration settings. Depth is
measured **above the lowest point of the graph**, in metres. The asymmetric basin
minimum lies slightly below its centre. The water level is horizontal, and only
the submerged footprint receives loading. Overflow is rejected.

The default baseline is the existing `dry/profiles/contact_200hz.json`, including
its material, thickness, shape, supports and exciter masses. `--baseline path.json`
selects another dry configuration; `--density 998` overrides fluid density in kg/m³.
An edited profile must retain valid dry evidence or be supplied as an ordinary
exploratory configuration without a verification claim.

The tool writes `report.json`, `summary.md` and one portable mode archive per depth
into ignored `data/fem/001_resonant_surface/water_loading/`. Choose `--output` to
retain another study. The report distinguishes integration error, analytical
approximation error, independent flat-fluid validation and dry-cache agreement.
Sorted frequency ranks are compared; mode identities are not tracked across fills.

This is a shallow-column inertia approximation. It does not yet produce a water
wave field or hydrophone pressure, and it has no validated wet contact-response
band. Audio/Blender export remains on the dry model until a spatial fluid model
and water-specific response checks are added. The original artistic water scene
also remains a separate model.

[Research write-up and results](../../../docs/research/water_loading/study.md).
[Reference study](../../../studies/water/001_column_loading/README.md).
