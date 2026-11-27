# FDM Surface Angle Optimization

An open-source, AI-assisted investigation into shallow-angle stair-stepping and a practical STL build orientation optimizer. Preliminary research, not a universal printing rule.

## Experimental observation

During development of a relocated camera bracket for the Flashforge Creator 5 Pro in November 2026, shallow upward-facing surfaces exhibited pronounced striping in sliced previews and roughness on a physical bracket. Calibration models covering 0–90 degrees in 10-degree steps and 0–20 degrees in 1-degree steps suggested a particularly undesirable band around 5–13 degrees with a 0.4 mm nozzle, 0.12 mm layer height and nominal 0.42 mm extrusion width.

Arachne, reduced wall count and ironing showed some improvement; finer tessellation, lower layer height and Z contouring did not substantially resolve the observed pattern. Orienting the bracket away from the undesirable band produced a much more uniform preview. Physical validation of the optimized orientation and independent replication remain pending.

## Mathematics

For an upward-facing unit face normal n and unit build-up vector u, inclination relative to the build plate is acos(n dot u). The horizontal terrace spacing for layer height h and nonzero inclination theta is h / tan(theta). At h = 0.12 mm and theta = 10 degrees, spacing is about 0.681 mm. The spacing is a geometric fact; the empirical bad-angle band is profile-dependent.

The optimizer sums actual triangle areas in the chosen upward-facing angle band. It samples directions on a Fibonacci sphere, adds cardinal directions, and refines the best candidates. It ranks by bad area, buffered bad area, projected downward overhang area, then tilt. It applies a rigid rotation and translates the lowest point to Z=0.

## Desktop application (v0.2)

Download the repository as a ZIP, extract it, and install Python 3 (with Tk support). On Windows, double-click `launch_windows.bat` to create a virtual environment, install dependencies and launch the application. The first launch needs internet access for dependencies. Alternatively run:

```sh
python -m pip install -r requirements-gui.txt
python optimizer_gui.py
```

Open an STL or click Demo block, select the undesirable angle band, click Optimize, orbit the two previews, and export a new STL and JSON report. Red faces are upward-facing triangles in the selected band; blue faces are outside it. The overhang projection is a heuristic, not a support-volume prediction. Review adhesion, supports and build volume in your slicer. The GUI demo and export were smoke-tested in a Linux virtual display; Windows launching has not been independently tested. No standalone executable is currently included.

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

## Limitations

This is a sampled search, not proof of a global optimum. The downward projection metric is only a heuristic, not actual support volume. Bed adhesion, printer build volume, support contact, strength, time, cosmetic priority and assembly constraints still require manual review. No physical improvement is guaranteed. Curved surfaces are evaluated as STL triangles. The software does not repair invalid meshes. Calibration STL assets, multiple candidate comparison, support-volume estimation and broader validation are planned.

## Contributing

Independent tests on different printers, filaments, line widths and layer heights are welcome. Record the slicer version, profile, angle band, preview and physical finish separately. Please avoid treating the preliminary 5–13 degree range as universal.

The goal is progress through freely accessible, reproducible experiments.
