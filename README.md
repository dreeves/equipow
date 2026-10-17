EquipowerfulPackage.m is a Mathematica package by Stan Wagon.

Up next: What n:m, if we could find them, would most help reduce our 2^18?


BGPW's five order-9 examples (lengths 352, 368, 400, 464, 496):

In[1]:= S[9][352]

Out[1]= {0, 2, 5, 8, 9, 11, 12, 14, 15, 17, 20, 23, 26, 29, 30, 32, 
33, 35, 36, 38, 39, 41, 44, 45, 47, 50, 51, 53, 54, 57, 59, 60, 65, 
68, 70, 71, 74, 77, 78, 80, 83, 86, 87, 89, 90, 92, 93, 95, 98, 100, 
101, 104, 105, 106, 107, 108, 110, 113, 115, 117, 120, 122, 123, 125, 
126, 128, 129, 130, 131, 137, 140, 142, 143, 146, 148, 149, 155, 158, 
159, 160, 161, 163, 165, 168, 170, 174, 176, 178, 179, 180, 182, 184, 
185, 187, 189, 194, 195, 197, 198, 199, 200, 201, 204, 206, 207, 210, 
212, 213, 215, 216, 217, 218, 219, 224, 227, 230, 232, 233, 235, 237, 
239, 240, 242, 248, 249, 252, 254, 255, 257, 260, 263, 266, 267, 269, 
270, 272, 275, 276, 278, 279, 282, 284, 285, 287, 288, 289, 290, 293, 
295, 296, 299, 302, 303, 305, 308, 309, 311, 314, 317, 320, 323, 324, 
326, 327, 329, 330, 332, 333, 335, 338, 341, 344, 345, 347, 348, 350}

In[2]:= S[9][368]

Out[2]= {0, 3, 5, 6, 8, 9, 12, 15, 17, 18, 21, 23, 24, 27, 30, 33, 
35, 36, 38, 39, 41, 42, 43, 45, 47, 48, 50, 51, 56, 57, 60, 62, 63, 
66, 69, 72, 75, 76, 77, 78, 81, 83, 84, 90, 91, 92, 93, 96, 97, 98, 
99, 102, 105, 106, 108, 110, 111, 114, 116, 117, 118, 120, 126, 127, 
129, 130, 132, 133, 138, 139, 143, 144, 145, 147, 148, 150, 152, 153, 
156, 161, 162, 163, 165, 168, 170, 171, 173, 174, 177, 178, 179, 180, 
181, 183, 185, 191, 192, 195, 198, 200, 201, 203, 207, 208, 209, 210, 
212, 213, 216, 218, 221, 225, 226, 227, 230, 231, 232, 233, 236, 239, 
242, 243, 244, 245, 246, 248, 252, 254, 255, 258, 260, 263, 264, 266, 
267, 272, 273, 278, 279, 280, 281, 282, 285, 287, 288, 293, 294, 296, 
297, 299, 300, 302, 303, 306, 308, 309, 312, 313, 314, 315, 318, 321, 
323, 327, 330, 333, 335, 336, 338, 339, 341, 342, 345, 347, 348, 351, 
353, 354, 356, 357, 360, 363, 365, 366}

In[3]:= S[9][400]

Out[3]= {2, 3, 5, 8, 9, 11, 12, 14, 15, 17, 18, 20, 23, 26, 29, 30, 
32, 35, 36, 38, 41, 42, 44, 47, 50, 53, 54, 56, 59, 60, 62, 65, 66, 
68, 69, 71, 74, 75, 77, 78, 79, 80, 83, 84, 86, 88, 92, 93, 95, 99, 
100, 101, 105, 107, 109, 110, 111, 113, 117, 119, 120, 123, 124, 125, 
129, 131, 132, 134, 135, 137, 141, 143, 144, 145, 146, 149, 151, 155, 
164, 165, 167, 168, 170, 171, 172, 174, 176, 177, 178, 179, 181, 182, 
183, 184, 185, 186, 188, 190, 192, 194, 196, 198, 200, 202, 204, 206, 
208, 210, 212, 219, 224, 226, 230, 233, 236, 237, 238, 239, 240, 241, 
242, 243, 245, 246, 247, 249, 251, 252, 257, 259, 260, 261, 263, 266, 
269, 271, 272, 273, 277, 278, 281, 283, 284, 285, 287, 291, 293, 295, 
296, 297, 301, 302, 303, 305, 308, 309, 310, 312, 314, 317, 318, 323, 
326, 327, 329, 332, 335, 336, 338, 341, 342, 344, 347, 348, 350, 351, 
353, 354, 356, 359, 360, 362, 365, 366, 368, 371, 372, 374, 375, 377, 
378, 380, 383, 386, 389, 392, 393, 395, 398, 399}

In[4]:= S[9][464] 

