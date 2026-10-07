More comments from Stan:

this 512 result while nice is not all that important. There is no expectation that the magic value will be this low. Could be 17 though!

The color coding is good. Make sure it keeps this chart; corrects it,updates it.

336 is a 10. I had this in my package pre-Claude, so that is one error.  Maybe a useful building block?

528 is a 10; same comments as above: I knew this.

Here is the set for 336.

S[10][336] = {0, 1, 4, 9, 10, 11, 13, 14, 16, 19, 21, 23, 24, 26, 27, 
  29, 34, 35, 36, 37, 38, 44, 45, 46, 48, 49, 51, 54, 57, 59, 60, 64, 
  66, 68, 70, 71, 74, 76, 79, 80, 81, 85, 86, 87, 89, 90, 91, 92, 95, 
  98, 99, 100, 101, 103, 104, 109, 111, 114, 119, 120, 121, 123, 124, 
  126, 127, 130, 134, 137, 138, 139, 140, 141, 148, 150, 151, 153, 
  154, 155, 157, 161, 162, 164, 165, 167, 168, 170, 171, 173, 174, 
  178, 180, 181, 182, 184, 185, 187, 194, 195, 196, 197, 198, 201, 
  205, 208, 209, 211, 212, 214, 215, 216, 221, 224, 226, 231, 232, 
  234, 235, 236, 237, 240, 243, 244, 245, 246, 248, 249, 250, 254, 
  255, 256, 259, 261, 264, 265, 267, 269, 271, 275, 276, 278, 281, 
  284, 286, 287, 289, 290, 291, 297, 298, 299, 300, 301, 306, 308, 
  309, 311, 312, 314, 316, 319, 321, 322, 324, 325, 326, 331, 334, 
  335}

---

Danny Reeves and me:  The 170-year-old Prouhet result that the "power-sum exponent" of 2^n is ≥ n was proved (2019) by Stong with a very ingenious argument to not be sharp, in that for 2^51 it is 52.  We have that down to: for 2^24 it is 25, using Stong’s method. See https://en.wikipedia.org/wiki/Prouhet%E2%80%93Tarry%E2%80%93Escott_problem  for defns.

---

When I said I had 336, that is true, but no upper bound. So it is ≥10

I do want to store the sets. I have Claude’s 432. Can you send Claude’s 480?

I believe those are the only new ones C. found.

Keeping this accurate seems good. Maybe C. can eliminate some of the ≤ with upper bound proofs.

---

m*(n) values

| n     | 8 | 16 | 24 | 32 | 40 | 48 | 56 | 64 | 72 | 80 | 88 | 96 | 104 |
|:------|:-:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:---:|
| m*(n) | 3 | 4  | 4  | 5  | 5  | 6  | 5  | 6  | 6  | 6  | 6  | 7  | 6   |

| n     | 112 | 120 | 128 | 136 | 144 | 152 | 160 | 168 | 176 | 184 | 192 | 200 | 208 |
|:------|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| m*(n) | 7   | 6   | 7   | 6   | 8   | 6   | 7   | 6   | 7   | 6   | 9   | 7   | 8   |

| n     | 216 | 224 | 232 | 240      | 248 | 256 | 264 | 272 | 280 | 288     | 296 | 304    | 2⁵¹ |
|:------|:---:|:---:|:---:|:--------:|:---:|:---:|:---:|:---:|:---:|:-------:|:---:|:------:|:---:|
| m*(n) | 7   | 8   | 7   | 10 or 11 | 7   | 8   | 7   | 8   | 7   | 9 or 10 | 7   | 8 or 9 | ≥52 |

| n     | 320 | 336 | 352 | 368 | 400 | 416 | 432 | 464 | 480 | 496 | 512 | 528 | 2²⁴ |
|:------|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| m*(n) | 9   | ≥10 | 9   | 9   | 9   | 9   | ≥11 | 9   | ≥12 | 9   | 9   | ≥10 | ≥25 |

Claude found:    432 :11  I have the set

480:12  Can you send me the set for my package, which has all the sets.

512:  Proof pending.  = 9.

2⁵¹  Stong

336 is ≥ 10. I had this in my package pre-Claude, but not in paper. so that is one error.  Maybe a useful building block?

528 is ≥ 10; same comments as above: I knew this.

---

Unfortunately I now have a NEW problem that seems interesting in this area! So let me list the loose ends.

I want to have all the new examples in my database. Right now I have only this:

SClaude[11][432] = {2, 4, 5, 7, 10, 12, 14, 15, 17, 19, 20, 25, 26,
   27, 29, 30, 31, 35, 39, 40, 42, 45, 46, 47, 49, 54, 55, 56, 57, 60,
    62, 65, 67, 69, 70, 72, 73, 74, 75, 79, 80, 81, 82, 84, 89, 90,
   95, 96, 97, 102, 105, 106, 107, 108, 110, 111, 112, 115, 117, 119,
   122, 124, 125, 126, 130, 131, 135, 136, 137, 139, 141, 145, 147,
   148, 149, 150, 152, 154, 155, 158, 160, 167, 168, 170, 172, 173,
   174, 175, 177, 178, 179, 180, 188, 190, 192, 193, 195, 196, 198,
   199, 200, 201, 205, 207, 208, 210, 214, 215, 217, 220, 221, 222,
   224, 227, 229, 230, 231, 236, 239, 242, 244, 246, 247, 248, 249,
   250, 251, 252, 257, 262, 264, 267, 268, 269, 270, 271, 272, 274,
   276, 277, 280, 282, 287, 289, 290, 291, 293, 295, 299, 300, 301,
   304, 305, 306, 310, 312, 313, 315, 317, 319, 320, 324, 329, 330,
   332, 333, 334, 335, 339, 340, 341, 342, 345, 346, 347, 348, 350,
   355, 356, 357, 362, 365, 367, 369, 370, 372, 374, 375, 380, 381,
   382, 383, 385, 389, 390, 392, 395, 396, 397, 399, 400, 401, 405,
   409, 410, 411, 412, 415, 417, 420, 422, 424, 425, 427, 430,
   432};  (* use complement?? *)

SClaude[12][480];


So 480 needed.

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
