from itertools import chain, product
from itertools import repeat as _repeat
from math import atan2 as _atan2
from math import cos as _cos
from math import hypot as _hypot
from math import pi
from math import sin as _sin

from numpy import arctan2, nonzero, repeat, reshape, transpose
from numpy import array as _array
from numpy import sqrt as nsqrt

from matrixmath import Vector


class Feature:
    """Unmatched feature, probably in print coordinates.

    A feature is derived from a trio of points/blobs forming two line segments:

      2.
      *
      |   3.
      |  *
    A | /
      |/ B
      *
      1.

    A is the longest side of the triangle.
    B is the second-longest side by convention.

    Ratio is B/A and must be <= 1.0.
    Theta is from B to A and can be positive or negative.

    Features are scale and rotation invariant, though this function
    considers the largest ones first to spend less time on image noise.
    """

    def __init__(self, pa, pb, pc):
        self.p1, self.p2, self.p3, self.ratio, self.theta = _normalize(pa, pb, pc)


class MatchedFeature:
    """Matched feature, with print coordinates like Feature plus raw scan coordinates."""

    def __init__(self, feature, s1, s2, s3):
        self.p1 = feature.p1
        self.p2 = feature.p2
        self.p3 = feature.p3

        self.ratio, self.theta = feature.ratio, feature.theta

        self.s1 = s1
        self.s2 = s2
        self.s3 = s3

    def fits(self, other):
        """Return false if this feature conflicts with another.

        Two features fit if their numbered points match pairwise, with
        the identity relationship between self.pn and other.pn being equal
        to that of self.sn and other.sn. Though not an interesting case,
        two features fit even if they have no points in common because
        there is no conflict.

        Assume that vertices can be simply compared with "is" and "is not".
        """
        for i, j in product((1, 2, 3), (1, 2, 3)):
            self_p, other_p = getattr(self, 'p%d' % i), getattr(other, 'p%d' % j)
            self_s, other_s = getattr(self, 's%d' % i), getattr(other, 's%d' % j)

            if self_p is other_p and self_s is not other_s:
                return False

            elif self_p is not other_p and self_s is other_s:
                return False

        return True


def _normalize(p1, p2, p3):
    """Return feature parts for a trio of points - re-ordered points, ratio, theta."""
    h12 = _hypot(p2.x - p1.x, p2.y - p1.y)
    h13 = _hypot(p3.x - p1.x, p3.y - p1.y)
    h23 = _hypot(p3.x - p2.x, p3.y - p2.y)

    hs = sorted([h12, h13, h23], reverse=True)

    #
    # Shuffle the points into correct order.
    #
    if hs[0] is h12:
        if hs[1] is h13:
            p1, p2, p3 = p1, p2, p3
        elif hs[1] is h23:
            p1, p2, p3 = p2, p1, p3
    elif hs[0] is h13:
        if hs[1] is h12:
            p1, p2, p3 = p1, p3, p2
        elif hs[1] is h23:
            p1, p2, p3 = p3, p1, p2
    elif hs[0] is h23:
        if hs[1] is h12:
            p1, p2, p3 = p2, p3, p1
        elif hs[1] is h13:
            p1, p2, p3 = p3, p2, p1

    h, ratio, theta = _measure(p1, p2, p3)

    return p1, p2, p3, ratio, theta


def _measure(p1, p2, p3):
    """Return hypotenuse, ratio and theta for a trio of ordered points."""
    ha, hb = _hypot(p3.x - p1.x, p3.y - p1.y), _hypot(p2.x - p1.x, p2.y - p1.y)
    va, vb = Vector(p1, p2), Vector(p1, p3)

    theta = _atan2(va.y, va.x)

    x = vb.x * _cos(-theta) - vb.y * _sin(-theta)
    y = vb.x * _sin(-theta) + vb.y * _cos(-theta)

    ratio = ha / hb
    theta = _atan2(y, x)

    return hb, ratio, theta


def theta_ratio_bounds(theta, theta_tol, ratio, ratio_tol):
    """Prepare last four arguments to blobs2features.

    Check bounds on theta so that zero is not crossed and on ration
    so that one is not crossed, either of which would indicate a feature
    flipped around its primary axis.
    """
    # adjust tolerances down with small angles
    ratio_tol *= _sin(abs(theta))
    theta_tol *= _sin(abs(theta))

    if theta > 0.0:
        min_theta, max_theta = max(0.0, theta - theta_tol), theta + theta_tol
    elif theta < 0.0:
        min_theta, max_theta = theta - theta_tol, min(0.0, theta + theta_tol)
    else:
        # zero? weird.
        min_theta, max_theta = 0.0, 0.0

    if ratio > 1.0:
        min_ratio, max_ratio = max(1.0, ratio - ratio_tol), ratio + ratio_tol
    elif ratio < 1.0:
        min_ratio, max_ratio = ratio - ratio_tol, min(1.0, ratio + ratio_tol)
    else:
        # one? weird.
        min_ratio, max_ratio = 1.0, 1.0

    return min_theta, max_theta, min_ratio, max_ratio


