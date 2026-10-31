/* _fastlp: the dense bounded dual simplex of proto.py, in C, for certbb's branch-and-bound LP.

   proto.py's docstring defines the method and its vocabulary (logical, cost, snapshot, slope); this file follows it
   step for step, in the same order and with the same tie-breaking, so that both make the same pivots up to rounding
   (quals_fastlp.py compares them on the captured corpus).  fastlp.py wraps the type with the costs.

   Dual(A, b, cost, limit): A an m x n C-contiguous float64 array, b m floats, cost n floats, limit the iterations
   allowed per solve.  Methods: rhs(b); solve(lo, hi, snapshot=None) -> (status, vector); snapshot() -> bytes;
   load(status codes, int8, n + m: HiGHS's 0 lower, 1 basic, 2 upper; others nonbasic); attributes iterations (the
   last solve's) and stats (a dict of counters).  Statuses: 'Optimal' with the point (n floats), 'Infeasible' with
   the ray y (m floats, y.b > max over the box of y.(A x)), 'Iteration limit' or 'Trouble' with None.  Nothing here
   is trusted: certbb's producer turns a ray into integer multipliers and checks them exactly. */
#define PY_SSIZE_T_CLEAN
#include <Python.h>
#define NPY_NO_DEPRECATED_API NPY_1_7_API_VERSION
#include <numpy/arrayobject.h>
#include <math.h>
#include <stdint.h>
#include <string.h>

#define TOL_P 1e-9      /* primal feasibility tolerance */
#define TOL_D 1e-9      /* dual feasibility tolerance, against costs of order 1 */
#define ALPHA_TOL 1e-9  /* pivot row entries at most this in size count as zero */
#define CHECK 1e-9      /* relative agreement asked of alpha_q from the row and from the column */
#define REFACTOR 64     /* updates of the explicit inverse between refactorizations */
#define MARGIN 1e-9     /* an 'Infeasible' ray's own bound, relative to max |y|, must pass this */
#define SINGULAR 1e-11  /* a refactorization's pivot at most this (relative to the column's largest) fails */
#define EQUAL 1e-9      /* scores and pivot sizes within this relative distance of the largest count as tied */
#define MAXDIM 4096     /* the most rows and columns A may have (indices stay far inside int) */

enum { OPTIMAL, INFEASIBLE, LIMIT, TROUBLE, BROKEN };      /* BROKEN: an assertion failed; solve raises */
enum { S_SOLVES, S_ITERATIONS, S_REFACTORS, S_CHECK_FAILS, S_FLIPS, S_CLAMPS, S_FIXUPS, S_MARGIN_FAILS, S_SINGULAR, S_N };
static const char *STAT_NAMES[S_N] = {"solves", "iterations", "refactors", "check_fails", "flips", "clamps", "fixups",
                                      "margin_fails", "singular"};
static PyObject *STATUS[4];

typedef struct {
    PyObject_HEAD
    int m, n, nt, limit, updates, iterations;
    double *A;              /* m x n, row-major */
    double *At;             /* n x m: column j of A at At + j m */
    /* the rows by density: v A over the dense rows (more than n/2 nonzeros) by axpys of A's rows, over the others by
       their nonzeros column by column (sp_*); a column's nonzeros (cs_*) serve B^-1 a_j, b - A x and flips */
    int nd, *dense, *sp_start, *sp_row, *cs_start, *cs_row;    /* nd; n + 1; nnz; n + 1; nnz */
    double *sp_val, *cs_val;
    double *b, *c, *lo, *hi, *d, *alpha;        /* b: m; the rest: nt.  The state: basic, pos, upper, Binv, updates,
                                                   xB, d and the box lo, hi (proto.py's 'state') */
    double *Binv, *B;       /* m x m, row-major; B: refactorization workspace (m x 2m) */
    double *xB, *y, *r, *aq, *col, *g, *blo, *bhi;  /* m, m, m, m, m, n, n, n (blo, bhi: a solve's box) */
    int *basic, *pos, *cidx;                    /* m, nt, 2 nt (the candidates, then the window) */
    unsigned char *upper, *cpass;               /* nt, nt */
    double *caa, *cdd, *ct, *ccap;              /* nt each */
    long long stats[S_N];
} Dual;

static double *alloc(size_t count) { return PyMem_Calloc(count ? count : 1, sizeof(double)); }

/* a . b over n entries, in four interleaved partial sums (fixed order), so the products' additions overlap */
static double dot(const double *a, const double *b, int n) {
    double t0 = 0.0, t1 = 0.0, t2 = 0.0, t3 = 0.0;
    int k = 0;
    for (; k + 4 <= n; k += 4) { t0 += a[k] * b[k]; t1 += a[k + 1] * b[k + 1]; t2 += a[k + 2] * b[k + 2]; t3 += a[k + 3] * b[k + 3]; }
    for (; k < n; k++) t0 += a[k] * b[k];
    return (t0 + t1) + (t2 + t3);
}

/* row . (the sparse vector of the nnz entries val at positions idx), in the same four partial sums */
static double dot_sparse(const double *row, const int *idx, const double *val, int nnz) {
    double t0 = 0.0, t1 = 0.0, t2 = 0.0, t3 = 0.0;
    int k = 0;
    for (; k + 4 <= nnz; k += 4) {
        t0 += row[idx[k]] * val[k]; t1 += row[idx[k + 1]] * val[k + 1];
        t2 += row[idx[k + 2]] * val[k + 2]; t3 += row[idx[k + 3]] * val[k + 3];
    }
    for (; k < nnz; k++) t0 += row[idx[k]] * val[k];
    return (t0 + t1) + (t2 + t3);
}

