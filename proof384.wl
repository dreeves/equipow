(* proof384.wl

   Written by Astra, 2026-10-20. A standalone exact-arithmetic version of proof384.py.
   Run with wolframscript -file proof384.wl, or evaluate Get["proof384.wl"] in a notebook.
   Get returns the counts, elimination levels, witness and power moments for inspection.
   No Python, solver, lattice package, search journal or floating-point arithmetic is used.

   Order m means that signed power sums vanish in degrees 0,...,m-1. Positions below are
   0,...,383; translating them to 1,...,384 preserves the order. An explicit order-10
   witness gives the lower bound. For the upper bound, suppose an order-11 witness exists.
   The binomial polynomials Binomial[p,k], k=0,...,10, span the polynomials of degree at
   most 10, so (z-1)^11 divides its sign polynomial in Z[z]. Modulo z^5-1, the five signed
   residue sums must therefore be an integer combination of cyclic shifts of the computed
   generator. Each shift satisfies residueConditions below, so every possible witness does.

   Enumeration of every signed residue sum allowed by class size, parity and divisibility
   leaves four plus-sign count vectors. Each has one class r with exactly one plus sign
   and one class s with exactly one minus sign. Their exceptional positions are r+5 i and
   s+5 j, where i,j=0,...,76. All four vectors and all 4*77^2 position pairs are checked,
   with no symmetry assumption. The other 230 binary variables obey eleven binomial
   moment equations and five residue-count equations. The moment targets are
   Binomial[384,k+1]/2, by the hockey-stick identity; their integrality is checked.

   Each certificate combines these sixteen equations. Its value on every free column is
   a multiple of its modulus, hence so must be its value on any feasible residual target.
   At least one certificate contradicts each of the 23,716 targets. This excludes order
   11 and every higher order. The actual order-10 witness also provides positive controls
   for the certificate identities, using its actual free-variable moments and counts.

   Mathematical positions and residue classes stay zero-based; only Part indices add 1.
   The constant power moment is computed separately, so no expression 0^0 is evaluated.
*)

