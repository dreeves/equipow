Claude's up-next list:

1. A second pass of the 240 search, with longer time limits for the sub-cases the first pass leaves open.
2. Searches like the 240 one for 304, 288, 432, 480, 528 and 576, starting with 304. If 304 has order 9, then 2^20 has order 21, since 8·304·368 + 320·480 = 2^20.
3. Count the order-7 partitions of {0, …, 127}. The antisymmetric ones alone number 303, and no count has been published.
   Claude: "Done: 431 partitions, 367 up to reversal. See the reply to Stan's uniqueness question below."
4. Could we get a nice visualization of the progress of these searches?

---

Stan and Claude Dialog:

this 512 result while nice is not all that important. There is no expectation that the magic value will be this low. Could be 17 though!

Claude: "17 isn't ruled out. Joins of products of the known blocks still bottom out at 2^24. Joins whose pieces cancel each other's top power sum, the trick behind Claude's 528, can't work for any k ≤ 16 with at most four pieces built from known blocks, and 17 is the first k they don't rule out. With 512 = 9, the smallest k with 2^k of order k + 1 is somewhere from 10 to 24."

336 is a 10. I had this in my package pre-Claude, so that is one error.  Maybe a useful building block?

Claude: "336 is exactly 10: the residue condition mod 5 rules out 11. It doesn't help as a building block. With every known block, 336:10 and 480:12 included, joins of products still bottom out at 2^24. The obstruction is divisibility by 3: 2^k isn't a multiple of 3, but 336 and 480 are."

---

Danny Reeves and me:  The 170-year-old Prouhet result that the "power-sum exponent" of 2^n is ≥ n was proved (2019) by Stong with a very ingenious argument to not be sharp, in that for 2^51 it is 52.  We have that down to: for 2^24 it is 25, using Stong’s method. See https://en.wikipedia.org/wiki/Prouhet%E2%80%93Tarry%E2%80%93Escott_problem  for defns.

Claude: "Prouhet's paper is from 1851, so it's 175 years old. And 2^51 now gets at least 53: with f the 2^24 construction, f # f # τ3 has order 25 + 25 + 3."

---

Keeping this accurate seems good. Maybe C. can eliminate some of the ≤ with upper bound proofs.

Claude: "Done for 336 (exactly 10, by mod 5) and 512 (exactly 9; the proof in proof512.txt also covers 496). Two new entries: 448 = 9, where mod 3 rules out 10, and 576 ∈ {10, 11, 12}, where mod 5 rules out 13. For 432, 480, 528, 288 and 304, every residue test tried passes, so they need full searches like the one for 240. Separately, OEIS A323629 leaves 112 out of L_7, though Berend and Golan (2006) and Theorem 3.1 of your paper both have it."

---

Did you try for improving 24 using a value I think Claude did not know about:  336:10

Claude: "Yes, and it doesn't lower 24 (see above). The open table entry that would: if 304 has order 9, then 8·304·368 + 320·480 = 2^20, which gives 2^20 order 21. A search for 304 is up next."

---

But now something new. Consider 2^2:  {0,1,2,3}.  Clearly 0,3  and 1,2  is the only partition that works for exponents 0,1.
Similar assertion is true for 2^3.
Similar assertion is true for 2^4.

So what is the first power of 2 for which the partition into evil&odious numbers is NOT the unique partition given equal power sums as in the basic problem?

We know that for 2^24 there is a second way (since we know we can get the next exponent). So this question ignores the new exponent.

Another way of looking at it: We know that for the classic example the next exponent fails. So in order to get  a Stong-like example we must have a second example. So studying just the existence of a second example seems worthwhile.

Maybe this is known in the context of Littlewood polynomials: we see a second Littlewood polynomial. 

Claude: "It's known. Roth, Siegel and Vardy asked exactly this (IEEE Trans. Inform. Theory 40 (1994) 1826–1840, p. 1830): Thue–Morse is the only one for k ≤ 5, and there are others for every k ≥ 6. Boyd proved the k ≤ 5 case (Math. Comp. 66 (1997) 1697–1703, Theorem 3) and found exactly 3 at 64, all symmetric (Math. Comp. 71 (2002) 1205–1217, Example 5). Section 7 of your paper's arXiv version cites Boyd for this."

---

There are 3 distinct examples in the case of 2^6. So my “new” question is already answered.  But this helps put Stong’s work in context.

At 64 we get new examples, but not any additional exponents.
At 2^24 we get a new example, but with a new exponent.

Claude: "An exhaustive search confirms the 3 at 64, and finds Thue–Morse alone at 32. At 128 there are 431 partitions, 367 up to reversal: the 303 antisymmetric ones, Thue–Morse among them, and 128 more that come in reversed pairs. No count at 128 had been published. Also, the order-7 partition of {0, …, 111} is unique."

---

A new result. And it can be certified instantaneously. By Danny Reeves and me, using Claude AI.

Recall that in our 2019 paper we gave Stong’s clever proof that there is a subset A of {0,1,…,2^51 -1} such that, if B is A’s complement, then the sums of A^j and B^j are equal for j = 0, 1, …, 52. The point here is that the Prouhet 1851 work gets this up to exponent 51. This gives one more exponent, defeating the conjecture that the Prouhet result is sharp.

Claude: "Two off-by-ones: order 52 means equal sums for j = 0, 1, …, 51, and Prouhet's partition of {0, …, 2^51 − 1} has equal sums only up to j = 50."

We now have this for 2^24 instead of 2^51. It comes from these two facts:

112 x 320^2 + 432 x 48 x 2^8 = 16777216 = 2^24

7 + 2 x 9 = 11 + 6 + 8 = 25. 

ClaudeAI found an example for 432 of order 11 (which then allowed it to find the relations above).
Examples of order 7 for 112 and order 9 for 320 were known.
And David B. had the famous order 6 for 48.
Prouhet for the 2^8 factor (the Thue-Morse polynomial)

So the corresponding Littlewood polynomials can be combined to get the claimed example. We were able to get the actual set A of 8388608 integers and compute the power sums explicitly as a check.

In the notation of the last section of our paper (attached for convenience) the new Littlewood polynomial arises from known Littlewood polynomials via the addition and multiplication operations on polynomials (# and OR) below. As for a lower bound, this cannot happen for powers of 2 up to and including 512.

```math
\left(p_{320,9}^{\#2} \mathbin{\#} p_{112,7}\right) \vee \left(p_{432,11} \mathbin{\#} p_{48,6} \mathbin{\#} (1-x)^{\#8}\right)
```

Claude: "The lower bound, nothing at powers of 2 up to 512, rests on 512 = 9, now proved in proof512.txt."