static void release(Dual *s) {
    void **p[] = {(void **)&s->A, (void **)&s->At, (void **)&s->b, (void **)&s->c, (void **)&s->lo,
                  (void **)&s->hi, (void **)&s->d, (void **)&s->alpha, (void **)&s->Binv, (void **)&s->B,
                  (void **)&s->xB, (void **)&s->y, (void **)&s->r, (void **)&s->aq, (void **)&s->col, (void **)&s->g,
                  (void **)&s->basic, (void **)&s->pos, (void **)&s->cidx, (void **)&s->upper, (void **)&s->cpass,
                  (void **)&s->caa, (void **)&s->cdd, (void **)&s->ct, (void **)&s->ccap, (void **)&s->dense,
                  (void **)&s->sp_start, (void **)&s->sp_row, (void **)&s->cs_start, (void **)&s->cs_row,
                  (void **)&s->sp_val, (void **)&s->cs_val, (void **)&s->blo, (void **)&s->bhi};
    for (size_t i = 0; i < sizeof p / sizeof p[0]; i++) { PyMem_Free(*p[i]); *p[i] = NULL; }
}

static void Dual_dealloc(Dual *s) {
    release(s);
    Py_TYPE(s)->tp_free((PyObject *)s);
}

/* ---------- linear algebra on the explicit inverse ---------- */

/* The inverse of the columns basic[0..m) of [A I], by Gauss-Jordan with partial pivoting, into the right half of the
   workspace B (m x 2m); -1 if singular.  Nothing else changes. */
static int invert(Dual *s, const int *basic) {
    int m = s->m, n = s->n, w = 2 * m;
    double *B = s->B;
    for (int i = 0; i < m; i++)
        for (int k = 0; k < w; k++) B[i * w + k] = 0.0;
    for (int k = 0; k < m; k++) {
        int v = basic[k];
        for (int i = 0; i < m; i++) B[i * w + k] = v < n ? s->At[(size_t)v * m + i] : (double)(i == v - n);
        B[k * w + m + k] = 1.0;
    }
    for (int k = 0; k < m; k++) {
        int piv = k;
        double big = fabs(B[k * w + k]), colmax = 0.0;
        for (int i = k; i < m; i++) {
            double a = fabs(B[i * w + k]);
            if (a > big) { big = a; piv = i; }
        }
        for (int i = 0; i < m; i++) colmax = fmax(colmax, fabs(B[i * w + k]));
        if (!(big > SINGULAR * fmax(colmax, 1.0))) { s->stats[S_SINGULAR]++; return -1; }
        if (piv != k)
            for (int j = 0; j < w; j++) { double t = B[k * w + j]; B[k * w + j] = B[piv * w + j]; B[piv * w + j] = t; }
        /* the columns that can be nonzero: k..m-1 on the left, and on the right those of the unit columns placed so
           far, m..m + piv for the row swaps seen: the whole right half is kept for simplicity */
        double inv = 1.0 / B[k * w + k];
        for (int j = k; j < w; j++) B[k * w + j] *= inv;
        for (int i = 0; i < m; i++) {
            double f = B[i * w + k];
            if (i == k || f == 0.0) continue;
            for (int j = k; j < w; j++) B[i * w + j] -= f * B[k * w + j];
        }
    }
    return 0;
}

/* Binv from scratch for the current basis; -1 if singular (then nothing changes). */
static int refactor(Dual *s) {
    int m = s->m;
    s->stats[S_REFACTORS]++;
    if (invert(s, s->basic) < 0) return -1;
    for (int i = 0; i < m; i++) memcpy(s->Binv + (size_t)i * m, s->B + (size_t)i * 2 * m + m, m * sizeof(double));
    s->updates = 0;
    return 0;
}

/* Are the state's numbers finite: xB, d and the explicit inverse?  A state that is not is Trouble (HiGHS's box). */
static int finite_state(const Dual *s) {
    int ok = 1;
    for (int i = 0; i < s->m; i++) ok &= isfinite(s->xB[i]);
    for (int j = 0; j < s->nt; j++) ok &= isfinite(s->d[j]);
    for (size_t k = 0; k < (size_t)s->m * s->m; k++) ok &= isfinite(s->Binv[k]);
    return ok;
}

/* out[j] = v . A[:, j] for the n structural columns. */
static void times_A(const Dual *s, const double *v, double *out) {
    int n = s->n, e = 0;
    for (int j = 0; j < n; j++) out[j] = 0.0;
    for (; e + 4 <= s->nd; e += 4) {          /* four dense rows per pass over out */
        const double *r0 = s->A + (size_t)s->dense[e] * n, *r1 = s->A + (size_t)s->dense[e + 1] * n;
        const double *r2 = s->A + (size_t)s->dense[e + 2] * n, *r3 = s->A + (size_t)s->dense[e + 3] * n;
        double v0 = v[s->dense[e]], v1 = v[s->dense[e + 1]], v2 = v[s->dense[e + 2]], v3 = v[s->dense[e + 3]];
        for (int j = 0; j < n; j++) out[j] += (v0 * r0[j] + v1 * r1[j]) + (v2 * r2[j] + v3 * r3[j]);
    }
    for (; e < s->nd; e++) {
        int i = s->dense[e];
        double vi = v[i];
        const double *row = s->A + (size_t)i * n;
        for (int j = 0; j < n; j++) out[j] += vi * row[j];
    }
    for (int j = 0; j < n; j++) {
        double t = 0.0;
        for (int k = s->sp_start[j]; k < s->sp_start[j + 1]; k++) t += v[s->sp_row[k]] * s->sp_val[k];
        out[j] += t;
    }
}

