(* This script is all Claude *)
(* Checks the computations in proof512.txt, which proves that 512 and 496 are not in L_10:
   no sequence of 512 or of 496 signs has order 10 or more.
   Run with wolframscript -file proof512.wl. All arithmetic is exact. The last line printed is the verdict. *)
(* Notation as in proof512.txt: positions are 0..n-1, and S(r mod M) is the sum of a_i over i = r (mod M). *)

(* D^10 w(j), the 10th forward difference of w at j *)
d10[w_, j_] := Sum[Binomial[10, t] (-1)^(10 - t) w[j + t], {t, 0, 10}];

(* [i = c (mod M)] *)
ind[c_, M_, i_] := Boole[Mod[i, M] == c];

(* Weights for Lemma 2 *)
wOne[i_] := 1;
w01[i_] := ind[0, 3, i] - ind[1, 3, i];
w12[i_] := ind[1, 3, i] - ind[2, 3, i];

(* Weight for Theorem A: period 27, modulus 3^7 = 2187 *)
wA[i_] := ind[1, 3, i] - ind[0, 3, i] + 81 (ind[8, 9, i] - ind[2, 9, i]) + 729 (ind[23, 27, i] - ind[14, 27, i]);

(* Weight for Theorem B: period 9, modulus 3^6 = 729 *)
wB[i_] := ind[1, 3, i] - ind[2, 3, i] + 81 (ind[3, 9, i] - ind[0, 9, i]);

