(* 240 in L_11?  Case-split search in Mathematica.  UNTESTED by Claude (no Mathematica in its sandbox).
   Stage 1 (exact): the 10 cases (counts mod 4 and mod 7, from a complete enumeration) are checked for an integer
            solution of the 11 moment equations plus the counts. Expect 8 of 10 to have none (Python found the same).
   Stage 2 (exact): each surviving case is split by its counts mod 8; sub-cases with no integer solution are dropped.
   Stage 3 (search): each remaining sub-case is searched with LinearOptimization in lattice coordinates
            (x = x0 + y.K, K an LLL-reduced basis of the integer kernel), time-limited, with a log line and an ETA
            after every sub-case. Results are checkpointed in mma240_state.m; rerunning skips finished sub-cases.
   A control first checks the whole pipeline on the known order-10 witness, including whether the search can find it. *)

n = 240; tSub = 300;          (* seconds per sub-case in stage 3 *)
logFile = FileNameJoin[{Directory[], "mma240.log"}];
stateFile = FileNameJoin[{Directory[], "mma240_state.m"}];
logLine[s_String] := Module[{line = DateString["ISODateTime"] <> "  " <> s, st},
   Print[line]; st = OpenAppend[logFile]; WriteLine[st, line]; Close[st]];
size[M_, r_] := Length[Range[r, n - 1, M]];
momentRows[m_] := Table[2 Binomial[p - n/2, k], {k, 0, m - 1}, {p, 0, n - 1}];
momentRhs[m_] := Table[Sum[Binomial[p - n/2, k], {p, 0, n - 1}], {k, 0, m - 1}];
countRows[M_] := Table[Boole[Mod[p, M] == r], {r, 0, M - 1}, {p, 0, n - 1}];
countRhs[M_, d_] := Table[(size[M, r] + d[[r + 1]])/2, {r, 0, M - 1}];

(* integer solutions of A.x == b:  particular[b] (or $Failed) and an LLL-reduced kernel basis *)
integerSystem[A_] := Module[{u, h, rk, hT, pinv},
   {u, h} = HermiteDecomposition[Transpose[A]];
   rk = MatrixRank[A];
   hT = Transpose[h[[1 ;; rk]]];
   pinv = Inverse[Transpose[hT] . hT] . Transpose[hT];
   <|"particular" -> Function[b, Module[{w = pinv . b},
        If[VectorQ[w, IntegerQ] && hT . w == b, Transpose[u[[1 ;; rk]]] . w, $Failed]]],
     "kernel" -> LatticeReduce[u[[rk + 1 ;;]]]|>];

