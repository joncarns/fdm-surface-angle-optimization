# FDM Surface Angle Optimization

An open-source, AI-assisted investigation into shallow-angle stair-stepping and a practical STL build orientation optimizer. Preliminary research, not a universal printing rule.

## Experimental observation

During development of a relocated camera bracket for the Flashforge Creator 5 Pro in November 2026, shallow upward-facing surfaces exhibited pronounced striping in sliced previews and roughness on a physical bracket. Calibration models covering 0–90 degrees in 10-degree steps and 0–20 degrees in 1-degree steps suggested a particularly undesirable band around 5–13 degrees with a 0.4 mm nozzle, 0.12 mm layer height and nominal 0.42 mm extrusion width.

Arachne, reduced wall count and ironing showed some improvement; finer tessellation, lower layer height and Z contouring did not substantially resolve the observed pattern. Orienting the bracket away from the undesirable band produced a much more uniform preview. Physical validation of the optimized orientation and independent replication remain pending.

## Mathematics

For an upward-facing unit face normal n and unit build-up vector u, inclination relative to the build plate is acos(n dot u). The horizontal terrace spacing for layer height h and nonzero inclination theta is h / tan(theta). At h = 0.12 mm and theta = 10 degrees, spacing is about 0.681 mm. The spacing is a geometric fact; the empirical bad-angle band is profile-dependent.

The optimizer sums actual triangle areas in the chosen upward-facing angle band. It samples directions on a Fibonacci sphere, adds cardinal directions, and refines the best candidates. The v0.2-compatible CLI ranks by bad area, buffered bad area, projected downward overhang area, then tilt. It applies a rigid rotation and translates the lowest point to Z=0.

## Desktop application (v0.3)

Download the repository as a ZIP, extract it, and install Python 3 (with Tk support). On Windows, double-click `launch_windows.bat` to create a virtual environment, install dependencies and launch the application. The first launch needs internet access for dependencies. Alternatively run:

```sh
python -m pip install -r requirements-gui.txt
python optimizer_gui.py
```

Open an STL or click **Demo block**, set the angle band, and click **Optimize**. Select a row to preview that orientation and export its STL and JSON report. Red faces are upward-facing triangles in the band. The reference plate shows Z = 0 and has no printer-specific dimensions. Rows list the exact-band area, buffered band area, projected overhang proxy, and build height. If several modes pick the same build direction, they share a row.

| Mode | Ranking |
|---|---|
| Surface quality | Minimize bad area, then buffered area, then the overhang proxy and height. |
| Balanced | Minimize bad area first, then trade off buffered area, overhang proxy and height equally. |
| Minimum supports proxy | Minimize projected downward overhang area. This choice can increase bad area. |
| Minimum height | Minimize the vertical distance between the lowest and highest points. This choice can increase bad area. |
| Custom | Minimize bad area first, then trade off buffered area, overhang proxy and height with your weights. |

For Balanced and Custom, both area metrics are divided by total mesh surface area and height by the original bounding-box diagonal. Custom weights are relative, allow zero, and require at least one positive value. Surface quality, Balanced and Custom preserve zero bad area whenever the search finds it. Narrow bands and results near a band edge may be sensitive to STL rounding. The export report remeasures all four metrics after reading back the saved STL.

The overhang proxy adds the horizontal projected area of downward faces past the configured overhang threshold. It can count bed-contact faces and overlapping projections. It estimates neither support grams nor print time. Confirm those measurements in the slicer with the same print profile when comparing builds.

## Quick start

Requires Python 3 and the dependencies in requirements.txt.

```sh
python -m pip install -r requirements.txt
python orientation_optimizer.py input.stl optimized.stl --low 5 --high 13
python -m unittest -v
```

The STL must be watertight with consistent outward winding and positive volume. Coordinates are assumed to be millimeters. Import the result without automatic reorientation. A JSON report is saved alongside it. Choose fresh output paths to avoid overwriting existing files.

## Initial validation

On the 61,370-triangle camera bracket mesh: 879.7551 mm² upward-facing area in the 5–13 degree band before optimization, 0 mm² after optimization and STL reimport. The exported mesh remained watertight. Three automated unit tests passed locally with NumPy 2.3.5 and trimesh 4.11.1.

The user's separate v0.2 Windows run reduced bad area from 68.403 to 0 mm². The result was 56.40 mm tall, with Flash Studio estimates of 3.64 g of support and 1 h 36 min at 0.10 mm layer height. These are historical benchmark values. The v0.3 regression tests use synthetic geometry. Seven unit tests and an automated Windows Tk smoke test passed with Python 3.12, NumPy 2.5.5, trimesh 4.12.2 and Matplotlib 3.11.2. The smoke test covered candidate selection, reference plate rendering and export. The Windows batch launcher, camera-bracket benchmark and physical prints still need v0.3 validation.

## Limitations

This is a sampled search, not proof of a global optimum. The downward projection metric is only a heuristic, not actual support volume. Bed adhesion, printer build volume, support contact, strength, time, cosmetic priority and assembly constraints still require manual review. No physical improvement is guaranteed. Curved surfaces are evaluated as STL triangles. The software does not repair invalid meshes. Calibration STL assets, slicer-aware support estimation and broader validation are planned.

## Contributing

Independent tests on different printers, filaments, line widths and layer heights are welcome. Record the slicer version, profile, angle band, preview and physical finish separately. Please avoid treating the preliminary 5–13 degree range as universal.

The goal is progress through freely accessible, reproducible experiments.
