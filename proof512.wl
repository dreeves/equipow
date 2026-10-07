(* TODO: every message this script prints is quoted as Claude: "..."; each says which check runs, what value is expected, and the final verdict *)
(* proof512.wl: exact check of the computational steps in proof512.txt (512 and 496 are not in L_10). *)
(* Run with:  wolframscript -file proof512.wl   (a few seconds), or Get it in a fresh kernel.
   All arithmetic is exact integer arithmetic. The last line printed is the verdict. *)
(* Conventions as in proof512.txt: positions are 0..n-1; S(r mod M) is the sum of a_i over positions i = r (mod M). *)

(* 10th forward difference of a weight function w at j: Sum_t C(10,t) (-1)^(10-t) w(j+t) *)
d10[w_, j_] := Sum[Binomial[10, t] (-1)^(10 - t) w[j + t], {t, 0, 10}];

(* Indicator [i = c (mod M)] *)
ind[c_, M_, i_] := Boole[Mod[i, M] == c];

(* The weights of Lemma 2 *)
wOne[i_] := 1;
w01[i_] := ind[0, 3, i] - ind[1, 3, i];
w12[i_] := ind[1, 3, i] - ind[2, 3, i];

(* The weight of Theorem A (period 27, modulus 3^7 = 2187) *)
wA[i_] := ind[1, 3, i] - ind[0, 3, i] + 81 (ind[8, 9, i] - ind[2, 9, i]) + 729 (ind[23, 27, i] - ind[14, 27, i]);

(* The weight of Theorem B (period 9, modulus 3^6 = 729) *)
wB[i_] := ind[1, 3, i] - ind[2, 3, i] + 81 (ind[3, 9, i] - ind[0, 9, i]);

(* Number of positions 0 <= i < n with i = r (mod M) *)
size[n_, M_, r_] := Length[Range[r, n - 1, M]];

Print["Claude: \"", "=== Lemma 1 hypotheses: 10th differences over one period ===", "\""];

(* Lemma 2: w = 1 *)
c1 = d10[wOne, 0];
Print["Claude: \"", "D^10 (w = 1) at j = 0 (expect 0): ", c1, "\""];

(* Lemma 2: the two mod-3 weights *)
c01 = Table[d10[w01, j], {j, 0, 2}];
Print["Claude: \"", "D^10 w01 at j = 0, 1, 2 (expect {0, -243, 243}): ", c01, "\""];
c12 = Table[d10[w12, j], {j, 0, 2}];
Print["Claude: \"", "D^10 w12 at j = 0, 1, 2 (expect {243, 0, -243}): ", c12, "\""];

(* Theorem A: all 27 values must be multiples of 2187 *)
cA = Table[d10[wA, j], {j, 0, 26}];
Print["Claude: \"", "D^10 wA at j = 0..26, divided by 2187 (expect integers): ", cA/2187, "\""];

(* Theorem B: all 9 values must be multiples of 729 *)
cB = Table[d10[wB, j], {j, 0, 8}];
Print["Claude: \"", "D^10 wB at j = 0..8, divided by 729 (expect integers): ", cB/729, "\""];

(* The weights really have the periods used (so one period of j suffices) *)
periodsOK = And @@ Flatten[{
    Table[wA[i] == wA[i + 27], {i, -81, 81}], Table[wB[i] == wB[i + 9], {i, -27, 27}],
    Table[w01[i] == w01[i + 3] && w12[i] == w12[i + 3], {i, -9, 9}]}];
Print["Claude: \"", "weights have periods 27, 9, 3, 3 (expect True): ", periodsOK, "\""];

(* The same numbers in residue-lattice form: D^10 w(j) = <w, coefficients of x^j (x-1)^10 mod x^M - 1>,
   so each weight is a dual vector of the lattice spanned by those M coefficient vectors *)
gen[M_, j_] := Module[{z}, PadRight[CoefficientList[PolynomialRemainder[z^j (z - 1)^10, z^M - 1, z], z], M]];
dual[w_, M_] := Table[Table[w[r], {r, 0, M - 1}] . gen[M, j], {j, 0, M - 1}];
dualOK = dual[wA, 27] == cA && dual[wB, 9] == cB && dual[w01, 3] == c01 && dual[w12, 3] == c12;
Print["Claude: \"", "same values from the residue-lattice generators x^j (x-1)^10 mod x^M - 1 (expect True): ", dualOK, "\""];

