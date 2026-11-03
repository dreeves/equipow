Hosted at https://equipow.dreev.es  

EquipowerfulPackage.m is a Mathematica package by Stan Wagon.  
LittlewoodPolynomialsReprint.pdf is the published version of the paper this is extending.  

---

Potential tasks: 
* [SYM] What's currently the most promising way to prove or disprove the Symmetry Conjecture?
  Astra suggests:
  1. Prove symmetric order 10 impossible at 288, using the symmetry-restricted lattice, residue constraints, and exact infeasibility certificates. This is substantially smaller than the unrestricted problem.
  2. If excluded, attack unrestricted order 10 at 288 using lattice searches without imposing symmetry.
  3. Systematically repeat this at other (n,m) with m>=9, prioritizing cases where modular constraints eliminate the symmetry-restricted problem cheaply.
  4. Or show there's no symmetric witness for 960:14
* [REO] See the notes in the index.html comments tagged [REO]
* [960] Is it possible to get an explicit bipartition for 960?
* [ETA] Maybe the ETA graph would be less confusing / more useful if the graph reset whenever we changed something about the search algorithm? I'm not sure though, so here's an idea for having the best of both worlds: Whenever something changes about the search, spawn a new graph right below the existing one(s) and label each graph with when it started, and keep updating all of them. Or make it more explicit: A button to start a fresh graph any time and buttons to drop any previous graph. PS: Wait, would panning and zooming subsume all that? I guess there's still the idea of "ignore everything that happened previously and recompute the ETA starting now".
* [CRO] This might be fun: Let people contribute computation by just having the equipow page open in their browser. (More boringly, Claude is estimating we could bring the next two searches down from a total of 90 days on my laptop to about 4 days on cloud compute costing around $300.)
* [FAC] Finish reorganizing the files: quals and search stuff in their own directories, certificates?, favicons etc in an images directory?
* [SER] Could the searches show a live estimate of the probability of finding a bipartition?
* [TRE] Could we see a time series of the number of pending nodes? If we could see the growth of that slow down, or when it starts to actually go down, we can better infer the ETA.
* [APP] Eyeballing the charts it looks like maybe `m*(n) ~= 1.2*log2(n)` or something; any interesting conjectures on the asymptotics here? PS: For powers of two we already have something like this: `m*(2^k) = c*log2(n)` where `c` is at least `77/68` and at most `2/log2(3)`. Relatedly, the upper envelope of `m*(n)` is at least `12/log2(480) log2(n)` ~= 1.347 which we get from Theorem 4.1 (Multiplication) of BGPW which tells us that `m*(n^k) >= k m*(n)`. Namely, `m*(480^k) >= 12k` so for certain `n`, `m*(n) >= 12 log_480(n) = 12 log2(n) / log2(480) = 12/log2(480) log2(n)`. So whenever we find a new high watermark for `m*(n)/log2(n)` that bumps up the upper envelope for the `m*()` function. Currently the best we have is 480:12. The following would beat that: 432:12, 672:13, 720: 13, 960:14. Update: We got 960:15! So 15/log2(960) ≈ 1.514 is the new bound on the upper envelope. Also 2^58 gives us 66/58 ≈ 1.138 as the lower bound.
* [LIN] Add one more line for m=16 to the "smallest length known for each order" table


Stan notes:

---

Danny Reeves and me: The 175-year-old Prouhet result that the "power-sum exponent" of 2^n is ≥ n was proved (2019) by Stong with a very ingenious argument to not be sharp, in that for 2^51 it is at least 52. 
See https://en.wikipedia.org/wiki/Prouhet%E2%80%93Tarry%E2%80%93Escott_problem for defns.
We've now shown that for 2^10 it's exactly 11.

---

Consider 2^2: {0,1,2,3}. Clearly {0,3} and {1,2} is the only partition that works for exponents 0,1.
Similar assertion is true for 2^3.
Similar assertion is true for 2^4.

So what is the first power of 2 for which the partition into evil&odious numbers is NOT the unique partition given equal power sums as in the basic problem?

We know that for 2^24 there is a second way (since we know we can get the next exponent). So this question ignores the new exponent.

Another way of looking at it: We know that for the classic example the next exponent fails. So in order to get a Stong-like example we must have a second example. So studying just the existence of a second example seems worthwhile.

Maybe this is known in the context of Littlewood polynomials: we see a second Littlewood polynomial. 

Claude: "It's known. Roth, Siegel and Vardy asked exactly this (IEEE Trans. Inform. Theory 40 (1994) 1826–1840, p. 1830): Thue–Morse is the only one for k ≤ 5, and there are others for every k ≥ 6. Boyd proved the k ≤ 5 case (Math. Comp. 66 (1997) 1697–1703, Theorem 3) and found exactly 3 at 2^6 = 64, all symmetric (Math. Comp. 71 (2002) 1205–1217, Example 5). Section 7 of BGPW's arXiv version cites Boyd for this."

---

There are 3 distinct examples in the case of 2^6. So my "new" question is already answered. But this helps put Stong’s work in context.

At 64 we get new examples, but not any additional exponents.
At 2^24 [now 2^10] we get a new example, but with a new exponent.

Claude: "An exhaustive search confirms the 3 at 64, and finds Thue–Morse alone at 2^5 = 32. At 2^7 = 128 there are 431 partitions, 367 up to reversal: the 303 antisymmetric ones, Thue–Morse among them, and 128 more that come in reversed pairs. No count at 128 had been published. Also, the order-7 partition of {0, …, 111} is unique."

---

A new result. And it can be certified instantaneously. By Danny Reeves and me, using Claude AI.

Recall that in our 2019 paper we gave Stong’s clever proof that there is a subset A of {0,1,…,2^51 -1} such that, if B is A’s complement, then the sums of A^j and B^j are equal for j = 0, 1, …, 51. The point here is that the Prouhet 1851 work gets this up to exponent 50. This gives one more exponent, defeating the conjecture that the Prouhet result is sharp.

We now have this for 2^24 [now 2^10] instead of 2^51. It comes from these two facts:

112 x 320^2 + 432 x 48 x 2^8 = 16777216 = 2^24

7 + 2 x 9 = 11 + 6 + 8 = 25. 

ClaudeAI found an example for 432 of order 11 (which then allowed it to find the relations above).
Examples of order 7 for 112 and order 9 for 320 were known.
And David B. had the famous order 6 for 48.
Prouhet for the 2^8 factor (the Thue-Morse polynomial).

So the corresponding Littlewood polynomials can be combined to get the claimed example. We were able to get the actual set A of 8388608 integers and compute the power sums explicitly as a check.

In the notation of the last section of our paper the new Littlewood polynomial arises from known Littlewood polynomials via the addition and multiplication operations on polynomials (v and #) below. As for a lower bound, this cannot happen for powers of 2 up to and including 512.

```math
\left(p_{320,9}^{\#2} \mathbin{\#} p_{112,7}\right) \vee \left(p_{432,11} \mathbin{\#} p_{48,6} \mathbin{\#} (1-x)^{\#8}\right)
```