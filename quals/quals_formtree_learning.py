"""Replicata: exact and unfinished roots with analytically tractable size errors.
Expectata: learn their scatter with normalized likelihoods, retaining its uncertainty.
Resultata: posterior moments are compared with independent one-dimensional integration.
"""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'searchwatch'))   # formtree_eta.py's directory since 2026-11-10 ([REF]); the root until then
import numpy as np
from scipy.integrate import quad
from scipy.special import ndtr
from scipy.stats import norm
import formtree_eta as eta


def fixture(values, floor):
    roots = [dict(name=str(i), blocks=[[10.] * 8]) for i in range(len(values) + 1)]
    model = dict(seed=61106, log_bias=0., discrepancy_log_sd=1., root_log_sd=.75,
                 root_log_sd_uncertainty=.5, rate_log_sd=0., roots=roots)
    work = dict(done=sum(values) + floor, rate=10., roots=[
        dict(name=str(i), done=value, complete=True) for i, value in enumerate(values)
    ] + [dict(name=str(len(values)), done=floor, complete=False)])
    return model, work


def integrated(values, floor):
    # Independently integrate the normal observation model over shared bias,
    # then integrate the remaining log-scatter hyperparameter by quadrature.
    y = np.log(np.asarray(values) / 10.)
    n = len(values)
    def density(log_sigma):
        sigma = np.exp(log_sigma)
        covariance = sigma * sigma * np.eye(n) + np.ones((n, n))
        logdet = np.linalg.slogdet(covariance)[1]
        exact = np.exp(-.5 * (y @ np.linalg.solve(covariance, y) + logdet))
        mean = y.sum() / (sigma * sigma + n)
        variance = sigma * sigma / (sigma * sigma + n)
        survival = ndtr((mean - np.log(floor / 10.)) / np.sqrt(variance + sigma * sigma)) if floor else 1.
        return norm.pdf(log_sigma, np.log(.75), .5) * exact * survival
    total = quad(density, -5, 3, epsabs=1e-10)[0]
    mean = quad(lambda z: np.exp(z) * density(z), -5, 3, epsabs=1e-10)[0] / total
    upper = quad(density, np.log(.75), 3, epsabs=1e-10)[0] / total
    return mean, upper


class Learning(unittest.TestCase):
    def test_exact_agreement_learns_smaller_scatter_with_correct_normalization(self):
        # Three exact matches have likelihood proportional to
        # sigma^-2 / sqrt(sigma^2 + 3), not a flat likelihood of one.
        m, w = fixture([10, 10, 10], 0)
        samples = eta.draws(m, w, 65536)
        expected, upper = integrated([10, 10, 10], 0)
        self.assertAlmostEqual(float(samples['weight'] @ samples['root_log_sd']), expected, delta=.01)
        self.assertAlmostEqual(float(samples['weight'][samples['root_log_sd'] > .75].sum()), upper, delta=.01)
        self.assertGreater(np.std(samples['root_log_sd']), 0.)

    def test_unfinished_root_survival_also_updates_scatter(self):
        # An exact root of20 and an unfinished one already above200 share bias;
        # both observations must inform scatter, with no false completion at200.
        m, w = fixture([20], 200)
        samples = eta.draws(m, w, 65536)
        expected, upper = integrated([20], 200)
        self.assertAlmostEqual(float(samples['weight'] @ samples['root_log_sd']), expected, delta=.025)
        self.assertAlmostEqual(float(samples['weight'][samples['root_log_sd'] > .75].sum()), upper, delta=.015)
        np.testing.assert_array_equal(samples['trees'][:, 0], 20.)
        self.assertTrue(np.all(samples['trees'][:, 1] > 200))

    def test_no_size_evidence_preserves_scatter_prior(self):
        m, w = fixture([], 0)
        samples = eta.draws(m, w, 65536)
        self.assertAlmostEqual(float(samples['weight'] @ samples['root_log_sd']), .75 * np.exp(.5 * .5**2), delta=.01)
        np.testing.assert_allclose(samples['weight'], 1 / 65536)

    def test_fixed_scatter_remains_an_exact_special_case(self):
        m, w = fixture([20], 200)
        del m['root_log_sd_uncertainty']
        fixed = eta.draws(m, w, 2048)
        m['root_log_sd_uncertainty'] = 0.
        degenerate = eta.draws(m, w, 2048)
        for key in fixed:
            np.testing.assert_array_equal(fixed[key], degenerate[key])

    def test_invalid_scatter_prior_is_not_repaired(self):
        m, w = fixture([20], 200)
        for value in (-1., float('nan'), float('inf')):
            m['root_log_sd_uncertainty'] = value
            with self.subTest(value=value), self.assertRaises(AssertionError):
                eta.draws(m, w, 32)


if __name__ == '__main__':
    unittest.main()