lemmaOK = c1 == 0 && c01 == {0, -243, 243} && c12 == {243, 0, -243} &&
   AllTrue[cA, Divisible[#, 2187] &] && AllTrue[cB, Divisible[#, 729] &] && periodsOK && dualOK;
Print["Claude: \"", "Lemma 1 hypotheses hold (expect True): ", lemmaOK, "\""];

(* Step 1: all (S0, S1, S2) with |S_r| <= s_r, S_r = s_r (mod 2), S0 + S1 + S2 = 0, S0 = S1 = S2 (mod 243) *)
step1[n_] := Module[{s = Table[size[n, 3, r], {r, 0, 2}]},
   Sort[Select[Flatten[Table[{x, y, -x - y}, {x, -s[[1]], s[[1]], 2}, {y, -s[[2]], s[[2]], 2}], 1],
     Abs[#[[3]]] <= s[[3]] && EvenQ[#[[3]] - s[[3]]] && Divisible[#[[1]] - #[[2]], 243] &&
       Divisible[#[[2]] - #[[3]], 243] &]]];

(* Step 3: for each admissible (S0, S1, S2), place the k minority signs of the nearly constant class c (mod 3)
   among its residue classes r (mod M), in every possible way, and return Sum_i w(i) a_i for each placement.
   In class c the majority value is sgn = Sign[S_c]; with k_r minority entries in class r (mod M),
   S(r mod M) = sgn (s_r - 2 k_r).  On the other two classes mod 3, w is constant (checked), so only S_q enters. *)
constOnClass[w_, M_, q_] := Module[{v = Union[Table[w[r], {r, q, M - 1, 3}]]},
   If[Length[v] != 1, Print["Claude: \"", "ERROR: weight not constant on class ", q, " mod 3", "\""]; Abort[]];
   First[v]];
step3[n_, M_, w_, S_] := Module[{c, sgn, k, cls, others, ks},
   c = First[Select[{0, 1, 2}, Abs[S[[# + 1]]] == 162 &]];
   sgn = Sign[S[[c + 1]]];
   k = (size[n, 3, c] - Abs[S[[c + 1]]])/2;
   cls = Range[c, M - 1, 3];
   others = DeleteCases[{0, 1, 2}, c];
   (* all ways to write k as an ordered sum of Length[cls] nonnegative integers *)
   ks = FrobeniusSolve[ConstantArray[1, Length[cls]], k];
   Table[Sum[constOnClass[w, M, q] S[[q + 1]], {q, others}] +
       Sum[w[cls[[i]]] sgn (size[n, M, cls[[i]]] - 2 kk[[i]]), {i, Length[cls]}], {kk, ks}]];

Print[""];
Print["Claude: \"", "=== Theorem A: n = 512 ===", "\""];
s1A = step1[512];
Print["Claude: \"", "admissible (S0, S1, S2) (expect {{-81, -81, 162}, {81, 81, -162}}): ", s1A, "\""];
Print["Claude: \"", "positions = 2 (mod 3): ", size[512, 3, 2], ", so S2 = -162 leaves exactly ", (size[512, 3, 2] - 162)/2,
  " entries +1 there (expect 170 and 4)", "\""];
Print["Claude: \"", "class sizes s(2 mod 9), s(8 mod 9), s(23 mod 27), s(14 mod 27) (expect {57, 56, 19, 19}): ",
  {size[512, 9, 2], size[512, 9, 8], size[512, 27, 23], size[512, 27, 14]}, "\""];
totA = Flatten[step3[512, 27, wA, #] & /@ s1A];
Print["Claude: \"", "placements checked (expect 990 = 2 x 495): ", Length[totA], "\""];
Print["Claude: \"", "placements with Sum_i wA(i) a_i = 0 (mod 2187) (expect 0): ", Count[Mod[totA, 2187], 0], "\""];
Print["Claude: \"", "values of Sum_i wA(i) a_i / 81 mod 27 that occur (never 0): ", Union[Mod[totA/81, 27]], "\""];
theoremAOK = s1A == {{-81, -81, 162}, {81, 81, -162}} && Length[totA] == 990 && Count[Mod[totA, 2187], 0] == 0;
Print["Claude: \"", "Theorem A computational step (expect True): ", theoremAOK, "\""];

Print[""];
Print["Claude: \"", "=== Theorem B: n = 496 ===", "\""];
s1B = step1[496];
Print["Claude: \"", "admissible (S0, S1, S2) (expect {{-162, 81, 81}, {162, -81, -81}}): ", s1B, "\""];
Print["Claude: \"", "positions = 0 (mod 3): ", size[496, 3, 0], ", so S0 = -162 leaves exactly ", (size[496, 3, 0] - 162)/2,
  " entries +1 there (expect 166 and 2)", "\""];
Print["Claude: \"", "class sizes s(0 mod 9), s(3 mod 9) (expect {56, 55}): ", {size[496, 9, 0], size[496, 9, 3]}, "\""];
totB = Flatten[step3[496, 9, wB, #] & /@ s1B];
Print["Claude: \"", "placements checked (expect 12 = 2 x 6): ", Length[totB], "\""];
Print["Claude: \"", "placements with Sum_i wB(i) a_i = 0 (mod 729) (expect 0): ", Count[Mod[totB, 729], 0], "\""];
theoremBOK = s1B == {{-162, 81, 81}, {162, -81, -81}} && Length[totB] == 12 && Count[Mod[totB, 729], 0] == 0;
Print["Claude: \"", "Theorem B computational step (expect True): ", theoremBOK, "\""];

Print[""];
Print["Claude: \"", "=== Controls (not part of the proof) ===", "\""];

(* Decode a hex code (paper's Table 5 convention: left half, bit 1 = +1; then a_{n-1-i} = (-1)^m a_i) *)
lp[h_, m_] := With[{l = 2 IntegerDigits[FromDigits[h, 16], 2, 4 StringLength[h]] - 1}, Join[l, (-1)^m Reverse[l]]];

(* Exact order: how many exponents k = 0, 1, 2, ... give equal power sums for the +1 and -1 positions
   (positions counted 1..n here, to avoid 0^0; shifting the positions does not change the order) *)
order[f_] := Module[{a = Flatten[Position[f, 1]], b = Flatten[Position[f, -1]], k = 0},
   While[Total[a^k] == Total[b^k], k++]; k];

(* Sum_i w(i) a_i over positions 0..n-1 *)
wsum[w_, a_] := Sum[w[i] a[[i + 1]], {i, 0, Length[a] - 1}];

wits = {
   {240, lp["C394E65AB989457A86B7D0D921636E", 10], 10},
   {336, lp["C87695B43E0ED258AB29C7793D8521DB227C0B746D", 10], 10},
   {432, lp["5A56B0EE234E8794ADE3D0C384F72A5C63A8BD65035EF015B78B46", 11], 11},
   {480, lp["B0CBC94F1E2C68D1E3A6371C357C4B1347952BB968236CF6C82CD9CE01F3", 12], 12},
   {528, Join[lp["C1BE1E21CD63D295A7887A59", 9], lp["9C5479E2669C97071E731A62EBC06F28E87B4961DF", 9]], 10}};

(* Every sequence of order >= 10, of any length, must satisfy all five congruences *)
witOK = And @@ Table[
    Module[{n = w[[1]], a = w[[2]], eo, cong},
     eo = order[a];
     cong = {wsum[wOne, a] == 0, Divisible[wsum[w01, a], 243], Divisible[wsum[w12, a], 243],
       Divisible[wsum[wA, a], 2187], Divisible[wsum[wB, a], 729]};
     Print["Claude: \"", "n = ", n, ": exact order ", eo, " (expect ", w[[3]], "); congruences (expect all True): ", cong, "\""];
     Length[a] == n && eo == w[[3]] && And @@ cong],
    {w, wits}];

(* Thue-Morse of length 512 has order 9 only, so its wA sum need not vanish mod 2187 *)
tm512 = Table[(-1)^DigitCount[i, 2, 1], {i, 0, 511}];
Print["Claude: \"", "Thue-Morse 512: exact order ", order[tm512], " (expect 9); Sum wA(i) a_i mod 2187 = ",
  Mod[wsum[wA, tm512], 2187], " (nonzero, which an order-9 sequence may have)", "\""];
Print["Claude: \"", "controls pass (expect True): ", witOK, "\""];

Print[""];
verdict = lemmaOK && theoremAOK && theoremBOK && witOK;
Print["Claude: \"", "VERDICT (512 and 496 are not in L_10; all checks pass): ", verdict, "\""];