def blobs2feats_fitted(blobA, blobB, blobs, tmin, tmax, rmin, rmax):
    """Generate a stream of features corresponding to limits.

    Yields 5-element tuples: indexes for three blobs followed by feature ratio, theta.

    Used when two blobs are known to be part of the target feature,
    but it's not clear which specific points in the feature they will
    correspond to. Performs a simple walk over all six possibilities
    using blobs2feats_limited().
    """
    lim = tmin, tmax, rmin, rmax
    ABL, BAL, ALB, BLA, LAB, LBA = 0, 1, 2, 3, 4, 5

    matches = chain(
        zip(_repeat(ABL), blobs2feats_limited([blobA], [blobB], blobs, *lim)),
        zip(_repeat(BAL), blobs2feats_limited([blobB], [blobA], blobs, *lim)),
        zip(_repeat(ALB), blobs2feats_limited([blobA], blobs, [blobB], *lim)),
        zip(_repeat(BLA), blobs2feats_limited([blobB], blobs, [blobA], *lim)),
        zip(_repeat(LAB), blobs2feats_limited(blobs, [blobA], [blobB], *lim)),
        zip(_repeat(LBA), blobs2feats_limited(blobs, [blobB], [blobA], *lim)),
    )

    for arrangement, match_tuple in matches:
        if arrangement == ABL:
            i, j, k = blobs.index(blobA), blobs.index(blobB), match_tuple[2]
        elif arrangement == BAL:
            i, j, k = blobs.index(blobB), blobs.index(blobA), match_tuple[2]
        elif arrangement == ALB:
            i, j, k = blobs.index(blobA), match_tuple[1], blobs.index(blobB)
        elif arrangement == BLA:
            i, j, k = blobs.index(blobB), match_tuple[1], blobs.index(blobA)
        elif arrangement == LAB:
            i, j, k = match_tuple[0], blobs.index(blobA), blobs.index(blobB)
        elif arrangement == LBA:
            i, j, k = match_tuple[0], blobs.index(blobB), blobs.index(blobA)

        ratio, theta = match_tuple[3:5]

        yield i, j, k, ratio, theta


def blobs2feats_limited(blobs1, blobs2, blobs3, min_theta=-pi, max_theta=pi, min_ratio=0, max_ratio=1):
    """Generate a stream of features corresponding to limits.

    Yields 5-element tuples: indexes for three blobs followed by feature ratio, theta.

    Makes the somewhat-dangerous assumption that the possible blob
    combinations are limited enough to calculate them all and return
    a stream sorted from largest feature to smallest, based on length
    of hypotenuse.
    """
    matches = []

    for blob1, blob2, blob3 in product(blobs1, blobs2, blobs3):
        if blob1 is blob2 or blob2 is blob3 or blob3 is blob1:
            continue

        hypot, ratio, theta = _measure(blob1, blob2, blob3)

        if theta < min_theta or max_theta < theta:
            continue

        if ratio < min_ratio or max_ratio < ratio:
            continue

        sort_by = blob1.size + blob2.size + blob3.size
        matches.append((sort_by, ratio, theta, blob1, blob2, blob3))

    matches.sort(reverse=True)

    for _, ratio, theta, blob1, blob2, blob3 in matches:
        i = blobs1.index(blob1)
        j = blobs2.index(blob2)
        k = blobs3.index(blob3)

        yield (i, j, k, ratio, theta)


def blobs2features(blobs, min_hypot=0, min_theta=-pi, max_theta=pi, min_ratio=0, max_ratio=1):
    """Generate a stream of features conforming to limits.

    Yields 5-element tuples: indexes for three blobs followed by feature ratio, theta.
    """
    count = len(blobs)

    # one-dimensional arrays of simple positions
    xs = _array([blob.x for blob in blobs], dtype=float)
    ys = _array([blob.y for blob in blobs], dtype=float)

    #
    # two-dimensional arrays of component distances between each blob
    #   dx = b.x - a.x, dy = b.y - a.y
    #
    xs_ = repeat(reshape(xs, (1, count)), count, 0)
    ys_ = repeat(reshape(ys, (1, count)), count, 0)
    dxs, dys = transpose(xs_) - xs_, transpose(ys_) - ys_

    #
    # two-dimensional array of distances between each blob
    #   distance = sqrt(dx^2 + dy^2)
    #
    distances = nsqrt(dxs**2 + dys**2)

    #
    # Make a list of eligible eligible blob pairs
    #
    hypoteni = distances.copy()
    hypoteni[distances < min_hypot] = 0

    hypot_nonzero = nonzero(hypoteni)

    ## Prepend separation distance, longest-to-shortest
    # blobs_sorted = [(distances[i,j], i, j) for (i, j) in zip(*hypot_nonzero)]

    # Prepend combined pixel size, largest-to-smallest
    blobs_sorted = [(blobs[i].size + blobs[j].size, i, j) for (i, j) in zip(*hypot_nonzero, strict=True)]

    blobs_sorted.sort(reverse=True)

    #
    # check each hypotenuse for an eligible third point
    #
    for _, i, j in blobs_sorted:
        #
        # vector theta for hypotenuse (i, j)
        #
        ij_theta = _atan2(dys[i, j], dxs[i, j])

        #
        # rotate each blob[k] around blob[i] by -theta, to get a hypotenuse-relative theta for (i, k)
        #
        ik_xs = dxs[i, :] * _cos(-ij_theta) - dys[i, :] * _sin(-ij_theta)
        ik_ys = dxs[i, :] * _sin(-ij_theta) + dys[i, :] * _cos(-ij_theta)

        ik_thetas = arctan2(ik_ys, ik_xs)

        ik_thetas = [(blobs[k].size, k, theta) for (k, theta) in enumerate(ik_thetas)]
        ik_thetas.sort(reverse=True)

        #
        # check each blob[k] for correct distance ratio
        #
        for _, k, theta in ik_thetas:
            ratio = distances[i, k] / distances[i, j]

            if theta < min_theta or max_theta < theta:
                continue

            if ratio < min_ratio or max_ratio < ratio:
                continue

            if i == j or i == k or j == k:
                continue

            yield (i, j, k, ratio, theta)