/* d = c - [A I]^T y with y = Binv^T c_B; 0 on the basic variables. */
static void duals(Dual *s) {
    int m = s->m, n = s->n;
    double *y = s->y, *g = s->g;
    for (int k = 0; k < m; k++) y[k] = 0.0;
    for (int i = 0; i < m; i++) {
        double cb = s->c[s->basic[i]];
        const double *row = s->Binv + (size_t)i * m;
        for (int k = 0; k < m; k++) y[k] += cb * row[k];
    }
    times_A(s, y, g);
    for (int j = 0; j < n; j++) s->d[j] = s->c[j] - g[j];
    for (int i = 0; i < m; i++) s->d[n + i] = s->c[n + i] - y[i];
    for (int i = 0; i < m; i++) s->d[s->basic[i]] = 0.0;
}

static double value(const Dual *s, int j) { return s->upper[j] ? s->hi[j] : s->lo[j]; }

/* xB = Binv (b - sum over nonbasic j of a_j x_j). */
static void primal(Dual *s) {
    int m = s->m, n = s->n;
    double *r = s->r;
    for (int i = 0; i < m; i++) r[i] = s->b[i];
    for (int j = 0; j < n; j++) {
        if (s->pos[j] >= 0) continue;
        double x = value(s, j);
        if (x == 0.0) continue;
        for (int k = s->cs_start[j]; k < s->cs_start[j + 1]; k++) r[s->cs_row[k]] -= x * s->cs_val[k];
    }
    for (int i = 0; i < m; i++) s->xB[i] = dot(s->Binv + (size_t)i * m, r, m);
}

/* xB -= Binv col. */
static void primal_move(Dual *s, const double *col) {
    int m = s->m;
    for (int i = 0; i < m; i++) s->xB[i] -= dot(s->Binv + (size_t)i * m, col, m);
}

/* col += delta a_j. */
static void add_column(const Dual *s, double *col, int j, double delta) {
    if (j >= s->n) { col[j - s->n] += delta; return; }
    for (int k = s->cs_start[j]; k < s->cs_start[j + 1]; k++) col[s->cs_row[k]] += delta * s->cs_val[k];
}

/* ---------- the solve ---------- */

static int movable(const Dual *s, int j) { return s->pos[j] < 0 && s->hi[j] > s->lo[j]; }

/* d and xB from scratch (the bounds as they are), after a refactorization. */
static void recompute(Dual *s) {
    duals(s);
    primal(s);
}

/* d and xB from scratch, with the bound choice by d's sign for every movable nonbasic variable. */
static void fresh(Dual *s) {
    duals(s);
    for (int j = 0; j < s->nt; j++) {
        if (!movable(s, j)) continue;
        if (s->upper[j] && s->d[j] > TOL_D) s->upper[j] = 0;
        else if (!s->upper[j] && s->d[j] < -TOL_D) s->upper[j] = 1;
    }
    primal(s);
}

/* Move the state to the box (lo, hi) of n structural bounds (proto.py's 'state'). */
static void move(Dual *s, const double *lo, const double *hi) {
    int m = s->m, nchanged = 0;
    for (int i = 0; i < m; i++) s->col[i] = 0.0;
    for (int j = 0; j < s->n; j++) {
        if (lo[j] == s->lo[j] && hi[j] == s->hi[j]) continue;
        int basic = s->pos[j] >= 0;
        double old = value(s, j);
        s->lo[j] = lo[j];
        s->hi[j] = hi[j];
        if (basic) continue;
        if (movable(s, j) && s->upper[j] && s->d[j] > TOL_D) s->upper[j] = 0;
        else if (movable(s, j) && !s->upper[j] && s->d[j] < -TOL_D) s->upper[j] = 1;
        add_column(s, s->col, j, value(s, j) - old);
        nchanged++;
    }
    if (nchanged) primal_move(s, s->col);
}

static int stop(Dual *s, int it, int status) {
    s->iterations = it;
    s->stats[S_ITERATIONS] += it;
    return status;
}

