(* Partition of {1,...,2^18} with equal power sums for exponents 0..18 (order 19). *)
(* Blocks (+-1 coefficient lists); order = number of leading power sums that agree. *)
(* Each block is decoded from its hex code on index.html, in the published paper's Table 5 convention: the hex digits
   give the left half of the signs (1 = +1, 0 = -1), then the rest by (-1)^m symmetry. *)
fromHex[h_String, m_Integer] := Module[{left = 2 IntegerDigits[FromDigits[h, 16], 2, 4 StringLength[h]] - 1},
  Join[left, (-1)^m Reverse[left]]];
p320 = fromHex["B24B649ED92CD2C36496CB2DB6295D974138BA41", 9];   (* order 9, antisymmetric; the page's p320 *)
p560 = fromHex["34D2E9F0DA19EC92492D966936ABCA25FAD924D26F2591EB64926924925D6E1A4BFE92", 10];   (* order 10, symmetric; found by lattice search *)
p432 = fromHex["5A56B0EE234E8794ADE3D0C384F72A5C63A8BD65035EF015B78B46", 11];   (* order 11, antisymmetric; the page's p432 *)
p48 = fromHex["C27D8C", 6];   (* order 6; Boyd; BGPW Table 5 *)
tm4 = Table[(-1)^DigitCount[i, 2, 1], {i, 0, 3}];   (* Thue-Morse, order 2 *)
order[w_] := LengthWhile[Table[Total[Flatten[Position[w, 1]]^k] - Total[Flatten[Position[w, -1]]^k], {k, 0, 13}], # == 0 &];
{order[p320], order[p560], order[p432], order[p48], order[tm4]}   (* expect {9, 10, 11, 6, 2} *)
xp[f_, g_] := Flatten[Outer[Times, g, f]];   (* expanded product f#g: length multiplies, orders add *)
a = xp[p320, p560];            (* 320*560     = 179200, order 9+10   = 19 *)
b = xp[xp[p48, p432], tm4];    (* 48*432*4    = 82944,  order 6+11+2 = 19 *)
f = Join[a, b];                (* length 2^18 *)
X = Flatten[Position[f, 1]];   (* the 2^17 elements of one half *)
{Length[f] == 2^18, Length[X] == 2^17}
(* direct check, exponent k: Total[X^k] == Sum[i^k, {i, 1, 2^18}]/2  for k = 0..18, fails at k = 19 *)
Table[Total[X^k] - Sum[i^k, {i, 1, 2^18}]/2, {k, 0, 19}]
(* the half itself:  Export["X_order19_2^18.txt", X, "List"] *)