Module[{n = 384, sizes, certificates, code, require, residueConditions, z, generator,
        choices, signed, vectors, keys, rows, momentRHS, left, witness, signs, moments,
        counts, checked = 0, r, s, free, base, control, survivors, levels, modulus,
        coefficients, values, constant, result},

  require[condition_] := If[!TrueQ[condition],
    (* TODO: report that a certificate verification failed. *)
    Print["Astra: \"Probatio deficit.\""];
    Abort[]];

  (* Keys are the two fixed residue classes, sorted. Coefficients are the eleven
     binomial rows followed by the five residue-count rows, in increasing order. *)
  certificates = <|
    {0, 3} -> {
      {25, {1, -1, 1, 0, -3, -20, 5, 0, 0, 0, 0, 0, 0, 0, 0, 0}},
      {125, {-32, -93, -32, -11, 15, 35, -20, -5, 0, 5, 0, 0, 0, 0, 0, 0}},
      {125, {-46, 46, -46, 0, 13, 5, -15, -15, -20, 0, 25, 0, 0, 0, 0, 0}},
      {625, {-216, 215, -214, 30, -105, 315, -30, 50, 25, 0, -100, 0, 1, 0, 0, 0}}
    },
    {1, 2} -> {
      {25, {0, -1, 1, 0, -2, -20, 5, 0, 0, 0, 0, 0, 0, 0, 0, 0}},
      {125, {0, 1, 42, -4, 10, -60, -5, -20, 0, 5, 0, 0, 0, 0, 0, 0}},
      {125, {0, 56, 29, -5, -3, -5, -10, -10, -5, 0, 25, 0, 0, 0, 0, 0}},
      {625, {-1, 233, -6, -55, -50, -305, 5, 0, -50, 0, -25, 1, 0, 0, 0, 0}}
    }
  |>;
  code = "C1BE1E21CD63D295A7887A5965A1EE1A56B4394C7B87827C";

  (* Validate all supplied certificate data before constructing the moment equations. *)
  require[AssociationQ[certificates]];
  require[AllTrue[Values[certificates], ListQ]];
  Do[
    require[MatchQ[certificate, {_Integer, {Repeated[_Integer]}}]];
    require[First[certificate] > 0 && Length[Last[certificate]] == 16],
    {group, Values[certificates]}, {certificate, group}];

  sizes = Table[Length[Range[t, n - 1, 5]], {t, 0, 4}];
  require[sizes === {77, 77, 77, 77, 76}];
  residueConditions[d_] := Total[d] == 0 && AllTrue[d, Divisible[#, 25] &] &&
    Divisible[d[[3]] - 4 d[[1]] - 2 d[[2]], 125] &&
    Divisible[d[[4]] - 3 d[[1]] - 3 d[[2]], 125];
  generator = PadRight[CoefficientList[PolynomialRemainder[(z - 1)^11, z^5 - 1, z], z], 5];
  require[generator === {450, -450, 275, 0, -275}];
  require[AllTrue[Table[RotateLeft[generator, t], {t, 0, 4}], residueConditions]];

  (* Enumerate all five classes directly, including the size-76 class. *)
  choices = Table[Select[Range[-size, size, 2], Divisible[#, 25] &], {size, sizes}];
  signed = Select[Tuples[choices], residueConditions];
  vectors = (# + sizes)/2 & /@ signed;
  require[vectors === {{1, 26, 51, 76, 38}, {26, 76, 1, 51, 38},
                       {51, 1, 76, 26, 38}, {76, 51, 26, 1, 38}}];
  keys = Union[Sort[{First[FirstPosition[#, 1]], First[FirstPosition[#, 76]]} - 1] & /@ vectors];
  require[Sort[Keys[certificates]] === keys];

  rows = Join[Table[Binomial[p, k], {k, 0, 10}, {p, 0, n - 1}],
              Table[Boole[Mod[p, 5] == t], {t, 0, 4}, {p, 0, n - 1}]];
  require[Dimensions[rows] === {16, n}];
  momentRHS = Table[Binomial[n, k + 1]/2, {k, 0, 10}];
  require[VectorQ[momentRHS, IntegerQ]];

  left = IntegerDigits[FromDigits[code, 16], 2, 4 StringLength[code]];
  witness = Join[left, Reverse[left]];
  require[Length[witness] == n && AllTrue[witness, MemberQ[{0, 1}, #] &]];
  signs = 2 witness - 1;
  moments = Prepend[Table[signs . (Range[0, n - 1]^k), {k, 1, 10}], Total[signs]];
  require[Take[moments, 10] === ConstantArray[0, 10] && Last[moments] != 0];
  require[2 rows[[1 ;; 10]] . witness === Table[Binomial[n, k + 1], {k, 0, 9}]];

  counts = Table[
    r = First[FirstPosition[vector, 1]] - 1;
    s = First[FirstPosition[vector, 76]] - 1;
    require[sizes[[r + 1]] == 77 && sizes[[s + 1]] == 77];
    free = Select[Range[0, n - 1], !MemberQ[{r, s}, Mod[#, 5]] &];
    require[Length[free] == 230];
    (* Start with r all minus and s all plus. The exceptional positions then
       subtract column r+5 i and add column s+5 j from the residual target. *)
    base = Join[momentRHS, vector] - (Total /@ rows[[All, Range[s, n - 1, 5] + 1]]);
    control = rows[[All, free + 1]] . witness[[free + 1]];
    survivors = Tuples[Range[0, 76], 2];
    checked += Length[survivors];
    levels = Table[
      {modulus, coefficients} = certificate;
      values = coefficients . rows;
      require[AllTrue[values[[free + 1]], Divisible[#, modulus] &]];
      require[Divisible[coefficients . control, modulus]];
      constant = coefficients . base;
      survivors = Select[survivors,
        Divisible[constant - values[[r + 5 #[[1]] + 1]] + values[[s + 5 #[[2]] + 1]], modulus] &];
      Length[survivors],
      {certificate, certificates[Sort[{r, s}]]}];
    require[survivors === {}];
    levels,
    {vector, vectors}];

  result = <|"vectors" -> Length[vectors], "countVectors" -> vectors, "cases" -> checked,
             "survivors" -> 0, "order10Control" -> True, "levels" -> counts,
             "moments" -> moments, "witness" -> witness|>;
  (* TODO: report the proved value, number of count vectors and position cases,
     and absence of any surviving order-11 case. *)
  Print["Astra: \"m*(384) = 10; ", result["vectors"], " vectores, ",
        result["cases"], " casus, ", result["survivors"], " superstites.\""];
  result
]