static int run(Dual *s) {
    int m = s->m, n = s->n, nt = s->nt, it = 0;
    for (;;) {
        /* 1. the leaving row: largest infeasibility^2 / ||Binv[r]||^2, the first of those within EQUAL of it */
        int r = -1;
        double best = 0.0, *score = s->r;
        for (int i = 0; i < m; i++) {
            int v = s->basic[i];
            double x = s->xB[i], inf = fmax(s->lo[v] - x, 0.0) + fmax(x - s->hi[v], 0.0);
            score[i] = 0.0;
            if (inf <= TOL_P) continue;
            const double *row = s->Binv + (size_t)i * m;
            score[i] = inf * inf / dot(row, row, m);
            best = fmax(best, score[i]);
        }
        for (int i = 0; i < m && best > 0.0; i++)
            if (score[i] >= best * (1 - EQUAL)) { r = i; break; }
        if (r < 0) return stop(s, it, finite_state(s) ? OPTIMAL : TROUBLE);
        if (it >= s->limit) return stop(s, it, LIMIT);
        int p = s->basic[r];
        double sigma = s->xB[r] > s->hi[p] ? 1.0 : -1.0;
        double bound = sigma > 0 ? s->hi[p] : s->lo[p];
        const double *rho = s->Binv + (size_t)r * m;
        /* 2. the pivot row alpha = rho [A I] */
        double *alpha = s->alpha;
        times_A(s, rho, alpha);
        for (int i = 0; i < m; i++) alpha[n + i] = rho[i];
        /* 3. the helpful moves (a branchless pass), then their quantities, with the least breakpoint (first) */
        int K = 0, first = -1;
        double total = 0.0;
        for (int j = 0; j < nt; j++) {
            double sj = s->upper[j] ? -1.0 : 1.0;
            s->cidx[K] = j;
            K += (s->pos[j] < 0) & (s->hi[j] > s->lo[j]) & (sj * sigma * alpha[j] > ALPHA_TOL);
        }
        for (int e = 0; e < K; e++) {
            int j = s->cidx[e];
            double aa = fabs(alpha[j]), dd = fmax((s->upper[j] ? -1.0 : 1.0) * s->d[j], 0.0), t = dd / aa;
            s->caa[e] = aa; s->cdd[e] = dd; s->ct[e] = t;
            s->ccap[e] = aa * (s->hi[j] - s->lo[j]);
            s->cpass[e] = 0;
            total += s->ccap[e];
            if (first < 0 || t < s->ct[first]) first = e;
        }
        double slope = fabs(s->xB[r] - bound);
        if (slope - total > TOL_P) {         /* no move makes row r feasible: the ray, checked afresh */
            double *y = s->y, ymax = 0.0, yb = 0.0, top = 0.0;
            for (int i = 0; i < m; i++) { y[i] = sigma * rho[i]; ymax = fmax(ymax, fabs(y[i])); yb += y[i] * s->b[i]; }
            times_A(s, y, s->g);
            for (int j = 0; j < n; j++) top += fmax(s->g[j] * s->lo[j], s->g[j] * s->hi[j]);
            if (yb - top > MARGIN * ymax) return stop(s, it, finite_state(s) ? INFEASIBLE : TROUBLE);
            s->stats[S_MARGIN_FAILS]++;
            if (s->updates == 0 || refactor(s) < 0) return stop(s, it, TROUBLE);
            recompute(s);
            continue;
        }
        /* the breakpoints passed while the slope stays above TOL_P (never the last), in increasing t, ties by index */
        int k = 0, a = first;
        while (k < K - 1 && slope - s->ccap[a] > TOL_P) {
            s->cpass[a] = 1;
            slope -= s->ccap[a];
            k++;
            a = -1;
            for (int e = 0; e < K; e++)
                if (!s->cpass[e] && (a < 0 || s->ct[e] < s->ct[a])) a = e;
        }
        /* Harris's window among those left: the largest |alpha| enters, the least t (then index) within EQUAL of it */
        double tmax = INFINITY, amax = 0.0;
        for (int e = 0; e < K; e++)
            if (!s->cpass[e]) tmax = fmin(tmax, (s->cdd[e] + TOL_D) / s->caa[e]);
        int W = 0, *win = s->cidx + K;      /* the window's members, after the candidates in cidx */
        for (int e = 0; e < K; e++)
            if (!s->cpass[e] && s->ct[e] <= tmax) { win[W++] = e; amax = fmax(amax, s->caa[e]); }
        int qe = -1;
        for (int w = 0; w < W; w++) {
            int e = win[w];
            if (s->caa[e] >= amax * (1 - EQUAL) && (qe < 0 || s->ct[e] < s->ct[qe])) qe = e;
        }
        /* with K >= 1 the window holds the least bound's candidate, so qe < 0 means numbers that are not finite
           (Trouble) or a broken invariant (raised) */
        if (qe < 0) return stop(s, it, finite_state(s) ? BROKEN : TROUBLE);
        int q = s->cidx[qe];
        /* 4. the entering column, checked against the row */
        double *aq = s->aq;
        if (q < n) {
            int c0 = s->cs_start[q], nnz = s->cs_start[q + 1] - c0;
            for (int i = 0; i < m; i++) aq[i] = dot_sparse(s->Binv + (size_t)i * m, s->cs_row + c0, s->cs_val + c0, nnz);
        } else {
            for (int i = 0; i < m; i++) aq[i] = s->Binv[(size_t)i * m + (q - n)];
        }
        if (fabs(aq[r] - alpha[q]) > CHECK * fmax(1.0, fabs(alpha[q]))) {
            s->stats[S_CHECK_FAILS]++;              /* on a fresh inverse a refactorization changes nothing: Trouble */
            if (s->updates == 0 || refactor(s) < 0) return stop(s, it, TROUBLE);
            recompute(s);
            continue;
        }
        it++;
        /* the flips of the passed breakpoints */
        int nflip = 0;
        for (int i = 0; i < m; i++) s->col[i] = 0.0;
        for (int e = 0; e < K; e++) {
            if (!s->cpass[e]) continue;
            int j = s->cidx[e];
            add_column(s, s->col, j, s->upper[j] ? s->lo[j] - s->hi[j] : s->hi[j] - s->lo[j]);
            s->upper[j] ^= 1;
            nflip++;
        }
        if (nflip) primal_move(s, s->col);
        s->stats[S_FLIPS] += nflip;
        /* the primal step and the explicit inverse's rank-one update */
        double xq = value(s, q), theta_p = (s->xB[r] - bound) / aq[r];
        for (int i = 0; i < m; i++) s->xB[i] -= theta_p * aq[i];
        s->xB[r] = xq + theta_p;
        double *pr = s->Binv + (size_t)r * m, piv = aq[r];
        for (int e = 0; e < m; e++) pr[e] /= piv;
        for (int i = 0; i < m; i++) {
            double f = aq[i];
            if (i == r || f == 0.0) continue;
            double *row = s->Binv + (size_t)i * m;
            for (int e = 0; e < m; e++) row[e] -= f * pr[e];
        }
        s->basic[r] = q;
        s->pos[q] = r;
        s->pos[p] = -1;
        s->upper[p] = sigma > 0;
        s->updates++;
        /* the dual step; a reduced cost then on its wrong side by at most TOL_D is set to 0, beyond it flips */
        double theta_d = s->d[q] / alpha[q], *d = s->d;
        for (int j = 0; j < nt; j++) d[j] -= theta_d * alpha[j];
        d[q] = 0.0;
        d[p] = -theta_d;
        int nfix = 0;
        for (int i = 0; i < m; i++) s->col[i] = 0.0;
        for (int j = 0; j < nt; j++) {
            if (!((s->upper[j] ? d[j] > 0.0 : d[j] < 0.0) && movable(s, j))) continue;
            if (fabs(d[j]) <= TOL_D) { d[j] = 0.0; s->stats[S_CLAMPS]++; continue; }
            add_column(s, s->col, j, s->upper[j] ? s->lo[j] - s->hi[j] : s->hi[j] - s->lo[j]);
            s->upper[j] ^= 1;
            nfix++;
        }
        if (nfix) primal_move(s, s->col);
        s->stats[S_FIXUPS] += nfix;
        if (s->updates >= REFACTOR) {
            if (refactor(s) < 0) return stop(s, it, TROUBLE);
            recompute(s);
        }
    }
}

