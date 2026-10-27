#!/usr/bin/env python3

from featuremath import MatchedFeature, blobs2feats_fitted, blobs2feats_limited, blobs2features, theta_ratio_bounds
from matrixmath import Transform, quad2quad


def paper_matches(blobs):
    """Generate matches for specific paper sizes.

    Yield tuples with transformations from scan pixels to print points,
    paper sizes and orientations. Print points are centered on lower right
    corner of QR code.
    """
    from dimensions import (
        point_F_landscape_a3,
        point_F_landscape_a4,
        point_F_landscape_ltr,
        point_F_portrait_a3,
        point_F_portrait_a4,
        point_F_portrait_ltr,
        ratio_landscape_a3,
        ratio_landscape_a4,
        ratio_landscape_ltr,
        ratio_portrait_a3,
        ratio_portrait_a4,
        ratio_portrait_ltr,
    )

    for dbc_match, aed_match in _blob_matches_primary(blobs):
        for f_match, point_F in _blob_matches_secondary(blobs, aed_match):
            #
            # determining paper size and orientation based on identity of point E.
            #
            if point_F is point_F_portrait_a3:
                orientation, paper_size, scale = 'portrait', 'a3', 1 / ratio_portrait_a3

            elif point_F is point_F_portrait_a4:
                orientation, paper_size, scale = 'portrait', 'a4', 1 / ratio_portrait_a4

            elif point_F is point_F_portrait_ltr:
                orientation, paper_size, scale = 'portrait', 'letter', 1 / ratio_portrait_ltr

            elif point_F is point_F_landscape_a3:
                orientation, paper_size, scale = 'landscape', 'a3', 1 / ratio_landscape_a3

            elif point_F is point_F_landscape_a4:
                orientation, paper_size, scale = 'landscape', 'a4', 1 / ratio_landscape_a4

            elif point_F is point_F_landscape_ltr:
                orientation, paper_size, scale = 'landscape', 'letter', 1 / ratio_landscape_ltr

            else:
                raise Exception('How did we ever get here?')

            #
            # find the scan location of point F
            #
            (scan_F,) = [getattr(f_match, 's%d' % i) for i in (1, 2, 3) if getattr(f_match, 'p%d' % i) is point_F]

            #
            # transform from scan pixels to homogenous print coordinates - A, C, E, F
            #
            s2h = quad2quad(
                aed_match.s1, aed_match.p1, dbc_match.s3, dbc_match.p3, aed_match.s2, aed_match.p2, scan_F, point_F
            )

            #
            # transform from scan pixels to printed points, with (0, 0) at lower right
            #
            h2p = Transform(scale, 0, 0, 0, scale, 0)
            s2p = s2h.multiply(h2p)

            yield s2p, paper_size, orientation


def _blob_matches_primary(blobs):
    """Generate known matches for DBC (top) and AED (bottom) triangle pairs."""
    from dimensions import feature_aed, feature_dab, feature_dbc, feature_eac, min_size, ratio_tol, theta_tol

    dbc_theta, dbc_ratio = feature_dbc.theta, feature_dbc.ratio
    dab_theta, dab_ratio = feature_dab.theta, feature_dab.ratio
    aed_theta, aed_ratio = feature_aed.theta, feature_aed.ratio
    eac_theta, eac_ratio = feature_eac.theta, feature_eac.ratio

    dbc_matches = blobs2features(blobs, min_size, *theta_ratio_bounds(dbc_theta, theta_tol, dbc_ratio, ratio_tol))

    for dbc_tuple in dbc_matches:
        i0, j0, k0 = dbc_tuple[0:3]
        dbc_match = MatchedFeature(feature_dbc, blobs[i0], blobs[j0], blobs[k0])

        # print('Found a match for DBC -', (i0, j0, k0))

        dab_matches = blobs2feats_limited(
            [blobs[i0]], blobs, [blobs[j0]], *theta_ratio_bounds(dab_theta, theta_tol, dab_ratio, ratio_tol)
        )

        for dab_tuple in dab_matches:
            i1, j1, k1 = i0, dab_tuple[1], j0
            dab_match = MatchedFeature(feature_dab, blobs[i1], blobs[j1], blobs[k1])

            if not dab_match.fits(dbc_match):
                continue

            # print(' Found a match for DAB -', (i1, j1, k1))

            #
            # We think we have a match for points A-D, now check for point E.
            #

            aed_matches = blobs2feats_limited(
                [blobs[j1]], blobs, [blobs[i1]], *theta_ratio_bounds(aed_theta, theta_tol, aed_ratio, ratio_tol)
            )

            for aed_tuple in aed_matches:
                i2, j2, k2 = j1, aed_tuple[1], i1
                aed_match = MatchedFeature(feature_aed, blobs[i2], blobs[j2], blobs[k2])

                if not aed_match.fits(dbc_match):
                    continue

                if not aed_match.fits(dab_match):
                    continue

                # print('  Found a match for AED -', (i2, j2, k2))

                #
                # We now know we have a three-triangle match; try a fourth to verify.
                # Use the very small set of blobs from the current set of matches.
                #

                _blobs = [blobs[n] for n in set((i0, j0, k0) + (i1, j1, k1) + (i2, j2, k2))]
                eac_matches = blobs2features(
                    _blobs, min_size, *theta_ratio_bounds(eac_theta, theta_tol, eac_ratio, ratio_tol)
                )

                for eac_tuple in eac_matches:
                    i3, j3, k3 = eac_tuple[0:3]
                    eac_match = MatchedFeature(feature_eac, _blobs[i3], _blobs[j3], _blobs[k3])

                    if not eac_match.fits(dbc_match):
                        continue

                    if not eac_match.fits(dab_match):
                        continue

                    if not eac_match.fits(aed_match):
                        continue

                    # print('   Confirmed match with EAC -', (i3, j3, k3))

                    yield dbc_match, aed_match


