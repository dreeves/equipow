(* record_gaps.wl

   Written by Claude (Claude Opus 5.5, an AI model made by Anthropic) on 2026-10-18, for Stan Wagon, at Danny Reeves's
   request.  The code and every comment in this file are Claude's; no human has reviewed them.

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
  {20, {{{848, 11}, {992, 11}}, {{240, 10}, {432, 11}, {2, 1}}}},
  {29, {{{608, 10}, {800, 11}, {800, 11}}, {{336, 10}, {336, 10}, {912, 12}}, {{240, 10}, {432, 11}, {432, 11}}}},
  {37, {{{208, 8}, {800, 11}, {800, 11}, {848, 11}}, {{192, 9}, {192, 9}, {432, 11}, {432, 11}, {2, 1}},
    {{48, 6}, {480, 12}, {480, 12}, {976, 11}}}},
  {41, {{{800, 11}, {800, 11}, {832, 11}, {848, 11}, {4, 2}}, {{432, 11}, {432, 11}, {432, 11}, {816, 11}, {4, 2}},
    {{480, 12}, {480, 12}, {480, 12}, {784, 10}}, {{432, 11}, {432, 11}, {480, 12}, {480, 12}}}},
  {48, {{{560, 10}, {800, 11}, {800, 11}, {800, 11}, {832, 11}},
    {{336, 10}, {336, 10}, {432, 11}, {432, 11}, {432, 11}, {2, 1}},
    {{48, 6}, {480, 12}, {480, 12}, {480, 12}, {928, 11}, {2, 1}},
    {{240, 10}, {336, 10}, {432, 11}, {432, 11}, {480, 12}},
    {{48, 6}, {480, 12}, {480, 12}, {480, 12}, {480, 12}, {2, 1}},
    {{48, 6}, {480, 12}, {480, 12}, {480, 12}, {480, 12}}}},
  {57, {{{352, 9}, {800, 11}, {800, 11}, {800, 11}, {800, 11}, {800, 11}},
    {{480, 12}, {480, 12}, {480, 12}, {480, 12}, {480, 12}, {512, 9}},
    {{432, 11}, {432, 11}, {432, 11}, {432, 11}, {432, 11}, {496, 9}},
    {{144, 8}, {368, 9}, {432, 11}, {480, 12}, {480, 12}, {480, 12}},
    {{240, 10}, {240, 10}, {432, 11}, {432, 11}, {432, 11}, {432, 11}},
    {{480, 12}, {480, 12}, {480, 12}, {480, 12}, {480, 12}, {64, 6}},
    {{240, 10}, {240, 10}, {240, 10}, {432, 11}, {432, 11}, {480, 12}},
    {{48, 6}, {336, 10}, {480, 12}, {480, 12}, {480, 12}, {480, 12}}}},
  {65, {{{112, 7}, {800, 11}, {800, 11}, {800, 11}, {800, 11}, {800, 11}, {928, 11}},
    {{480, 12}, {480, 12}, {480, 12}, {848, 11}, {896, 11}, {896, 11}, {16, 4}},
    {{192, 9}, {336, 10}, {336, 10}, {432, 11}, {432, 11}, {432, 11}, {432, 11}},
    {{48, 6}, {432, 11}, {432, 11}, {432, 11}, {480, 12}, {480, 12}, {592, 10}},
    {{480, 12}, {480, 12}, {480, 12}, {480, 12}, {480, 12}, {480, 12}, {16, 4}},
    {{432, 11}, {432, 11}, {480, 12}, {480, 12}, {480, 12}, {480, 12}, {8, 3}},
    {{480, 12}, {480, 12}, {480, 12}, {480, 12}, {480, 12}, {480, 12}, {4, 2}},
    {{480, 12}, {480, 12}, {480, 12}, {480, 12}, {480, 12}, {480, 12}, {2, 1}}}},
  {68, {{{800, 11}, {800, 11}, {800, 11}, {800, 11}, {800, 11}, {800, 11}, {832, 11}},
    {{480, 12}, {480, 12}, {480, 12}, {480, 12}, {480, 12}, {480, 12}, {2048, 11}},
    {{480, 12}, {480, 12}, {480, 12}, {480, 12}, {480, 12}, {480, 12}, {1024, 10}},
    {{208, 8}, {480, 12}, {480, 12}, {480, 12}, {800, 11}, {800, 11}, {832, 11}},
    {{192, 9}, {432, 11}, {432, 11}, {432, 11}, {432, 11}, {432, 11}, {896, 11}, {4, 2}},
    {{192, 9}, {192, 9}, {432, 11}, {432, 11}, {432, 11}, {432, 11}, {480, 12}, {8, 3}},
    {{192, 9}, {336, 10}, {336, 10}, {432, 11}, {432, 11}, {480, 12}, {480, 12}, {4, 2}},
    {{480, 12}, {480, 12}, {480, 12}, {480, 12}, {480, 12}, {480, 12}, {256, 8}},
    {{192, 9}, {192, 9}, {480, 12}, {480, 12}, {480, 12}, {480, 12}, {896, 11}},
    {{480, 12}, {480, 12}, {480, 12}, {480, 12}, {480, 12}, {480, 12}, {128, 7}},
    {{480, 12}, {480, 12}, {480, 12}, {480, 12}, {480, 12}, {480, 12}, {64, 6}},
    {{12, 3}, {480, 12}, {480, 12}, {480, 12}, {480, 12}, {480, 12}, {480, 12}, {4, 2}},
    {{480, 12}, {480, 12}, {480, 12}, {480, 12}, {480, 12}, {480, 12}, {32, 5}}}}
};

(* TODO: error copy; says the script stopped, and which check failed *)
check[test_, what_String] := If[! TrueQ[test], Print["Claude: \"record_gaps.wl stopped: " <> what <> "\""]; Abort[]];

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
  (* TODO: error copy; says the products' lengths in the row of 2^k do not sum to 2^k *)
  check[Total[Times @@@ ps[[All, All, 1]]] == 2^k,
    "the products' lengths in the row of 2^" <> ToString[k] <> " do not sum to 2^" <> ToString[k]];
  (* TODO: error copy; says the least order of the products in the row of 2^k is not k + g, and what it is *)
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
