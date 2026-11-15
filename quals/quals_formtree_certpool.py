#!/usr/bin/env python3
"""Cached exact form bounds keep their scales, signed pins, and initialization.

Replicata: upper/lower certificates of different supported scales for a fixed class
sum, and an exact-bound call whose candidates all exceed the certificate limits.
Expectata: cached grid decisions agree with direct integer bounds; fallback is the
current trivial bound. Missing/opposite pins and reinitialization invalidate old
certificates. Resultata before repair: feasible nodes were closed by interpreting
a fine-scale certificate with the coarse denominator or reusing obsolete pins.
The native harness invokes arithmetic helpers, not a search or a live library.
"""
import functools
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(os.environ.get('CERTPOOL_SOURCE', ROOT/'searches/formtree/pex.cpp'))
WORK = tempfile.TemporaryDirectory(prefix='quals_formtree_certpool_')
HARNESS = r'''
static void setup(int n, int degree) {
    N_=n; M_=degree; FOLD=0; CERTPOOL=16; CERTF=nullptr; FZ.assign(n,0); FZlist.clear();
    L.K=degree+2; L.y.assign(degree+2,0); CPOOL.clear(); CPOOL_next=0;
    BINOM.assign(n,vector<LL>(degree,0));
    for(int p=0;p<n;p++) { BINOM[p][0]=1; for(int t=1;t<degree;t++) BINOM[p][t]=BINOM[p][t-1]*(p-t+1)/t; }
    UU.assign(degree,vector<long double>(degree,0));
    for(int t=0;t<degree;t++) UU[t][t]=1.0L/BINOM[n-1][t];
    mods.assign(1,Mod{}); Mod&m=mods[0];m.M=2;m.pos=degree;m.sz={n/2,n/2};m.norm={1,1};m.members.resize(2);
    for(int p=0;p<n;p++)m.members[p%2].push_back(p);
    rowform.assign(degree+2,{-1,{}});rowform[degree]={0,{}};rowform[degree+1]={0,{}};
}
static FormCert fixed_cert(int exponent, int sign) {
    FormCert c; c.rows={M_};c.c={sign*(1LL<<(24+4*exponent))};c.tot=0;
    c.dd=((LL)1)<<(50+4*exponent);c.scale=c.dd*(((LL)1)<<(24+4*exponent));
    return c;
}
static ll direct(const FormCert&c,const vector<ll>&raw) {
    LL n=c.tot;for(size_t i=0;i<c.rows.size();i++)n+=c.dd*c.c[i]*raw[c.rows[i]];
    return (ll)(n/c.scale-(n<0&&n%c.scale!=0));
}
int main(int argc,char**argv) {
    assert(argc==2);string mode=argv[1];
    if(mode=="grids") {
        setup(2,1);Node nd;nd.fixed={{1,1}};
        for(int a=0;a<3;a++)for(int b=0;b<3;b++)for(int parity=0;parity<2;parity++) {
            CPOOL.clear();cpool_add(fixed_cert(a,1),fixed_cert(b,-1),2,parity);
            assert(cpool_close(nd)==(parity==0));
        }
        cout<<18<<"\n";return 0;
    }
    if(mode=="pins") {
        for(int s:{-1,1}) {
            setup(4,2);vector<int>w={1,0};L.y.clear();ll bound;
            assert(exact_bound_form(0,w,s,vector<int>{},vector<double>{},bound)&&bound==2);FormCert free=LASTCERT;
            FZ[0]=FZ[2]=s;FZlist={s,3*s};
            assert(exact_bound_form(0,w,-s,vector<int>{},vector<double>{},bound)&&bound==-2);FormCert pinned=LASTCERT;
            cpool_add(s<0?pinned:free,s<0?free:pinned,4,0);Node nd;
            // Either bound alone carries pins forcing this form to +/-2, outside 0 mod4.
            // Without both pins, (+,-,-,+) or its negative witnesses form0; FZ stays old.
            for(vector<int> pins: {vector<int>{},vector<int>{s},vector<int>{-s,3*s}}) { nd.sgn=pins;assert(!cpool_close(nd)); }
            for(vector<int> pins: {vector<int>{s,3*s},vector<int>{s,3*s,2}}) { nd.sgn=pins;assert(cpool_close(nd)); }
        }
        cout<<10<<"\n";return 0;
    }
    if(mode=="init") {
        setup(2,1);cpool_add(fixed_cert(0,1),fixed_cert(0,-1),1,0);CPOOL_next=3;
        string path=string(argv[0])+".cfg";{ofstream out(path);out<<"2 1 0\n1\n";}
        double moments[2]={1,1};assert(pe_init(path.c_str(),moments)==0);
        assert(CPOOL.empty()&&CPOOL_next==0);Node nd;assert(!cpool_close(nd));
        cout<<1<<"\n";return 0;
    }
    if(mode=="captured") {
        setup(480,14);vector<int>rows(M_+2);for(int q=0;q<M_+2;q++)rows[q]=q;
        vector<double>vals(rows.size(),0);vals[M_]=7;vals[M_+1]=-7;
        vector<ll>raw(rows.size(),0);raw[M_]=7;raw[M_+1]=-7;
        mt19937 gen(411);int finer=0;
        for(int i=0;i<150;i++) {
            for(double&v:L.y)v=((int)(gen()%10001)-5000)/997.0;
            for(signed char&v:FZ)v=(int)(gen()%3)-1;
            FZlist.clear();for(int p=0;p<N_;p++)if(FZ[p])FZlist.push_back((p+1)*FZ[p]);
            vector<int>w(2);for(int&v:w)v=(int)(gen()%7)-3;
            ll bound;assert(exact_bound_form(0,w,i%2?1:-1,rows,vals,bound));
            assert(LASTCERT.dd>0&&LASTCERT.scale>0&&direct(LASTCERT,raw)==bound);
            finer+=LASTCERT.dd>DD0;
        }
        assert(finer>0);cout<<150<<" "<<finer<<"\n";return 0;
    }
    assert(mode=="fallback");setup(2,1);
    vector<int>w={1,0};ll bound;L.y={1};
    assert(exact_bound_form(0,w,1,vector<int>{1},vector<double>{1},bound));
    assert(bound==1&&!LASTCERT.rows.empty());
    L.y={ldexp(1.0,39)};
    assert(exact_bound_form(0,w,1,vector<int>{0},vector<double>{0},bound));
    assert(bound==1&&LASTCERT.rows.empty()&&LASTCERT.c.empty());
    assert(direct(LASTCERT,vector<ll>(3,0))==bound);
    cout<<1<<"\n";
}
'''


@functools.lru_cache(maxsize=1)
def executable():
    cpp=Path(WORK.name)/'certpool.cpp';exe=Path(WORK.name)/'certpool'
    cpp.write_text('#include <cassert>\n'+SOURCE.read_text()+HARNESS)
    subprocess.run(['g++','-O2','-std=c++17',str(cpp),'-o',str(exe)],check=True)
    return exe


class CertPoolQuals(unittest.TestCase):
    def check(self, mode):
        p=subprocess.run([executable(),mode],capture_output=True,text=True)
        self.assertEqual(p.returncode,0,p.stdout+p.stderr)

    def test_mixed_scales_preserve_feasible_and_infeasible_grids(self): self.check('grids')
    def test_cached_bounds_equal_the_bounds_actually_returned(self): self.check('captured')
    def test_trivial_fallback_replaces_previous_certificate(self): self.check('fallback')
    def test_missing_or_opposite_pins_do_not_reuse_a_conditional_bound(self): self.check('pins')
    def test_reinitialization_clears_prior_cached_bounds(self): self.check('init')


if __name__=='__main__': unittest.main()
