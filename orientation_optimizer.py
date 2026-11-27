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


def search_inputs(mesh, low, high, margin, overhang, samples):
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
    return n, a


def sample_directions(samples):
    # Fibonacci sphere, plus the six cardinal axes. Directions are build-up vectors in input coordinates.
    i = np.arange(samples)
    z = 1 - 2*(i+.5)/samples
    phi = i*np.pi*(3-np.sqrt(5))
    r = np.sqrt(1-z*z)
    return np.vstack((np.column_stack((r*np.cos(phi), r*np.sin(phi), z)), np.eye(3), -np.eye(3)))


def nearby_directions(best, step):
    candidates = list(best)
    for u in best:
        axis = np.eye(3)[np.argmin(np.abs(u))]
        t = np.cross(u, axis)
        t /= np.linalg.norm(t)
        s = np.cross(u, t)
        for x in range(-2, 3):
            for y in range(-2, 3):
                v = u + np.tan(np.deg2rad(step*x))*t + np.tan(np.deg2rad(step*y))*s
                candidates.append(v/np.linalg.norm(v))
    return np.array(candidates)


def optimize(mesh, low=5., high=13., margin=0.5, overhang=45., samples=2048):
    n, a = search_inputs(mesh, low, high, margin, overhang, samples)
    directions = sample_directions(samples)
    def evaluate(v):
        m = metrics(n, a, v, low, high, margin, overhang)
        # Bad area first, margin second, projected overhang third, then minimum tilt.
        order = np.lexsort((-v[:,2], m[:,2], m[:,1], m[:,0]))
        return v[order[:4]], m[order[:4]]
    best, _ = evaluate(directions)
    for step in (3., 1., .25):
        best, _ = evaluate(nearby_directions(best, step))
    return orientation_result(mesh, best[0], n, a, low, high, margin, overhang, samples)


def orientation_result(mesh, u, n, a, low, high, margin, overhang, samples):
    transform = trimesh.geometry.align_vectors(u, [0,0,1])
    out = mesh.copy(); out.apply_transform(transform)
    out.apply_translation([0,0,-out.bounds[0,2]])
    before = metrics(n, a, [[0,0,1]], low, high, margin, overhang)[0]
    after = metrics(out.face_normals, out.area_faces, [[0,0,1]], low, high, margin, overhang)[0]
    def describe(m):
        return dict(bad_area_mm2=float(m[0]), buffered_bad_area_mm2=float(m[1]), downward_projection_proxy_mm2=float(m[2]))
    report = dict(angle_band_deg=[low,high], margin_deg=margin, overhang_angle_deg=overhang,
                  samples=samples, total_area_mm2=float(a.sum()), before=dict(describe(before), build_height_mm=float(mesh.extents[2])),
                  after=dict(describe(after), build_height_mm=float(out.extents[2])),
                  build_up_input=u.tolist(), rotation_matrix=transform[:3,:3].tolist(),
                  bounding_box_mm=out.extents.tolist())
    return out, report



def optimize_candidates(mesh, low=5., high=13., margin=.5, overhang=45.,
                        samples=2048, custom_weights=None):
    """Return distinct orientations with reports and the modes each won."""
    n, a = search_inputs(mesh, low, high, margin, overhang, samples)
    vertices = mesh.vertices
    height_scale = float(np.linalg.norm(mesh.extents))
    area_scale = float(a.sum())
    weights = None
    if custom_weights is not None:
        weights = np.asarray(custom_weights, dtype=float)
        if (weights.shape != (3,) or not np.isfinite(weights).all()
                or (weights < 0).any() or not weights.any()):
            raise ValueError('Enter three finite nonnegative weights, with at least one positive.')
        weights = weights / weights.max()
        weights /= weights.sum()

    def evaluate(directions):
        areas = metrics(n, a, directions, low, high, margin, overhang)
        heights = []
        for start in range(0, len(directions), 32):
            projections = vertices @ directions[start:start+32].T
            heights.extend(np.ptp(projections, axis=0))
        return np.column_stack((areas, heights))

    def orders(directions, scores):
        bad, buffered, support, height = scores.T
        tilt = -directions[:, 2]
        scaled = np.column_stack((buffered / area_scale, support / area_scale,
                                  height / height_scale))
        result = {
            'Surface quality': np.lexsort((tilt, height, support, buffered, bad)),
            'Balanced': np.lexsort((tilt, buffered, scaled.mean(axis=1), bad)),
            'Minimum supports proxy': np.lexsort((tilt, height, buffered, bad, support)),
            'Minimum height': np.lexsort((tilt, support, buffered, bad, height)),
        }
        if weights is not None:
            result['Custom'] = np.lexsort((tilt, buffered, scaled @ weights, bad))
        return result

    directions = sample_directions(samples)
    scores = evaluate(directions)
    for step in (3., 1., .25):
        pools = orders(directions, scores)
        seeds = np.unique(np.concatenate([order[:4] for order in pools.values()]))
        nearby = np.unique(nearby_directions(directions[seeds], step), axis=0)
        directions = np.vstack((directions, nearby))
        scores = np.vstack((scores, evaluate(nearby)))

    # Check the metrics in the rotated frame before ranking. Trigonometric
    # boundaries can shift by a few floating-point units after rotation.
    contenders = np.unique(np.concatenate([
        order[:12] for order in orders(directions, scores).values()
    ]))
    directions = directions[contenders]
    verified = []
    for direction in directions:
        rotation = trimesh.geometry.align_vectors(direction, [0, 0, 1])
        rotated = trimesh.transform_points(vertices, rotation)
        projected = metrics(n @ rotation[:3, :3].T, a, [[0, 0, 1]],
                            low, high, margin, overhang)[0]
        verified.append([*projected, np.ptp(rotated[:, 2])])

    candidates = {}
    for mode, order in orders(directions, np.asarray(verified)).items():
        direction = directions[order[0]]
        key = tuple(np.round(direction, 12))
        if key not in candidates:
            output, report = orientation_result(
                mesh, direction, n, a, low, high, margin, overhang, samples)
            report['candidate_modes'] = []
            if weights is not None:
                report['custom_weights'] = dict(zip(
                    ('buffered_bad_area', 'overhang_proxy', 'build_height'), weights.tolist()))
            candidates[key] = output, report
        candidates[key][1]['candidate_modes'].append(mode)
    return list(candidates.values())


def export_orientation(mesh, report, path):
    """Export the chosen orientation and measure the float32 STL after reimport."""
    path = Path(path)
    mesh.export(path)
    saved = trimesh.load(path, force='mesh')
    low, high = report['angle_band_deg']
    bad, buffered, support = metrics(saved.face_normals, saved.area_faces, [[0, 0, 1]],
                                    low, high, report['margin_deg'],
                                    report['overhang_angle_deg'])[0]
    result = dict(report, exported_watertight=bool(saved.is_watertight),
                  exported_bad_area_mm2=float(bad),
                  exported_buffered_bad_area_mm2=float(buffered),
                  exported_downward_projection_proxy_mm2=float(support),
                  exported_build_height_mm=float(saved.extents[2]))
    path.with_suffix('.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    return result


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
    report = export_orientation(out, report, args.output)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