SetAttributes[yy, NHoldAll];
searchSub[x0_, K_, tlim_] := Module[{y = Array[yy, Length[K]], x, res},
   x = x0 + y . K;
   res = TimeConstrained[Quiet[LinearOptimization[0, N[Join[Thread[0 <= x], Thread[x <= 1]]],
        Map[Element[#, Integers] &, y], "PrimalMinimizer"]], tlim, $TimedOut];
   Which[res === $TimedOut, {"OPEN", None},
    VectorQ[res, NumberQ], {"FEASIBLE", x0 + Round[res] . K},
    True, {"INFEASIBLE", ToString[Head[res]]}]];
exactOrder[a_] := Module[{k = 0}, While[Sum[a[[i]] (i - 1)^k, {i, Length[a]}] == 0, k++]; k];
sub8[{d4_, d7_}, ordr_, sys_] := Module[{c4 = countRhs[4, d4], base = Join[momentRhs[ordr], countRhs[7, d7]], cands},
   cands = Select[Tuples[Range[0, 30], 4], AllTrue[Range[4], Function[r, 0 <= c4[[r]] - #[[r]] <= 30]] &];
   Select[Map[Join[#, c4 - #] &, cands], sys["particular"][Join[base, #]] =!= $Failed &]];

(* ---------- control on the known order-10 witness ---------- *)
lp[h_, m_] := With[{l = 2 IntegerDigits[FromDigits[h, 16], 2, 4 StringLength[h]] - 1}, Join[l, (-1)^m Reverse[l]]];
wit = lp["C394E65AB989457A86B7D0D921636E", 10]; wx = (wit + 1)/2;
wd4 = Table[Total[wit[[r + 1 ;; ;; 4]]], {r, 0, 3}]; wd7 = Table[Total[wit[[r + 1 ;; ;; 7]]], {r, 0, 6}];
wc8 = Table[Total[wx[[r + 1 ;; ;; 8]]], {r, 0, 7}];
sys10 = integerSystem[Join[momentRows[10], countRows[7], countRows[8]]];
x0w = sys10["particular"][Join[momentRhs[10], countRhs[7, wd7], wc8]];
logLine["control: witness order " <> ToString[exactOrder[wit]] <> " (expect 10); its sub-case has an integer solution: " <>
   ToString[x0w =!= $Failed] <> "; witness lies in x0 + K Z: " <>
   ToString[x0w =!= $Failed && VectorQ[Quiet@LinearSolve[Transpose[sys10["kernel"]], wx - x0w], IntegerQ]]];
ctrl = searchSub[x0w, sys10["kernel"], 600];
logLine["search control (find an order-10 solution in the witness's sub-case within 600 s): " <> ctrl[[1]] <>
   If[ctrl[[1]] === "FEASIBLE", ", exact order " <> ToString[exactOrder[2 ctrl[[2]] - 1]], ""]];

(* ---------- stage 1 ---------- *)
cases = {{{-32, -32, 32, 32}, {7, -7, 28, 14, 0, -14, -28}}, {{-32, 0, 32, 0}, {7, -7, 28, 14, 0, -14, -28}},
   {{-32, 32, 32, -32}, {7, -7, 28, 14, 0, -14, -28}}, {{0, -32, 0, 32}, {7, -7, 28, 14, 0, -14, -28}},
   {{0, 0, 0, 0}, {7, -7, 28, 14, 0, -14, -28}}, {{0, 32, 0, -32}, {7, -7, 28, 14, 0, -14, -28}},
   {{32, -32, -32, 32}, {7, -7, 28, 14, 0, -14, -28}}, {{32, 0, -32, 0}, {7, -7, 28, 14, 0, -14, -28}},
   {{32, 32, -32, -32}, {7, -7, 28, 14, 0, -14, -28}}, {{0, 0, 0, 0}, {35, 35, -14, -14, -14, -14, -14}}};
sys1 = integerSystem[Join[momentRows[11], countRows[4], countRows[7]]];
surv = Select[cases, sys1["particular"][Join[momentRhs[11], countRhs[4, #[[1]]], countRhs[7, #[[2]]]]] =!= $Failed &];
logLine["stage 1: " <> ToString[Length[cases] - Length[surv]] <> " of 10 cases have no integer solution (expect 8); remaining: " <> ToString[surv]];

(* ---------- stage 2 ---------- *)
sys2 = integerSystem[Join[momentRows[11], countRows[7], countRows[8]]];
subs = Flatten[Table[{cs, c8}, {cs, surv}, {c8, sub8[cs, 11, sys2]}], 1];
logLine["stage 2: " <> ToString[Length[subs]] <> " sub-cases (counts mod 8) admit an integer solution"];

(* ---------- stage 3 ---------- *)
state = If[FileExistsQ[stateFile], Get[stateFile], <||>];
K2 = sys2["kernel"]; t0 = AbsoluteTime[]; nDone = 0; tSpent = 0.;
Do[
  Module[{key = ToString[s], x0, r, dt, left},
   If[KeyExistsQ[state, key] && state[key] =!= "OPEN", Continue[]];
   x0 = sys2["particular"][Join[momentRhs[11], countRhs[7, s[[1, 2]]], s[[2]]]];
   dt = First@AbsoluteTiming[r = searchSub[x0, K2, tSub]];
   state[key] = r[[1]]; Put[state, stateFile];
   nDone++; tSpent += dt;
   left = Count[subs, t_ /; ! (KeyExistsQ[state, ToString[t]] && state[ToString[t]] =!= "OPEN")];
   logLine["sub-case " <> key <> ": " <> r[[1]] <> " (" <> ToString[Round[dt]] <> " s); remaining " <> ToString[left] <>
     ", ETA " <> ToString[Round[left tSpent/nDone/60]] <> " min" <> If[r[[1]] === "INFEASIBLE", " [solver returned " <> r[[2]] <> "]", ""]];
   If[r[[1]] === "FEASIBLE",
    logLine["*** candidate witness: exact order " <> ToString[exactOrder[2 r[[2]] - 1]] <> " ***"];
    Put[r[[2]], FileNameJoin[{Directory[], "mma240_witness.m"}]]; Abort[]]],
  {s, subs}];
logLine["done: " <> ToString[Count[Values[state], "INFEASIBLE"]] <> " infeasible, " <> ToString[Count[Values[state], "OPEN"]] <> " open, of " <> ToString[Length[subs]]];
