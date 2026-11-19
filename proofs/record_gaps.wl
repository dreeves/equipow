(* record_gaps.wl
   Written by Claude.

   The table's form and its header row are Stan Wagon's (his table of 2026-10-18, whose two rows, 2^17's and 2^27's,
   stopped being record gaps on 2026-10-26 and 2026-10-25, when 2^10 and 2^20 took them), but for one product per
   line, each with its own order (Danny Reeves's choice), since in some rows a product's order exceeds the row's
   bound.

   Get["record_gaps.wl"] (or a paste into a notebook) returns the table behind Theorem 1 on https://equipow.dreev.es
   (the section "Bounds on m*(2^k) - k for every k up to 72"): for each record gap g = 1, ..., 9, the least k known
   with m*(2^k) >= k + g, and its construction, as the page's chart of powers of 2 gives it (pow2.js, which pow2.py
   writes).

   A construction writes 2^k as a join of products of blocks {n, m}.  A block is a sequence of length n and order m:
   Thue-Morse tau_j is {2^j, j}; {1024, 11} is the page's example of order 11 at 1024, p_1024; and any other block is
   the sequence of length n whose order is the lower bound in column n of the page's chart of m*(n).  A product's
   length is the product of its blocks' lengths, and its order is at least the sum of theirs; a join's length is the
   sum of its products' lengths, and its order is at least the least of theirs (BGPW, Theorem 4.1).  The script
   checks each row: its products' lengths sum to 2^k, and the least of their orders is k + g.  A failed check stops
   it with a line saying which, and no table. *)

records = {
  {10, {{{1024, 11}}}},
  {20, {{{848, 11}, {992, 11}},
    {{240, 10}, {432, 11}, {2, 1}}}},
  {22, {{{2528, 13}, {1568, 12}},
    {{960, 15}, {240, 10}}}},
  {30, {{{1504, 12}, {800, 11}, {800, 11}},
    {{1488, 14}, {1440, 16}, {32, 5}},
    {{1632, 15}, {1632, 15}, {16, 4}}}},
  {35, {{{2608, 13}, {2528, 13}, {2528, 13}, {2, 1}},
    {{768, 13}, {672, 13}, {672, 13}, {2, 1}},
    {{1440, 16}, {960, 15}, {240, 10}}}},
  {42, {{{2528, 13}, {2528, 13}, {800, 11}, {800, 11}},
    {{1440, 16}, {960, 15}, {368, 9}, {304, 8}},
    {{1632, 15}, {672, 13}, {672, 13}, {208, 8}}}},
  {50, {{{2528, 13}, {832, 11}, {800, 11}, {800, 11}, {800, 11}},
    {{2528, 13}, {1936, 12}, {1200, 14}, {960, 15}, {8, 3}},
    {{1728, 15}, {1728, 15}, {1488, 14}, {672, 13}},
    {{1488, 14}, {960, 15}, {960, 15}, {672, 13}}}},
  {55, {{{2528, 13}, {2528, 13}, {2528, 13}, {2528, 13}, {848, 11}},
    {{2096, 12}, {1328, 11}, {960, 15}, {768, 13}, {672, 13}},
    {{1728, 15}, {1632, 15}, {1440, 16}, {960, 15}, {4, 2}}}},
  {63, {{{2608, 13}, {2608, 13}, {2608, 13}, {800, 11}, {800, 11}, {800, 11}},
    {{2608, 13}, {2608, 13}, {2608, 13}, {960, 15}, {960, 15}, {8, 3}},
    {{1632, 15}, {1504, 12}, {960, 15}, {960, 15}, {960, 15}},
    {{1632, 15}, {1632, 15}, {1488, 14}, {768, 13}, {672, 13}, {4, 2}}}},
  {68, {{{2608, 13}, {2608, 13}, {2528, 13}, {2528, 13}, {2528, 13}, {2528, 13}},
    {{2608, 13}, {2608, 13}, {960, 15}, {960, 15}, {832, 11}, {832, 11}},
    {{1648, 12}, {1632, 15}, {1568, 12}, {1568, 12}, {1504, 12}, {960, 15}},
    {{2016, 15}, {1728, 15}, {1632, 15}, {848, 11}, {848, 11}, {848, 11}}}}
};

(* error copy; says the script stopped, and which check failed *)
check[test_, what_String] := If[! TrueQ[test], Print["record_gaps.wl stopped: " <> what <> ""]; Abort[]];

(* a product's blocks, ascending by length, each with its count: {n, m, c} *)
factors[p_] := {#[[1, 1]], #[[1, 2]], Length[#]} & /@ Split[SortBy[p, First]];

(* a block in a row's power of 2 and in its order, as Stan Wagon writes them: 368^2 and 2*9 for two blocks of length
   368 and order 9, 800 and 11 for one block of length 800 and order 11 *)
power[{n_, _, 1}] := n;
power[{n_, _, c_}] := Superscript[n, c];
times[{_, m_, 1}] := m;
times[{_, m_, c_}] := Row[{c, m}, "\[CenterDot]"];

(* the table's lines for record gap g, its record {k, products}: the bound on the first line, then a line per product,
   its length and its order *)
lines[g_, {k_, ps_}] := (
  (* error copy; says the products' lengths in the row of 2^k do not sum to 2^k *)
  check[Total[Times @@@ ps[[All, All, 1]]] == 2^k,
    "the products' lengths in the row of 2^" <> ToString[k] <> " do not sum to 2^" <> ToString[k]];
  (* error copy; says the least order of the products in the row of 2^k is not k + g, and what it is *)
  check[Min[Total /@ ps[[All, All, 2]]] == k + g,
    "the least order in the row of 2^" <> ToString[k] <> " is " <> ToString[Min[Total /@ ps[[All, All, 2]]]] <>
      ", not " <> ToString[k + g]];
  Transpose[{
    Prepend[ConstantArray[SpanFromAbove, Length[ps] - 1],
      Row[{Superscript[Style["m", Italic], "*"], "(", Superscript[2, k], ") \[GreaterEqual] ", k + g}]],
    MapThread[Row[{#1, Row[power /@ factors[#2], "\[CenterDot]"]}] &,
      {Prepend[ConstantArray["+ ", Length[ps] - 1], ""], ps}],
    Row[{Row[times /@ factors[#], " + "], " = ", Total[#[[All, 2]]]}] & /@ ps}]);

Grid[Prepend[Join @@ MapIndexed[lines[First[#2], #1] &, records], {"Record gaps", "The power of 2", "The order"}],
  Dividers -> {All, Thread[Join[{1, 2}, 2 + Accumulate[Length /@ records[[All, 2]]]] -> True]},
  Alignment -> {{Center, Left, Left}, Baseline},
  BaseStyle -> {FontFamily -> "Times", 14}, Background -> RGBColor[1, 1, .8], Spacings -> {2, 1}]