/* ---------- the Python type ---------- */

static PyArrayObject *vector_arg(PyObject *o, npy_intp size, const char *what) {
    PyArrayObject *a = (PyArrayObject *)PyArray_FROMANY(o, NPY_DOUBLE, 1, 1, NPY_ARRAY_IN_ARRAY);
    if (!a) return NULL;
    if (PyArray_DIM(a, 0) != size) {
        PyErr_Format(PyExc_ValueError, "%s has %zd entries, not %zd", what, (Py_ssize_t)PyArray_DIM(a, 0), (Py_ssize_t)size);
        Py_DECREF(a);
        return NULL;
    }
    const double *v = PyArray_DATA(a);
    for (npy_intp i = 0; i < size; i++)
        if (!isfinite(v[i])) { PyErr_Format(PyExc_ValueError, "%s is not finite", what); Py_DECREF(a); return NULL; }
    return a;
}

/* The rows by density and the columns' nonzeros (see the struct); 0, or -1 without memory. */
static int structure(Dual *s) {
    int m = s->m, n = s->n, nnz = 0, snz = 0;
    s->dense = PyMem_Calloc(m, sizeof(int));
    s->sp_start = PyMem_Calloc(n + 1, sizeof(int));
    s->cs_start = PyMem_Calloc(n + 1, sizeof(int));
    if (!s->dense || !s->sp_start || !s->cs_start) return -1;
    unsigned char isdense[m];
    s->nd = 0;
    for (int i = 0; i < m; i++) {
        int k = 0;
        for (int j = 0; j < n; j++) k += s->A[(size_t)i * n + j] != 0.0;
        isdense[i] = 2 * k > n;
        if (isdense[i]) s->dense[s->nd++] = i;
        nnz += k;
        snz += isdense[i] ? 0 : k;
    }
    s->sp_row = PyMem_Calloc(snz ? snz : 1, sizeof(int));
    s->sp_val = alloc(snz);
    s->cs_row = PyMem_Calloc(nnz ? nnz : 1, sizeof(int));
    s->cs_val = alloc(nnz);
    if (!s->sp_row || !s->sp_val || !s->cs_row || !s->cs_val) return -1;
    int e = 0, f = 0;
    for (int j = 0; j < n; j++) {
        s->sp_start[j] = e;
        s->cs_start[j] = f;
        for (int i = 0; i < m; i++) {
            double a = s->A[(size_t)i * n + j];
            if (a == 0.0) continue;
            s->cs_row[f] = i; s->cs_val[f++] = a;
            if (!isdense[i]) { s->sp_row[e] = i; s->sp_val[e++] = a; }
        }
    }
    s->sp_start[n] = e;
    s->cs_start[n] = f;
    return 0;
}