(* s(r mod M) = #{0 <= i < n : i = r (mod M)} *)
size[n_, M_, r_] := Length[Range[r, n - 1, M]];

Print["Lemma 1 hypotheses: 10th differences over one period"];

(* Lemma 2: w = 1 *)
c1 = d10[wOne, 0];
Print["D^10 wOne: ", c1];

(* Lemma 2: the two mod-3 weights *)
c01 = Table[d10[w01, j], {j, 0, 2}];
Print["D^10 w01: ", c01];
c12 = Table[d10[w12, j], {j, 0, 2}];
Print["D^10 w12: ", c12];

(* Theorem A, step 2: all 27 values must be multiples of 2187 *)
cA = Table[d10[wA, j], {j, 0, 26}];
Print["D^10 wA / 2187: ", cA/2187];

(* Theorem B: all 9 values must be multiples of 729 *)
cB = Table[d10[wB, j], {j, 0, 8}];
Print["D^10 wB / 729: ", cB/729];

(* wA, wB, w01, w12 have periods 27, 9, 3, 3, so one period of j suffices *)
periodsOK = And @@ Flatten[{
    Table[wA[i] == wA[i + 27], {i, -81, 81}], Table[wB[i] == wB[i + 9], {i, -27, 27}],
    Table[w01[i] == w01[i + 3] && w12[i] == w12[i + 3], {i, -9, 9}]}];
Print["wA, wB, w01, w12 have periods 27, 9, 3, 3: ", periodsOK];

(* The same values as inner products: for w of period M, D^10 w(j) = <w, x^j (x-1)^10 mod x^M - 1>.
   So wA/2187, wB/729, w01/243 and w12/243 are in the dual of the lattice these M vectors span. *)
gen[M_, j_] := Module[{z}, PadRight[CoefficientList[PolynomialRemainder[z^j (z - 1)^10, z^M - 1, z], z], M]];
dual[w_, M_] := Table[Table[w[r], {r, 0, M - 1}] . gen[M, j], {j, 0, M - 1}];
dualOK = dual[wA, 27] == cA && dual[wB, 9] == cB && dual[w01, 3] == c01 && dual[w12, 3] == c12;
Print["same values from x^j (x-1)^10 mod x^M - 1: ", dualOK];

lemmaOK = c1 == 0 && c01 == {0, -243, 243} && c12 == {243, 0, -243} &&
   AllTrue[cA, Divisible[#, 2187] &] && AllTrue[cB, Divisible[#, 729] &] && periodsOK && dualOK;
Print["Lemma 1 hypotheses hold: ", lemmaOK];

(* Step 1: all (S_0, S_1, S_2) with |S_r| <= s(r mod 3), S_r = s(r mod 3) (mod 2),
   S_0 + S_1 + S_2 = 0 and S_0 = S_1 = S_2 (mod 243) *)
step1[n_] := Module[{s = Table[size[n, 3, r], {r, 0, 2}]},
   Sort[Select[Flatten[Table[{x, y, -x - y}, {x, -s[[1]], s[[1]], 2}, {y, -s[[2]], s[[2]], 2}], 1],
     Abs[#[[3]]] <= s[[3]] && EvenQ[#[[3]] - s[[3]]] && Divisible[#[[1]] - #[[2]], 243] &&
       Divisible[#[[2]] - #[[3]], 243] &]]];

(* Step 3: c is the class mod 3 with |S_c| = 162. All but k of its entries equal sgn = Sign[S_c].
   For each placement of the other k among the classes r mod M with r = c (mod 3), return Sum_i w(i) a_i,
   using S(r mod M) = sgn (s(r mod M) - 2 k_r) when k_r of them are in class r.
   On the other two classes mod 3, w is constant (checked). *)
constOnClass[w_, M_, q_] := Module[{v = Union[Table[w[r], {r, q, M - 1, 3}]]},
   If[Length[v] != 1, Print["weight not constant on class ", q, " mod 3"]; Abort[]];
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
Print["Theorem A: n = 512"];
s1A = step1[512];
Print["admissible (S_0, S_1, S_2): ", s1A];
Print["positions i = 2 (mod 3): ", size[512, 3, 2], ", of which +1 when S_2 = -162: ", (size[512, 3, 2] - 162)/2];
Print["s(2 mod 9), s(8 mod 9), s(23 mod 27), s(14 mod 27): ",
  {size[512, 9, 2], size[512, 9, 8], size[512, 27, 23], size[512, 27, 14]}];
totA = Flatten[step3[512, 27, wA, #] & /@ s1A];
Print["placements: ", Length[totA]];
Print["placements with Sum_i wA(i) a_i = 0 (mod 2187): ", Count[Mod[totA, 2187], 0]];
Print["values of Sum_i wA(i) a_i / 81 mod 27: ", Union[Mod[totA/81, 27]]];
theoremAOK = s1A == {{-81, -81, 162}, {81, 81, -162}} && Length[totA] == 990 && Count[Mod[totA, 2187], 0] == 0;
Print["Theorem A case analysis: ", theoremAOK];

Print[""];
Print["Theorem B: n = 496"];
s1B = step1[496];
Print["admissible (S_0, S_1, S_2): ", s1B];
Print["positions i = 0 (mod 3): ", size[496, 3, 0], ", of which +1 when S_0 = -162: ", (size[496, 3, 0] - 162)/2];
Print["s(0 mod 9), s(3 mod 9): ", {size[496, 9, 0], size[496, 9, 3]}];
totB = Flatten[step3[496, 9, wB, #] & /@ s1B];
Print["placements: ", Length[totB]];
Print["placements with Sum_i wB(i) a_i = 0 (mod 729): ", Count[Mod[totB, 729], 0]];
theoremBOK = s1B == {{-162, 81, 81}, {162, -81, -81}} && Length[totB] == 12 && Count[Mod[totB, 729], 0] == 0;
Print["Theorem B case analysis: ", theoremBOK];

Print[""];
Print["Controls (not part of the proof)"];

(* Decode a hex code as in Table 5 of Buhler, Golan, Pratt and Wagon (Math. Comp. 90, 2021):
   the hex digits give the left half (bit 1 = +1), and a_{n-1-i} = (-1)^m a_i gives the rest *)
lp[h_, m_] := With[{l = 2 IntegerDigits[FromDigits[h, 16], 2, 4 StringLength[h]] - 1}, Join[l, (-1)^m Reverse[l]]];

(* Order: the least k with Sum_i a_i i^k != 0. Positions run 1..n here to avoid 0^0, which doesn't change the order. *)
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

(* Any sequence of order >= 10 satisfies all five congruences *)
witOK = And @@ Table[
    Module[{n = w[[1]], a = w[[2]], eo, cong},
     eo = order[a];
     cong = {wsum[wOne, a] == 0, Divisible[wsum[w01, a], 243], Divisible[wsum[w12, a], 243],
       Divisible[wsum[wA, a], 2187], Divisible[wsum[wB, a], 729]};
     Print["n = ", n, ": order ", eo, ", congruences ", cong];
     Length[a] == n && eo == w[[3]] && And @@ cong],
    {w, wits}];

(* Thue-Morse of length 512 has order 9, so its wA sum need not vanish mod 2187 *)
tm512 = Table[(-1)^DigitCount[i, 2, 1], {i, 0, 511}];
Print["Thue-Morse 512: order ", order[tm512], ", Sum_i wA(i) a_i mod 2187 = ", Mod[wsum[wA, tm512], 2187]];
Print["n = 240, 336, 432, 480, 528: ", witOK];

Print[""];
verdict = lemmaOK && theoremAOK && theoremBOK && witOK;
Print["512 and 496 are not in L_10: ", verdict];
