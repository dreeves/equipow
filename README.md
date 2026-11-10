Hosted at https://equipow.dreev.es  

EquipowerfulPackage.m is a Mathematica package by Stan Wagon.  
LittlewoodPolynomialsReprint.pdf is the published version of the paper this is extending.  

---

Potential tasks: 
* [COM] Be more principled about what to omit from Figure 1. Idea: checkboxes for what's omitted, in terms of the biggest power of two factor:
  [ ] Nothing
  [ ] n>0 is odd => `m*(n) = 0`
  [ ] n>2 is an odd multiple of 2 => `m*(n) = 1`
  [ ] n>4 is an odd multilple of 4 => `m*(n) = 3`
  [ ] n>=200 is an odd multiple of 8 => `m*(n) = 7`
  (Do we have or can we get a similar result when the biggest power of two factor is 16?)
* [BOU] Let's try having Figure 1 go up to 2048. Actually, let's try this: replace the reset-zoom button with "cap:" and then buttons for 2^6, 2^7, 2^8, 2^9, 2^10, 2^11.
* [MAI] Let's get more things as expandable sections of the main equipow page instead of linking to separate pages. Proofs currently in txt files for starters.
* [CLU] Are there past searches we don't care about anymore that we don't need on the page? Some are interesting for posterity.
* [REO] See the notes in the index.html comments tagged [REO]. Better organization / less redundancy.
* [CRO] This might be fun: Let people contribute computation by just having the equipow page open in their browser. Claude thinks this could work. (More boringly, Claude is estimating we could bring the next two searches down from a total of 90 days on my laptop to about 4 days on cloud compute costing around $300.)
* [TRE] We now have a time series of the number of pending nodes in the search. Seeing when that plateaus or starts to actually go down should improve our ETA. Can we incorporate that in the ETA graph? (Also this was missing from the 288:10 search for some reason.)
* [REF] Refactor the directory structure, like probably all the python scripts belong in a directory.


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