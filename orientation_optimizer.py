"""Area-weighted, sampled STL build orientation optimization (millimeters)."""
import argparse
import json
from pathlib import Path
import numpy as np
import trimesh


def metrics(normals, areas, directions, low=5., high=13., margin=0.5, overhang=45.):
    """Return actual bad area, buffered bad area, and downward projection proxy."""
    directions = np.atleast_2d(directions)
    result = []
    for start in range(0, len(directions), 32):
        d = normals @ directions[start:start+32].T
        def band(lo, hi):
            return ((d >= np.cos(np.deg2rad(hi))) &
                    (d <= np.cos(np.deg2rad(lo)))).T @ areas
        bad = band(low, high)
        buffered = band(max(0., low-margin), min(90., high+margin))
        downward = (np.where(d < -np.cos(np.deg2rad(overhang)), -d, 0.)).T @ areas
        result.extend(np.column_stack((bad, buffered, downward)))
    return np.array(result)


def optimize(mesh, low=5., high=13., margin=0.5, overhang=45., samples=2048):
    if not 0 < low < high < 90 or not 0 <= margin < low or not 0 < overhang < 90 or samples < 32:
        raise ValueError('Require 0 < low < high < 90, 0 <= margin < low, 0 < overhang < 90, samples >= 32.')
    if not mesh.is_watertight or not mesh.is_winding_consistent or mesh.volume <= 0:
        raise ValueError('Input must be a watertight, consistently outward-oriented positive-volume mesh.')
    a = mesh.area_faces
    n = mesh.face_normals
    keep = a > 1e-12
    a, n = a[keep], n[keep]
    if not len(a) or not np.all(np.isfinite(n)):
        raise ValueError('No valid faces.')
    # Fibonacci sphere, plus the six cardinal axes. Directions are build-up vectors in input coordinates.
    i = np.arange(samples)
    z = 1 - 2*(i+.5)/samples
    phi = i*np.pi*(3-np.sqrt(5))
    r = np.sqrt(1-z*z)
    directions = np.vstack((np.column_stack((r*np.cos(phi), r*np.sin(phi), z)), np.eye(3), -np.eye(3)))
    def evaluate(v):
        m = metrics(n, a, v, low, high, margin, overhang)
        # Bad area first, margin second, projected overhang third, then minimum tilt.
        order = np.lexsort((-v[:,2], m[:,2], m[:,1], m[:,0]))
        return v[order[:4]], m[order[:4]]
    best, scores = evaluate(directions)
    for step in (3., 1., .25):
        candidates = list(best)
        for u in best:
            axis = np.eye(3)[np.argmin(np.abs(u))]
            t = np.cross(u, axis); t /= np.linalg.norm(t)
            s = np.cross(u, t)
            for x in range(-2, 3):
                for y in range(-2, 3):
                    v = u + np.tan(np.deg2rad(step*x))*t + np.tan(np.deg2rad(step*y))*s
                    candidates.append(v/np.linalg.norm(v))
        best, scores = evaluate(np.array(candidates))
    u = best[0]
    transform = trimesh.geometry.align_vectors(u, [0,0,1])
    out = mesh.copy(); out.apply_transform(transform)
    out.apply_translation([0,0,-out.bounds[0,2]])
    before = metrics(n, a, [[0,0,1]], low, high, margin, overhang)[0]
    after = metrics(out.face_normals, out.area_faces, [[0,0,1]], low, high, margin, overhang)[0]
    def describe(m):
        return dict(bad_area_mm2=float(m[0]), buffered_bad_area_mm2=float(m[1]), downward_projection_proxy_mm2=float(m[2]))
    report = dict(angle_band_deg=[low,high], margin_deg=margin, overhang_angle_deg=overhang,
                  samples=samples, total_area_mm2=float(a.sum()), before=describe(before), after=describe(after),
                  build_up_input=u.tolist(), rotation_matrix=transform[:3,:3].tolist(),
                  bounding_box_mm=out.extents.tolist())
    return out, report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('input', type=Path); p.add_argument('output', type=Path)
    p.add_argument('--low', type=float, default=5.); p.add_argument('--high', type=float, default=13.)
    p.add_argument('--margin', type=float, default=.5); p.add_argument('--overhang', type=float, default=45.)
    p.add_argument('--samples', type=int, default=2048)
    args = p.parse_args()
    if args.input.resolve() == args.output.resolve(): p.error('Choose a different output path.')
    if args.input.suffix.lower() != '.stl' or args.output.suffix.lower() != '.stl': p.error('Use STL files.')
    mesh = trimesh.load(args.input, force='mesh')
    out, report = optimize(mesh, args.low, args.high, args.margin, args.overhang, args.samples)
    out.export(args.output)
    # Recheck exported mesh; STL stores float32 coordinates.
    saved = trimesh.load(args.output, force='mesh')
    report['exported_watertight'] = bool(saved.is_watertight)
    report['exported_bad_area_mm2'] = float(metrics(saved.face_normals, saved.area_faces, [[0,0,1]], args.low, args.high, args.margin, args.overhang)[0,0])
    args.output.with_suffix('.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