static int Dual_init(Dual *s, PyObject *args, PyObject *kw) {
    static char *names[] = {"A", "b", "cost", "limit", NULL};
    PyObject *Ao, *bo, *co;
    int limit;
    if (!PyArg_ParseTupleAndKeywords(args, kw, "OOOi", names, &Ao, &bo, &co, &limit)) return -1;
    PyArrayObject *A = (PyArrayObject *)PyArray_FROMANY(Ao, NPY_DOUBLE, 2, 2, NPY_ARRAY_IN_ARRAY);
    if (!A) return -1;
    npy_intp m0 = PyArray_DIM(A, 0), n0 = PyArray_DIM(A, 1);
    if (m0 > MAXDIM || n0 > MAXDIM) {
        PyErr_Format(PyExc_ValueError, "A is %zd x %zd; at most %d x %d", (Py_ssize_t)m0, (Py_ssize_t)n0, MAXDIM, MAXDIM);
        Py_DECREF(A);
        return -1;
    }
    int m = (int)m0, n = (int)n0, nt = m + n;
    PyArrayObject *b = m > 0 && n > 0 && limit >= 0 ? vector_arg(bo, m, "b") : NULL;
    PyArrayObject *c = b ? vector_arg(co, n, "cost") : NULL;
    if (!c) {
        if (!PyErr_Occurred()) PyErr_SetString(PyExc_ValueError, "an empty A or a negative limit");
        Py_DECREF(A); Py_XDECREF(b);
        return -1;
    }
    release(s);
    s->m = m; s->n = n; s->nt = nt; s->limit = limit; s->updates = 0; s->iterations = 0;
    memset(s->stats, 0, sizeof s->stats);
    s->A = alloc((size_t)m * n); s->At = alloc((size_t)m * n); s->b = alloc(m); s->c = alloc(nt);
    s->lo = alloc(nt); s->hi = alloc(nt); s->d = alloc(nt); s->alpha = alloc(nt); s->Binv = alloc((size_t)m * m);
    s->B = alloc((size_t)m * 2 * m); s->xB = alloc(m); s->y = alloc(m); s->r = alloc(m); s->aq = alloc(m);
    s->col = alloc(m); s->g = alloc(n); s->blo = alloc(n); s->bhi = alloc(n); s->caa = alloc(nt); s->cdd = alloc(nt); s->ct = alloc(nt); s->ccap = alloc(nt);
    s->basic = PyMem_Calloc(m, sizeof(int)); s->pos = PyMem_Calloc(nt, sizeof(int)); s->cidx = PyMem_Calloc(2 * (size_t)nt, sizeof(int));
    s->upper = PyMem_Calloc(nt, 1); s->cpass = PyMem_Calloc(nt, 1);
    int ok = s->A && s->At && s->b && s->c && s->lo && s->hi && s->d && s->alpha && s->Binv && s->B && s->xB
             && s->y && s->r && s->aq && s->col && s->g && s->blo && s->bhi && s->caa && s->cdd && s->ct && s->ccap && s->basic && s->pos
             && s->cidx && s->upper && s->cpass;
    if (ok) {
        const double *Ad = PyArray_DATA(A), *bd = PyArray_DATA(b), *cd = PyArray_DATA(c);
        for (int i = 0; i < m; i++)
            for (int j = 0; j < n; j++) {
                double a = Ad[(size_t)i * n + j];
                ok &= isfinite(a);
                s->A[(size_t)i * n + j] = a;
                s->At[(size_t)j * m + i] = a;
            }
        memcpy(s->b, bd, m * sizeof(double));
        memcpy(s->c, cd, n * sizeof(double));       /* logicals cost 0 (calloc) */
        if (!ok) PyErr_SetString(PyExc_ValueError, "A is not finite");
        else if (structure(s) < 0) { ok = 0; PyErr_NoMemory(); }
        for (int j = 0; j < n; j++) { s->lo[j] = 0.0; s->hi[j] = 1.0; s->pos[j] = -1; }
        for (int i = 0; i < m; i++) {                /* the slack basis: every logical basic, fixed at 0 */
            s->lo[n + i] = s->hi[n + i] = 0.0;
            s->basic[i] = n + i;
            s->pos[n + i] = i;
            s->Binv[(size_t)i * m + i] = 1.0;
        }
        if (ok) fresh(s);
    } else {
        PyErr_NoMemory();
    }
    Py_DECREF(A); Py_DECREF(b); Py_DECREF(c);
    if (!ok) { release(s); return -1; }
    return 0;
}

static int ready(Dual *s) {
    if (s->A) return 1;
    PyErr_SetString(PyExc_RuntimeError, "Dual was not initialized");
    return 0;
}

static PyObject *Dual_rhs(Dual *s, PyObject *bo) {
    if (!ready(s)) return NULL;
    PyArrayObject *b = vector_arg(bo, s->m, "b");
    if (!b) return NULL;
    memcpy(s->b, PyArray_DATA(b), s->m * sizeof(double));
    Py_DECREF(b);
    primal(s);
    Py_RETURN_NONE;
}

/* The snapshot's bytes, the state: int32 m, nt, updates; int32 basic[m]; uint8 upper[nt]; then doubles (unaligned):
   Binv[m m], xB[m], d[nt], lo[n], hi[n]. */
static size_t snapshot_size(const Dual *s) {
    return 12 + 4 * (size_t)s->m + (size_t)s->nt + 8 * ((size_t)s->m * s->m + s->m + s->nt + 2 * (size_t)s->n);
}

static PyObject *Dual_snapshot(Dual *s, PyObject *unused) {
    if (!ready(s)) return NULL;
    PyObject *out = PyBytes_FromStringAndSize(NULL, (Py_ssize_t)snapshot_size(s));
    if (!out) return NULL;
    char *p = PyBytes_AS_STRING(out);
    int32_t head[3] = {s->m, s->nt, s->updates};
    memcpy(p, head, 12); p += 12;
    for (int i = 0; i < s->m; i++) { int32_t v = s->basic[i]; memcpy(p, &v, 4); p += 4; }
    memcpy(p, s->upper, s->nt); p += s->nt;
    memcpy(p, s->Binv, 8 * (size_t)s->m * s->m); p += 8 * (size_t)s->m * s->m;
    memcpy(p, s->xB, 8 * (size_t)s->m); p += 8 * (size_t)s->m;
    memcpy(p, s->d, 8 * (size_t)s->nt); p += 8 * (size_t)s->nt;
    memcpy(p, s->lo, 8 * (size_t)s->n); p += 8 * (size_t)s->n;
    memcpy(p, s->hi, 8 * (size_t)s->n);
    return out;
}

/* Restore a snapshot: every part is checked on the snapshot's own bytes first (shape, a basis of distinct variables,
   bound flags of 0 or 1, finite numbers, lo <= hi), and only then copied in; a refused snapshot changes nothing.
   cpass, scratch between solves, marks the basic variables seen. */
