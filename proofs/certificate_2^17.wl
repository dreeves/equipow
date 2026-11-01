(* Partition of {0,...,2^17-1} with equal power sums for exponents 0..17 (order 18). *)
(* Blocks (+-1 coefficient lists); order = number of leading power sums that agree. *)
(* Each block is decoded from its hex code on index.html, in the published paper's Table 5 convention: the hex digits
   give the left half of the signs (1 = +1, 0 = -1), then the rest by (-1)^m symmetry. *)
fromHex[h_String, m_Integer] := Module[{left = 2 IntegerDigits[FromDigits[h, 16], 2, 4 StringLength[h]] - 1},
  Join[left, (-1)^m Reverse[left]]];
p112 = fromHex["A5994DB29B45A0", 7];   (* order 7, antisymmetric; BGPW Table 5 *)
p800 = fromHex["966965968F2C965B25B44B25B3596D924B6D96496C964B65B2CB24B25B2C96CB6C97496CB2CD6E960B243A59A592DB2DB6D9", 11];   (* order 11, antisymmetric; found by lattice search *)
p48 = fromHex["C27D8C", 6];   (* order 6; Boyd; BGPW Table 5 *)
p432 = fromHex["5A56B0EE234E8794ADE3D0C384F72A5C63A8BD65035EF015B78B46", 11];   (* order 11, antisymmetric; the page's p432 *)
tm2 = {1, -1};   (* Thue-Morse, order 1 *)
(* positions run 0..n-1; the 0th power sum of a set is its size (0^0 = 1), which Mathematica leaves Indeterminate,
   so k = 0 compares sizes and k >= 1 compares Total[set^k] *)
order[w_] := Module[{a = Flatten[Position[w, 1]] - 1, b = Flatten[Position[w, -1]] - 1},
  LengthWhile[Prepend[Table[Total[a^k] - Total[b^k], {k, 1, 13}], Length[a] - Length[b]], # == 0 &]];
{order[p112], order[p800], order[p48], order[p432], order[tm2]}   (* expect {7, 11, 6, 11, 1} *)
xp[f_, g_] := Flatten[Outer[Times, g, f]];   (* expanded product f#g: length multiplies, orders add *)
a = xp[p112, p800];            (* 112*800     = 89600, order 7+11   = 18 *)
b = xp[xp[p48, p432], tm2];    (* 48*432*2    = 41472, order 6+11+1 = 18 *)
f = Join[a, b];                (* length 2^17 *)
X = Flatten[Position[f, First[f]]] - 1;   (* the half that contains 0: its 2^16 elements, in {0, ..., 2^17 - 1} *)
{Length[f] == 2^17, Length[X] == 2^16}
(* direct check, exponent k: Total[X^k] == Sum[i^k, {i, 0, 2^17 - 1}]/2  for k = 1..17, fails at k = 18; k = 0 is the half's size *)
Prepend[Table[Total[X^k] - Sum[i^k, {i, 0, 2^17 - 1}]/2, {k, 1, 18}], Length[X] - 2^17/2]
(* the half itself:  Export["X_order18_2^17.txt", X, "List"] *)
