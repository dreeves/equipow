(* lattice_search.wl

   Written by Claude (Claude Opus 5.5, an AI model made by Anthropic) on 2026-10-14, for Stan Wagon, at Danny Reeves's
   request.  The code and every comment in this file are Claude's; no human has reviewed them.

   It is the lattice method behind Claude's examples on https://equipow.dreev.es (the section "How Claude found its
   examples" explains it), cut down to what runs in plain Mathematica: LatticeReduce (LLL) where Claude's runs used
   fplll's BKZ-20, and the compiled enumeration below where they used fplll's.

   The problem: a sequence f_0, ..., f_(n-1) of signs +1 and -1 has order m when sum_i f_i i^k = 0 for k = 0, ..., m-1.
   s = 1 looks for symmetric f (f_(n-1-i) = f_i), s = -1 for antisymmetric f (f_(n-1-i) = -f_i), and s = 0 for any f.

   The method, in one paragraph: the free signs a (h of them: n/2, or n when s = 0) satisfy linear equations A.a = 0.
   With a = 2x - 1, the integer solutions x form a coset x0 + K of the integer kernel K of A, so a ranges over the coset
   t + 2K, t = 2 x0 - 1.  Every vector of that coset has odd entries, so its squared length is at least h, with equality
   exactly when every entry is +1 or -1; any other vector of the coset has squared length at least h + 8.  So the
   solutions are exactly the shortest vectors of the coset, and finding them is a closest-vector problem: enumerate the
   lattice vectors v of 2K with |t + v|^2 <= h, after reducing the basis of 2K.  Without pruning, the enumeration is
   exhaustive: it finds every solution of the given symmetry.  With pruning it searches only part of the tree, finding
   each solution with some probability, so it is rerun on rerandomized bases.

   Usage:
     Get["lattice_search.wl"]
     r = latticeSearch[48, 6, 1]                         (* a symmetric sequence of length 48 and order 6 *)
     r["solutions"]                                      (* the sequences found, as lists of +1 and -1 *)
     r["sets"]                                           (* each as the half of {0, ..., n-1} that contains 0 *)
     latticeSearch[32, 5, 0, "Want" -> Infinity]         (* every sequence of length 32 and order 5 *)
     latticeSearch[144, 8, 1, "Pruning" -> 0.1]          (* pruned *)

   Options:
     "Want"      stop once this many distinct sequences are found (Infinity: all of them, which needs no pruning)
     "Pruning"   delta: the enumeration keeps a partial sum over the last j of the d Gram-Schmidt coordinates only
                 while it is at most Min[1, delta + j/d] times the radius^2.  1 (the default) or more prunes nothing;
                 0 is the linear pruning of Gama, Nguyen and Regev (Eurocrypt 2010), which is too tight here: a
                 solution's partial sums tend to run a little above j/d times the radius^2.
     "MaxNodes"  the most enumeration nodes per trial (one trial = one rerandomized basis)
     "TimeLimit" seconds; checked between trials, so one trial can overrun it
     "Seed"      for SeedRandom

   The result is an association: "solutions" (sorted; a sequence and its negation both appear, as both have the order),
   "sets" (each solution as the half of the partition that contains 0, numbered from 0, as in the sets on
   equipow.dreev.es), "complete" (True when the enumeration ran unpruned to the end, so "solutions" holds every sequence of that symmetry
   and order at least m), "dimension" (d, the lattice's dimension, or Missing["NoIntegerSolution"] when the equations
   have no integer solution, so no sequence exists), "trials", "nodes" and "seconds".  Every sequence returned has been
   checked to have order at least m with exact integer power sums.

   Only latticeSearch and latticeSystem are exported (from the context LatticeSearch`); the helpers live in
   LatticeSearch`Private`, so they cannot clash with the names of other packages. *)

BeginPackage["LatticeSearch`"];
latticeSearch::usage = "latticeSearch[n, m, s, options] searches for sequences of n signs of order at least m, symmetric (s = 1), antisymmetric (s = -1) or either (s = 0); see the comment at the top of lattice_search.wl.";
latticeSystem::usage = "latticeSystem[n, m, s] gives the lattice latticeSearch searches: <|\"P\", \"B\", \"t\", \"R2\"|>, or Missing[\"NoIntegerSolution\"].";
Begin["`Private`"];

latticeSearch::fail = "Check failed: ``";
check[ok_, what_] := If[ok =!= True, Message[latticeSearch::fail, what]; Abort[]];

(* the order of a sequence of +1 and -1: the number of leading power sums sum_i f_i i^k, k = 0, 1, ..., that are 0
   (positions are numbered from 1 here, which gives the same order: the order does not change under translation) *)
order[f_List] := Module[{k = 0, x = Range[Length[f]]}, While[f . (x^k) == 0, k++]; k];

(* the half of the partition that contains 0, numbered from 0, as in the sets on equipow.dreev.es *)
half[f_List] := Flatten[Position[f, First[f]]] - 1;

(* every integer x with M.x == b, as {x0, K}: one solution x0 and a basis K (as rows) of the integer kernel of M, from
   the Hermite decomposition u.Transpose[M] == hm (u unimodular, the nonzero rows of hm first); or
   Missing["NoIntegerSolution"] *)
integerSolve[M_, b_] := Module[{u, hm, rk, z},
   {u, hm} = HermiteDecomposition[Transpose[M]];
   rk = Count[hm, row_ /; AnyTrue[row, # != 0 &]];
   check[hm[[rk + 1 ;;]] == 0 hm[[rk + 1 ;;]], "the zero rows of the Hermite form come last"];
   z = LinearSolve[Transpose[hm[[1 ;; rk]]], b];
   check[Transpose[hm[[1 ;; rk]]] . z == b, "the equations have a rational solution"];
   If[VectorQ[z, IntegerQ], {z . u[[1 ;; rk]], u[[rk + 1 ;;]]}, Missing["NoIntegerSolution"]]];

(* The lattice of the search: P maps the h free signs a to the sequence f = P.a; the reduced basis B (rows) of 2K;
   the short coset representative t; and R2, the squared length of the part inside the span of B that every vector of
   t + 2K with entries +-1 has.  The equations are the power sums with positions centered on 0 and doubled,
   sum_i f_i (2i - n + 1)^k = 0 for k < m, which have the same solutions (the power sums of any shift and scaling of
   the positions vanish together), with smaller integers.  Or Missing["NoIntegerSolution"]. *)
latticeSystem[n_Integer, m_Integer, s_Integer] := Module[{P, h, A, sol, x0, K, B, G, t, proj},
   check[EvenQ[n] && n >= 2 && m >= 1 && MemberQ[{-1, 0, 1}, s], "n is even, m >= 1, and s is -1, 0 or 1"];
   P = If[s == 0, IdentityMatrix[n], Join[IdentityMatrix[n/2], s Reverse[IdentityMatrix[n/2]]]];
   h = Length[First[P]];
   A = Table[(2 i - n + 1)^k, {k, 0, m - 1}, {i, 0, n - 1}] . P;
   sol = integerSolve[2 A, A . ConstantArray[1, h]];          (* A.(2x - 1) == 0, that is, 2A.x == A.1 *)
   If[MissingQ[sol], Return[sol]];
   {x0, K} = sol;
   check[Length[K] >= 1, "the lattice has dimension at least 1"];
   B = 2 LatticeReduce[K];
   check[Length[B] == Length[K], "LatticeReduce kept every basis vector"];
   G = B . Transpose[B];
   t = 2 x0 - 1;
   t = t - Round[LinearSolve[G, B . t]] . B;                  (* shorter, by rounding its coordinates in the basis B *)
   proj = LinearSolve[G, B . t] . B;                           (* t's projection on the span of B, exactly *)
   <|"P" -> P, "B" -> B, "t" -> t, "R2" -> h - (t - proj) . (t - proj)|>];

(* Schnorr-Euchner enumeration of the integer vectors c with |t + c.B|^2 <= the radius^2, from the Gram-Schmidt data
   of B: rr[[i]] = |b*_i|^2, mu[[j, i]] = <b_j, b*_i>/|b*_i|^2 and tau[[i]] = <t, b*_i>/|b*_i|^2.  It fixes c[[d]],
   c[[d-1]], ..., c[[1]] in turn; at level i the partial sum l of (c_j - center_j)^2 rr[[j]] over j >= i must be at most
   bnd[[i]] (the pruning: bnd[[1]] is the whole radius^2), and the c[[i]] at a level are tried in zigzag order from the
   nearest integer to the center out, so the first that fails ends the level.  The first row of the result is {number
   of vectors found, nodes visited, 1 if the enumeration ran to the end and 0 if it stopped at maxSol or maxNodes},
   padded with 0s; each further row is three 0s and then a c found. *)
enumerate = Compile[{{rr, _Real, 1}, {mu, _Real, 2}, {tau, _Real, 1}, {bnd, _Real, 1}, {maxSol, _Integer},
    {maxNodes, _Integer}},
   Module[{d = Length[rr], i = 0, j = 0, c, cen, dx, ddx, l, sols, nsol = 0, nodes = 0, diff = 0., li = 0., s = 0.},
    c = Table[0, {d}]; dx = Table[0, {d}]; ddx = Table[0, {d}];
    cen = Table[0., {d}]; l = Table[0., {d + 1}];
    sols = Table[0, {maxSol + 1}, {d + 3}];
    i = d;
    cen[[d]] = -tau[[d]]; c[[d]] = Round[cen[[d]]];
    dx[[d]] = If[cen[[d]] >= c[[d]], 1, -1]; ddx[[d]] = dx[[d]];
    While[i <= d && nodes < maxNodes && nsol < maxSol,
     nodes++;
     diff = c[[i]] - cen[[i]];
     li = l[[i + 1]] + diff*diff*rr[[i]];
     If[li <= bnd[[i]],
      If[i == 1,
       nsol++;
       For[j = 1, j <= d, j++, sols[[nsol + 1, j + 3]] = c[[j]]];
       c[[1]] += dx[[1]]; ddx[[1]] = -ddx[[1]]; dx[[1]] = ddx[[1]] - dx[[1]];,
       l[[i]] = li; i--;
       s = tau[[i]];
       For[j = i + 1, j <= d, j++, s += mu[[j, i]]*c[[j]]];
       cen[[i]] = -s; c[[i]] = Round[cen[[i]]];
       dx[[i]] = If[cen[[i]] >= c[[i]], 1, -1]; ddx[[i]] = dx[[i]];];,
      i++;
      If[i <= d, c[[i]] += dx[[i]]; ddx[[i]] = -ddx[[i]]; dx[[i]] = ddx[[i]] - dx[[i]];];]];
    sols[[1, 1]] = nsol; sols[[1, 2]] = nodes; sols[[1, 3]] = If[i > d, 1, 0];
    Take[sols, nsol + 1]]];

Options[latticeSearch] = {"Want" -> 1, "Pruning" -> 1, "MaxNodes" -> 10^7, "TimeLimit" -> 60, "Seed" -> 1};
latticeSearch[n_Integer, m_Integer, s_Integer, OptionsPattern[]] := Module[
   {start = AbsoluteTime[], want = OptionValue["Want"], delta = OptionValue["Pruning"], sys, B, t, P, d, bnd,
    found = {}, trials = 0, nodes = 0, complete = False, cap, Bp, q, r, res, pts, fs},
   SeedRandom[OptionValue["Seed"]];
   sys = latticeSystem[n, m, s];
   If[MissingQ[sys], Return[<|"solutions" -> {}, "sets" -> {}, "complete" -> True, "dimension" -> sys,
      "trials" -> 0, "nodes" -> 0, "seconds" -> AbsoluteTime[] - start|>]];
   {P, B, t} = sys /@ {"P", "B", "t"};
   d = Length[B];
   bnd = N[(sys["R2"] + 1/2) Table[Min[1, delta + (d - i + 1)/d], {i, d}]];   (* + 1/2: room for rounding error *)
   While[Length[found] < want && ! complete && AbsoluteTime[] - start < OptionValue["TimeLimit"],
    trials++;
    (* a random unimodular change of basis, then LLL again: the rows shuffled, then a unit lower triangular matrix
       (which alone would leave the Gram-Schmidt vectors, and so LLL's result, unchanged) *)
    Bp = LatticeReduce[(IdentityMatrix[d] + LowerTriangularize[RandomInteger[{-1, 1}, {d, d}], -1]) . RandomSample[B]];
    check[Length[Bp] == d, "LatticeReduce kept every basis vector"];
    {q, r} = QRDecomposition[Transpose[N[Bp]]];                 (* b*_i = r[[i, i]] q[[i]] *)
    cap = Min[want - Length[found], 10^4];
    res = enumerate[Diagonal[r]^2, Transpose[r/Diagonal[r]], (q . N[t])/Diagonal[r], bnd, cap,
      OptionValue["MaxNodes"]];
    nodes += res[[1, 2]];
    pts = (t + # . Bp) & /@ res[[2 ;;, 4 ;;]];
    check[AllTrue[Flatten[pts], Abs[#] == 1 &], "every vector found has entries +1 and -1"];
    fs = (P . #) & /@ pts;
    check[AllTrue[fs, order[#] >= m &], "every sequence found has order at least m"];
    found = Union[found, fs];
    complete = delta >= 1 && res[[1, 3]] == 1 && res[[1, 1]] < cap];
   <|"solutions" -> found, "sets" -> half /@ found, "complete" -> complete, "dimension" -> d, "trials" -> trials,
    "nodes" -> nodes, "seconds" -> AbsoluteTime[] - start|>];

End[];
EndPackage[];