static int restore(Dual *s, PyObject *snap) {
    if (!PyBytes_Check(snap) || (size_t)PyBytes_GET_SIZE(snap) != snapshot_size(s)) {
        PyErr_SetString(PyExc_ValueError, "not a snapshot of this Dual's size");
        return -1;
    }
    int m = s->m, n = s->n, nt = s->nt;
    const char *p = PyBytes_AS_STRING(snap), *pb = p + 12, *pu = pb + 4 * (size_t)m, *pd = pu + nt;
    int32_t head[3];
    memcpy(head, p, 12);
    int ok = head[0] == m && head[1] == nt && head[2] >= 0;
    memset(s->cpass, 0, nt);
    for (int i = 0; ok && i < m; i++) {
        int32_t v;
        memcpy(&v, pb + 4 * (size_t)i, 4);
        ok = v >= 0 && v < nt && !s->cpass[v];
        if (ok) s->cpass[v] = 1;
    }
    for (int j = 0; ok && j < nt; j++) ok = (unsigned char)pu[j] <= 1;
    size_t nd = (size_t)m * m + m + nt + 2 * (size_t)n;
    for (size_t k = 0; ok && k < nd; k++) {
        double v;
        memcpy(&v, pd + 8 * k, 8);
        ok = isfinite(v);
    }
    const char *plo = pd + 8 * ((size_t)m * m + m + nt), *phi = plo + 8 * (size_t)n;
    for (int j = 0; ok && j < n; j++) {
        double l, h;
        memcpy(&l, plo + 8 * (size_t)j, 8);
        memcpy(&h, phi + 8 * (size_t)j, 8);
        ok = l <= h;
    }
    if (!ok) {
        PyErr_SetString(PyExc_ValueError, "a snapshot that is not a state of this Dual");
        return -1;
    }
    for (int j = 0; j < nt; j++) s->pos[j] = -1;
    for (int i = 0; i < m; i++) {
        int32_t v;
        memcpy(&v, pb + 4 * (size_t)i, 4);
        s->basic[i] = v;
        s->pos[v] = i;
    }
    memcpy(s->upper, pu, nt);
    memcpy(s->Binv, pd, 8 * (size_t)m * m); pd += 8 * (size_t)m * m;
    memcpy(s->xB, pd, 8 * (size_t)m); pd += 8 * (size_t)m;
    memcpy(s->d, pd, 8 * (size_t)nt); pd += 8 * (size_t)nt;
    memcpy(s->lo, pd, 8 * (size_t)n); pd += 8 * (size_t)n;
    memcpy(s->hi, pd, 8 * (size_t)n);
    s->updates = head[2];
    return 0;
}

/* A basis from HiGHS's status codes (int8, n + m: 0 lower, 1 basic, 2 upper, 3 zero, 4 nonbasic), checked and inverted
   in scratch space (the basic list in cidx, the inverse in B) before anything of the state changes; a refused or
   singular basis changes nothing. */
static PyObject *Dual_load(Dual *s, PyObject *so) {
    if (!ready(s)) return NULL;
    PyArrayObject *a = (PyArrayObject *)PyArray_FROMANY(so, NPY_INT8, 1, 1, NPY_ARRAY_IN_ARRAY);
    if (!a) return NULL;
    if (PyArray_DIM(a, 0) != s->nt) { Py_DECREF(a); PyErr_SetString(PyExc_ValueError, "not n + m status codes"); return NULL; }
    const int8_t *st = PyArray_DATA(a);
    int count = 0, m = s->m, ok = 1;
    for (int j = 0; j < s->nt; j++) {
        ok &= st[j] >= 0 && st[j] <= 4;
        count += st[j] == 1;
    }
    if (!ok || count != m) { Py_DECREF(a); PyErr_SetString(PyExc_ValueError, "not m basic variables among codes 0 to 4"); return NULL; }
    int k = 0;
    for (int j = 0; j < s->nt; j++)
        if (st[j] == 1) s->cidx[k++] = j;
    if (invert(s, s->cidx) < 0) { Py_DECREF(a); PyErr_SetString(PyExc_ValueError, "a singular basis"); return NULL; }
    for (int j = 0; j < s->nt; j++) { s->pos[j] = -1; s->upper[j] = st[j] == 2; }
    for (int i = 0; i < m; i++) { s->basic[i] = s->cidx[i]; s->pos[s->cidx[i]] = i; }
    Py_DECREF(a);
    for (int i = 0; i < m; i++) memcpy(s->Binv + (size_t)i * m, s->B + (size_t)i * 2 * m + m, m * sizeof(double));
    s->updates = 0;
    s->stats[S_REFACTORS]++;
    fresh(s);
    Py_RETURN_NONE;
}

/* out[0..n) = the n numbers of the sequence o, read from a private tuple of its items (so that no __float__ can change
   what is read): ints through PyLong_AsDouble, others through PyFloat_AsDouble; ValueError for a wrong length, a
   conversion error or a number that is not finite. */
static int read_box(PyObject *o, double *out, int n, const char *what) {
    PyObject *t = PySequence_Tuple(o);
    if (!t) return -1;
    int ok = PyTuple_GET_SIZE(t) == n;
    for (int j = 0; ok && j < n; j++) {
        PyObject *item = PyTuple_GET_ITEM(t, j);
        double v = PyLong_CheckExact(item) ? PyLong_AsDouble(item) : PyFloat_AsDouble(item);
        ok = !(v == -1.0 && PyErr_Occurred()) && isfinite(v);
        out[j] = v;
    }
    Py_DECREF(t);
    if (!ok) {
        PyErr_Clear();
        PyErr_Format(PyExc_ValueError, "%s is not %d finite numbers", what, n);
        return -1;
    }
    return 0;
}

