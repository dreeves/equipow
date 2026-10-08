Claude's up-next list:

1. A second pass of the 240 search, with longer time limits for the sub-cases the first pass leaves open.
2. Searches like the 240 one for 304, 288, 432, 480, 528 and 576, starting with 304. If 304 has order 9, then 2^20 has order 21, since 8·304·368 + 320·480 = 2^20.
3. Count the order-7 partitions of {0, …, 127}. The antisymmetric ones alone number 303, and no count has been published.

---

More comments from Stan:

this 512 result while nice is not all that important. There is no expectation that the magic value will be this low. Could be 17 though!

336 is a 10. I had this in my package pre-Claude, so that is one error.  Maybe a useful building block?

---

Danny Reeves and me:  The 170-year-old Prouhet result that the "power-sum exponent" of 2^n is ≥ n was proved (2019) by Stong with a very ingenious argument to not be sharp, in that for 2^51 it is 52.  We have that down to: for 2^24 it is 25, using Stong’s method. See https://en.wikipedia.org/wiki/Prouhet%E2%80%93Tarry%E2%80%93Escott_problem  for defns.

---

Keeping this accurate seems good. Maybe C. can eliminate some of the ≤ with upper bound proofs.

---

Unfortunately I now have a NEW problem that seems interesting in this area! So let me list the loose ends.

---

Did you try for improving 24 using a value I think Claude did not know about:  336:10

---

But now something new. Consider 2^2:  {0,1,2,3}.  Clearly 0,3  and 1,2  is the only partition that works for exponents 0,1.
Similar assertion is true for 2^3.
Similar assertion is true for 2^4.

So what is the first power of 2 for which the partition into evil&odious numbers is NOT the unique partition given equal power sums as in the basic problem?

We know that for 2^24 there is a second way (since we know we can get the next exponent). So this question ignores the new exponent.

Another way of looking at it: We know that for the classic example the next exponent fails. So in order to get  a Stong-like example we must have a second example. So studying just the existence of a second example seems worthwhile.

Maybe this is known in the context of Littlewood polynomials: we see a second Littlewood polynomial. 

---

There are 3 distinct examples in the case of 2^6. So my “new” question is already answered.  But this helps put Stong’s work in context.

At 64 we get new examples, but not any additional exponents.
At 2^24 we get a new example, but with a new exponent.

---

A new result. And it can be certified instantaneously. By Danny Reeves and me, using Claude AI.

Recall that in our 2019 paper we gave Stong’s clever proof that there is a subset A of {0,1,…,2^51 -1} such that, if B is A’s complement, then the sums of A^j and B^j are equal for j = 0, 1, …, 52. The point here is that the Prouhet 1851 work gets this up to exponent 51. This gives one more exponent, defeating the conjecture that the Prouhet result is sharp.

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