def _blob_matches_secondary(blobs, aed_match):
    """Generate known matches for AED (bottom) and paper-specific triangle groups."""
    from dimensions import (
        feature_f_landscape_a3,
        feature_f_landscape_a4,
        feature_f_landscape_ltr,
        feature_f_portrait_a3,
        feature_f_portrait_a4,
        feature_f_portrait_ltr,
        feature_g_landscape_a3,
        feature_g_landscape_a4,
        feature_g_landscape_ltr,
        feature_g_portrait_a3,
        feature_g_portrait_a4,
        feature_g_portrait_ltr,
        point_F_landscape_a3,
        point_F_landscape_a4,
        point_F_landscape_ltr,
        point_F_portrait_a3,
        point_F_portrait_a4,
        point_F_portrait_ltr,
        point_G_landscape_a3,
        point_G_landscape_a4,
        point_G_landscape_ltr,
        point_G_portrait_a3,
        point_G_portrait_a4,
        point_G_portrait_ltr,
        ratio_tol,
        theta_tol,
    )

    features_fg = (
        (feature_g_landscape_ltr, point_G_landscape_ltr, feature_f_landscape_ltr, point_F_landscape_ltr),
        (feature_g_portrait_ltr, point_G_portrait_ltr, feature_f_portrait_ltr, point_F_portrait_ltr),
        (feature_g_landscape_a4, point_G_landscape_a4, feature_f_landscape_a4, point_F_landscape_a4),
        (feature_g_portrait_a4, point_G_portrait_a4, feature_f_portrait_a4, point_F_portrait_a4),
        (feature_g_landscape_a3, point_G_landscape_a3, feature_f_landscape_a3, point_F_landscape_a3),
        (feature_g_portrait_a3, point_G_portrait_a3, feature_f_portrait_a3, point_F_portrait_a3),
    )

    for feature_g, _point_G, feature_f, point_F in features_fg:
        g_theta, g_ratio = feature_g.theta, feature_g.ratio
        g_bounds = theta_ratio_bounds(g_theta, theta_tol, g_ratio, ratio_tol)
        g_matches = blobs2feats_fitted(aed_match.s1, aed_match.s2, blobs, *g_bounds)

        for g_tuple in g_matches:
            i0, j0, k0 = g_tuple[0:3]
            g_match = MatchedFeature(feature_g, blobs[i0], blobs[j0], blobs[k0])

            if not g_match.fits(aed_match):
                continue

            aed_blobs = (aed_match.s1, aed_match.s2)

            if g_match.s1 in aed_blobs and g_match.s2 in aed_blobs:
                blob_G = g_match.s3
            elif g_match.s1 in aed_blobs and g_match.s3 in aed_blobs:
                blob_G = g_match.s2
            elif g_match.s2 in aed_blobs and g_match.s3 in aed_blobs:
                blob_G = g_match.s1
            else:
                raise Exception('what?')

            # print('    Found a match for point G -', (i0, j0, k0))

            #
            # We think we have a match for point G, now check for point F.
            #

            f_theta, f_ratio = feature_f.theta, feature_f.ratio
            f_bounds = theta_ratio_bounds(f_theta, theta_tol, f_ratio, ratio_tol)
            f_matches = blobs2feats_fitted(blob_G, aed_match.s2, blobs, *f_bounds)

            for f_tuple in f_matches:
                i1, j1, k1 = f_tuple[0:3]
                f_match = MatchedFeature(feature_f, blobs[i1], blobs[j1], blobs[k1])

                if not f_match.fits(g_match):
                    continue

                # print('     Found a match for point F -', (i1, j1, k1), point_F)

                #
                # Based on the identity of point_F, we can find paper size and orientation.
                #
                yield f_match, point_F


def get_paper_size(paper, orientation):
    if (paper, orientation) == ('letter', 'landscape'):
        from dimensions import paper_size_landscape_ltr as paper_size_pt

    elif (paper, orientation) == ('letter', 'portrait'):
        from dimensions import paper_size_portrait_ltr as paper_size_pt

    elif (paper, orientation) == ('a4', 'landscape'):
        from dimensions import paper_size_landscape_a4 as paper_size_pt

    elif (paper, orientation) == ('a4', 'portrait'):
        from dimensions import paper_size_portrait_a4 as paper_size_pt

    elif (paper, orientation) == ('a3', 'landscape'):
        from dimensions import paper_size_landscape_a3 as paper_size_pt

    elif (paper, orientation) == ('a3', 'portrait'):
        from dimensions import paper_size_portrait_a3 as paper_size_pt

    else:
        raise Exception('not yet')

    paper_width_pt, paper_height_pt = paper_size_pt

    return paper_width_pt, paper_height_pt