static PyObject *Dual_solve(Dual *s, PyObject *args) {
    PyObject *loo, *hio, *snap = Py_None;
    if (!ready(s) || !PyArg_ParseTuple(args, "OO|O", &loo, &hio, &snap)) return NULL;
    int n = s->n;
    double *box = PyMem_Malloc(2 * (size_t)n * sizeof(double));      /* private: no callback can free it */
    if (!box) return PyErr_NoMemory();
    int ok = read_box(loo, box, n, "lo") == 0 && read_box(hio, box + n, n, "hi") == 0;
    if (ok && !(s->A && s->n == n)) {                    /* a __float__ may have re-initialized this Dual */
        PyErr_SetString(PyExc_ValueError, "the Dual changed while its box was read");
        ok = 0;
    }
    for (int j = 0; ok && j < n; j++)
        if (!(box[j] <= box[n + j])) { PyErr_SetString(PyExc_ValueError, "a lower bound above its upper bound"); ok = 0; }
    ok = ok && (snap == Py_None || restore(s, snap) == 0);
    if (ok) {
        memcpy(s->blo, box, n * sizeof(double));
        memcpy(s->bhi, box + n, n * sizeof(double));
    }
    PyMem_Free(box);
    if (!ok) return NULL;
    move(s, s->blo, s->bhi);
    s->stats[S_SOLVES]++;
    int status = run(s);
    if (status == BROKEN) {
        PyErr_SetString(PyExc_AssertionError, "_fastlp: no entering variable in a nonempty ratio test, on finite numbers");
        return NULL;
    }
    PyObject *vec = Py_None;
    if (status == OPTIMAL || status == INFEASIBLE) {
        npy_intp size = status == OPTIMAL ? s->n : s->m;
        vec = PyArray_SimpleNew(1, &size, NPY_DOUBLE);
        if (!vec) return NULL;
        double *v = PyArray_DATA((PyArrayObject *)vec);
        for (npy_intp j = 0; j < size; j++)
            v[j] = status == INFEASIBLE ? s->y[j] : (s->pos[j] >= 0 ? s->xB[s->pos[j]] : value(s, (int)j));
    } else {
        Py_INCREF(vec);
    }
    PyObject *out = PyTuple_Pack(2, STATUS[status], vec);
    Py_DECREF(vec);
    return out;
}

static PyObject *Dual_stats(Dual *s, void *unused) {
    PyObject *dict = PyDict_New();
    for (int i = 0; dict && i < S_N; i++) {
        PyObject *v = PyLong_FromLongLong(s->stats[i]);
        if (!v || PyDict_SetItemString(dict, STAT_NAMES[i], v) < 0) { Py_XDECREF(v); Py_DECREF(dict); return NULL; }
        Py_DECREF(v);
    }
    return dict;
}

static PyObject *Dual_iterations(Dual *s, void *unused) { return PyLong_FromLong(s->iterations); }
static PyObject *Dual_updates(Dual *s, void *unused) { return PyLong_FromLong(s->updates); }

static PyMethodDef Dual_methods[] = {
    {"rhs", (PyCFunction)Dual_rhs, METH_O, "rhs(b): set the right-hand sides"},
    {"solve", (PyCFunction)Dual_solve, METH_VARARGS, "solve(lo, hi, snapshot=None) -> (status, vector)"},
    {"snapshot", (PyCFunction)Dual_snapshot, METH_NOARGS, "snapshot() -> bytes: the basis and its explicit inverse"},
    {"load", (PyCFunction)Dual_load, METH_O, "load(codes): a basis from HiGHS's status codes, refactored"},
    {NULL, NULL, 0, NULL}};

static PyGetSetDef Dual_getset[] = {
    {"stats", (getter)Dual_stats, NULL, "counters", NULL},
    {"iterations", (getter)Dual_iterations, NULL, "the last solve's iterations", NULL},
    {"updates", (getter)Dual_updates, NULL, "updates of the explicit inverse since its refactorization", NULL},
    {NULL, NULL, NULL, NULL, NULL}};

static PyTypeObject DualType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "_fastlp.Dual",
    .tp_basicsize = sizeof(Dual),
    .tp_dealloc = (destructor)Dual_dealloc,
    .tp_flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,
    .tp_doc = "the dense bounded dual simplex (see _fastlp.c)",
    .tp_methods = Dual_methods,
    .tp_getset = Dual_getset,
    .tp_init = (initproc)Dual_init,
    .tp_new = PyType_GenericNew,
};

static struct PyModuleDef module = {PyModuleDef_HEAD_INIT, "_fastlp", "the dense bounded dual simplex", -1,
                                    NULL, NULL, NULL, NULL, NULL};

PyMODINIT_FUNC PyInit__fastlp(void) {
    import_array();
    if (PyType_Ready(&DualType) < 0) return NULL;
    const char *names[4] = {"Optimal", "Infeasible", "Iteration limit", "Trouble"};
    for (int i = 0; i < 4; i++)
        if (!(STATUS[i] = PyUnicode_InternFromString(names[i]))) return NULL;
    PyObject *mod = PyModule_Create(&module);
    if (!mod) return NULL;
    Py_INCREF(&DualType);
    if (PyModule_AddObject(mod, "Dual", (PyObject *)&DualType) < 0) { Py_DECREF(&DualType); Py_DECREF(mod); return NULL; }
    return mod;
}