Out[4] = {0, 3, 6, 7, 8, 9, 12, 15, 17, 18, 21, 23, 24, 27, 29, 30,
32, 33, 36, 38, 39, 42, 45, 47, 48, 53, 54, 56, 57, 59, 60, 62, 
63, 67, 68, 69, 72, 75, 77, 78, 81, 83, 84, 87, 89, 90, 93, 96, 97,
98, 101, 102, 104, 107, 108, 111, 113, 114, 115, 117, 119, 120, 
122, 126, 133, 134, 135, 137, 138, 139, 141, 143, 145, 147, 148, 
150, 151, 152, 153, 154, 158, 164, 167, 168, 169, 172, 173, 174, 
177, 179, 180, 181, 182, 186, 188, 192, 193, 194, 195, 198, 200, 
201, 206, 207, 209, 211, 212, 214, 216, 219, 222, 224, 226, 227, 
228, 230, 232, 234, 238, 240, 242, 243, 245, 246, 248, 250, 253, 
255, 258, 259, 260, 261, 264, 266, 267, 272, 273, 274, 276, 278, 
279, 280, 285, 287, 288, 292, 293, 297, 298, 300, 301, 302, 303, 
304, 306, 307, 308, 314, 317, 319, 321, 323, 327, 331, 332, 333, 
334, 335, 336, 338, 339, 340, 342, 345, 347, 351, 353, 354, 357, 
358, 360, 363, 364, 368, 369, 371, 372, 375, 377, 378, 381, 383, 
384, 387, 389, 390, 392, 393, 397, 398, 399, 402, 405, 408, 411, 
412, 413, 414, 417, 419, 420, 422, 423, 426, 428, 429, 432, 435, 
437, 438, 441, 443, 444, 447, 449, 450, 452, 453, 458, 459, 461, 
462}

In[5]:= S[9][496]

Out[5]= {0, 1, 4, 7, 9, 10, 12, 15, 16, 19, 22, 24, 25, 27, 28, 31, 
34, 36, 37, 39, 40, 42, 43, 46, 49, 52, 54, 55, 57, 58, 59, 61, 63, 
64, 67, 69, 70, 73, 76, 79, 81, 82, 84, 85, 87, 91, 92, 94, 97, 99, 
102, 103, 108, 109, 111, 112, 114, 115, 117, 119, 120, 123, 124, 127, 
129, 132, 133, 134, 136, 138, 141, 142, 144, 147, 148, 151, 152, 154, 
156, 159, 160, 162, 164, 165, 168, 169, 170, 177, 178, 179, 182, 184, 
186, 187, 188, 189, 191, 192, 193, 197, 199, 201, 202, 203, 205, 214, 
215, 216, 218, 219, 222, 223, 226, 227, 228, 231, 232, 234, 237, 240, 
241, 244, 245, 246, 248, 252, 253, 256, 257, 259, 260, 262, 265, 266, 
270, 271, 274, 275, 278, 282, 283, 284, 285, 286, 287, 288, 289, 291, 
295, 297, 299, 300, 301, 305, 310, 312, 314, 315, 319, 320, 321, 322, 
323, 324, 328, 329, 332, 334, 337, 338, 340, 342, 345, 346, 349, 350, 
352, 355, 356, 358, 360, 364, 365, 367, 369, 370, 373, 374, 377, 379, 
382, 385, 388, 389, 390, 391, 394, 395, 397, 399, 400, 402, 405, 406, 
407, 409, 412, 415, 417, 418, 420, 421, 423, 424, 427, 429, 430, 433, 
435, 439, 442, 444, 445, 447, 448, 450, 451, 454, 457, 460, 462, 463, 
465, 466, 469, 472, 474, 475, 477, 478, 481, 482, 484, 487, 489, 490, 
492, 493}


Claude's up-next list:

* Count the order-7 partitions of {0, …, 127}. The antisymmetric ones alone number 303, and no count has been published.
  Claude: "Done: 431 partitions, 367 up to reversal. See the reply to Stan's uniqueness question below."

---

Stan notes:

This 512 result while nice is not all that important. There is no expectation that the magic value will be this low. Could be 17 though!

Claude: "17 isn't ruled out. Joins of products of the known blocks still bottom out at 2^24. Joins whose pieces cancel each other's top power sum, the trick behind Claude's 528, can't work for any k ≤ 16 with at most four pieces built from known blocks, and 17 is the first k they don't rule out. With 512 = 9, the smallest k with 2^k of order k + 1 is somewhere from 10 to 24."

336 is a 10. I had this in my package pre-Claude, so that is one error. Maybe a useful building block?

Claude: "336 is exactly 10: the residue condition mod 5 rules out 11. It doesn't help as a building block. With every known block, 336:10 and 480:12 included, joins of products still bottom out at 2^24. The obstruction is divisibility by 3: 2^k isn't a multiple of 3, but 336 and 480 are."

---

Danny Reeves and me:  The 175-year-old Prouhet result that the "power-sum exponent" of 2^n is ≥ n was proved (2019) by Stong with a very ingenious argument to not be sharp, in that for 2^51 it is 52.  We have that down to: for 2^24 it is 25, using Stong’s method. See https://en.wikipedia.org/wiki/Prouhet%E2%80%93Tarry%E2%80%93Escott_problem for defns.

---

Claude: OEIS A323629 leaves 112 out of L_7, though Berend and Golan (2006) and Theorem 3.1 of BGPW both have it.

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

Recall that in our 2019 paper we gave Stong’s clever proof that there is a subset A of {0,1,…,2^51 -1} such that, if B is A’s complement, then the sums of A^j and B^j are equal for j = 0, 1, …, 51. The point here is that the Prouhet 1851 work gets this up to exponent 50. This gives one more exponent, defeating the conjecture that the Prouhet result is sharp.

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