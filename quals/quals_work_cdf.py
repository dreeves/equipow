"""Work CDF quals: retain atom/uniform probabilities with linear working memory."""
import math
from pathlib import Path
import sys
import tracemalloc
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
import chance


def reference(rest,absent,present,ahead):
    """Independent scalar definition, without a horizon-by-sample array."""
    return np.asarray([math.fsum(a*(h>=r)+b*(min(h,r)/r)
                                for r,a,b in zip(rest,absent,present)) for h in ahead])


class WorkCDF(unittest.TestCase):
    def check(self,rest,absent,present,ahead):
        rest,absent,present=(np.asarray(x,dtype=float) for x in (rest,absent,present))
        before=[x.copy() for x in (rest,absent,present)]
        got=chance._work_cdf(rest,absent,present,ahead)
        self.assertTrue(np.isfinite(got).all())
        np.testing.assert_allclose(got,reference(rest,absent,present,ahead),rtol=3e-13,atol=2e-14)
        for x,y in zip((rest,absent,present),before):
            np.testing.assert_array_equal(x,y)
        return got

    def test_duplicate_times_include_the_whole_atom_at_the_boundary(self):
        # Replicate: unordered horizons around two equal completion times.
        # Expect: both atoms appear at the time, neither just before it.
        h=[10.,np.nextafter(2.,0.),2.,0.,np.nextafter(2.,np.inf),1.]
        self.check([2,10,2],[.2,.1,.1],[.1,.3,.2],h)

    def test_atoms_uniforms_and_zero_masses(self):
        # Replicate each component separately. Expect its stated probability law.
        h=[0,.5,1,2,20,float('inf')]
        self.check([1,2],[.4,.6],[0,0],h)
        self.check([1,2],[0,0],[.4,.6],h)
        self.check([1,2],[0,0],[0,0],h)

    def test_extreme_positive_durations_stay_finite_at_zero_and_infinity(self):
        # Replicate: the smallest positive float and a very long duration.
        # Expect finite probabilities; pre-dividing mass by tiny duration may overflow.
        tiny=np.nextafter(0.,1.)
        self.check([tiny,1e-300,1e300],[0,0,0],[.2,.3,.5],
                   [0,tiny,2*tiny,1e-310,1e-300,1e100,1e300,float('inf')])

    def test_wide_dynamic_range_matches_independent_scalar_definition(self):
        # Replicate: mixed scales and shuffled queries, including zero and infinity.
        # Expect the same mixture distribution independent of summation strategy.
        rng=np.random.default_rng(61106)
        r=np.power(10.,rng.uniform(-250,250,200))
        a=rng.random(200);a*=.4/a.sum()
        b=rng.random(200);b*=.6/b.sum()
        h=np.r_[0,np.power(10.,rng.uniform(-270,270,90)),np.inf]
        self.check(r,a,b,h)

    def test_monotone_cdf_reaches_total_mass(self):
        rng=np.random.default_rng(61107)
        r=rng.integers(1,100,size=1000)
        a=rng.random(1000);b=rng.random(1000);scale=(a+b).sum()
        got=self.check(r,a/scale,b/scale,np.arange(101))
        self.assertTrue(np.all(np.diff(got)>=-2e-14))
        self.assertEqual(got[0],0.)
        self.assertAlmostEqual(got[-1],1.)

    def test_empty_horizon_list_has_empty_output(self):
        self.check([1],[.5],[.5],[])

    def test_large_distribution_uses_linear_working_memory(self):
        # Replicate: thousands of draws and hundreds of chart horizons.
        # Expect less than 1 MiB temporary memory, not a horizon-by-draw matrix.
        # The bound scales with the input/output lengths, not their product.
        n,h=4096,257
        r=np.linspace(.1,100,n);a=np.full(n,.4/n);b=np.full(n,.6/n)
        ahead=np.linspace(0,120,h)
        tracemalloc.start()
        try:
            got=chance._work_cdf(r,a,b,ahead)
            _,peak=tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        self.assertEqual(got.shape,(h,))
        self.assertLess(peak,160*(n+h)+65536)


if __name__=='__main__':
    unittest.main()
