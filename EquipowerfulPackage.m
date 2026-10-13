(* ::Package:: *)

(* ::Input::Initialization:: *)
OddToTop[A_]:=Prepend[2 Rest[A], Total[A]];

RowReduceKernel[A_]:= RowReduce[NullSpace[A]];
BinomialArray[m_,n_]:= Table[Binomial[Range[0,n-1],r],{r,0,m-1}];
(* HalfMatrix[n,m] has dimensions n/2-Floor[m/2] \[Times]  n/2 *)
HalfMatrix[m_, n_?EvenQ]:= Module[{A=BinomialArray[m,n], Astar}, 
AStar=Reverse/@ A;  
      RowReduceKernel[(Take[#,n/2]&)/@(A+(-1)^m AStar)]];
HalfMatrixPointed[m_, n_?EvenQ]:=OddToTop[HalfMatrix[m,n]];

FullMatrix[m_, n_?EvenQ]:=RowReduceKernel[BinomialArray[m,n]];
FullMatrixPointed[m_,n_?EvenQ]:=OddToTop[FullMatrix[m,n]];

VMatrix[m_, n_?EvenQ]:= Join[HalfMatrix[m,n],Reverse[HalfMatrix[m+1,n]]];
WMatrix[m_,n_?EvenQ]:=Join[#,(-1)^m Reverse[#]]&/@VMatrix[m,n]
VMatrixPointed[n_?EvenQ,m_]:=  OddToTop[VMatrix[m,n]];
WMatrixPointed[n_?EvenQ,m_]:=  OddToTop[WMatrix[m,n]];


(* ::Input::Initialization:: *)
GetLegalUsingSymmetryConjectureModp::usage = "GetLegalUsingSymmetryConjectureModp[n,m,p] gets the legal d[p] vectors using some modular equation solving based on the binomial identities and symmetry or antisymmetry. It is very fast.";


(* ::Input::Initialization:: *)
GetLegalUsingSymmetryConjectureModp//Clear;
Options[GetLegalUsingSymmetryConjectureModp]={CheckFeasibility->False, PrimesToUse->{}, BasicTuplesBounds->Automatic};

GetLegalUsingSymmetryConjectureModp[n_,m_,p_, opts___]:= Module[{s, sign=(-1)^m,ans,r,j,tups},
{chQ, pr, tupbd} = {CheckFeasibility, PrimesToUse,BasicTuplesBounds}/. {opts} /. Options[GetLegalUsingSymmetryConjectureModp];

{s,r}=QuotientRemainder[m,p-1];
If[r==0, Return["r is 0; bad case"]];
Do[baseSetSmall[j]=1/p^s  Select[baseSet[n,m-1,p],Divisible[#, p^s]&&EvenQ[#1-Length[Select[Range[0,n-1],Mod[#1,p]==j&]]]&],{j,0,p-1}];matching=DeleteDuplicates[Sort/@ SymmetricQRules[n,p]-1]/.  {z_Integer, zz_Integer}:>{ d[z], sign d[zz]};

matchingRule = Rule @@@ matching;

freeVbles = Last/@ matching/. -d[z_] :> d[z];

try = d/@ Range[0,p-1]/. matchingRule;
eqns=Table[\!\(
\*UnderoverscriptBox[\(\[Sum]\), \(z = j\), \(p - 1\)]\(Binomial[z, j]\ try[\([z + 1]\)]\)\), {j,1,r-1}] /. x_Integer :> Mod[x,p];

eqns1=List@@Reduce[Thread[eqns==0],freeVbles,Modulus->p];
(* maybe I could LinearSolve here ??? ; this just uses simple row reduction  *) 

cons=DeleteDuplicates[Cases[eqns1,C[_],\[Infinity]]];

eqns2= Select[eqns1, !MemberQ[cons,#[[2]] ]&];
consRule=Rule @@@Reverse/@ Select[eqns1, MemberQ[cons,#[[2]] ]&];

varToIterate=Sort[Last/@ consRule];
varToIterateInd=First/@ varToIterate;
varDependent=First/@ eqns2;
varDependentInd=First/@ varDependent;
eqns3=Sort[eqns2/.consRule];
If[Length[varToIterate]>1, 
Do[coefficients[ind]=List@@(Select[eqns3,#1[[1,1]]==ind&][[1,2]])/. d[_]->1,{ind,varDependentInd}];
Do[coefficients[ind]=If[coefficients[ind]===0,(0&)/@varToIterate,coefficients[ind]],{ind,varDependentInd}],
Do[coefficients[ind]=Flatten[{List@@(Select[eqns3,#1[[1,1]]==ind&][[1,2]]/. d[_]->1)}],{ind,varDependentInd}];
Do[coefficients[ind]=If[coefficients[ind]==={0},(0&)/@varToIterate,coefficients[ind]],{ind,varDependentInd}];
];
Do[dVals[ind]=baseSetSmall[ind], {ind, varToIterateInd}];

tups = Tuples[dVals/@ varToIterateInd];
tracetupsLength = Length[tups];
tups=If[tupbd===Automatic, tups, tups[[tupbd[[1]];;tupbd[[2]]]]];
symChoice = If[OddQ[m], UseAntisymmetry,UseSymmetry];
Select[traceDomain=Flatten[Table[
     Do[ dVals[ind]=Select[baseSetSmall[ind],
Mod[coefficients[ind] . t-#, p]==0&],{ind, varDependentInd}];
p^s Table[try/.Thread[varToIterate->t]/.Thread[d/@ varDependentInd->tt], {tt, Tuples[dVals/@ varDependentInd]}],{t,tups}],1],
     (traceVec = #; Total[#]==0 &&
     If[chQ,CheckFeasibilityTuple[n,m-1,p,#,symChoice->True, OmitPrimes->Complement[Select[Range[p-1], PrimeQ], pr]], True] 
)&]];


(* ::Input::Initialization:: *)
transformPrime[m_, dvec_,p_,e_]:=(dvec-Flatten[Table[Take[dvec,-p],p^(e-1)]])/p^Quotient[m,EulerPhi[p^e]];

baseSetPrimePower[n_,k_,p_,e_]:=With[{q=p^e},Select[Range[-bound[n,q],bound[n,q]],Abs[#]<=Max[Table[countRes[p,jjj,n],{jjj,0,p-1}]]&]];



polynomialFromSet[A_] := Total[x^A] -Total[ x^Complement[ Range[0,2Length[A]-1],A]];
order[A_] :=PolynomialGCD[ polynomialFromSet[A], (1-x)^100]/. (_^n_) :> n /. 1-x->1/. x-1->1
orderPoly[p_] :=PolynomialGCD[ p, (1-x)^100]/. (_^n_) :> n /. 1-x->1/. x-1->1


Options[GetLegalPrimePowerBasic] = {UseAntisymmetry->False, UseSymmetry->False};

GetLegalPrimePowerBasic[n_, m_, p_, e_, dataForp_, opts___] := Module[{q=p^e,s,r,ans},
{aQ, sQ} = {UseAntisymmetry, UseSymmetry}/. {opts} /. Options[GetLegalPrimePowerBasic];
{s,r} = QuotientRemainder[m,EulerPhi[q]];  (* r not used here, but used later *) 
Do[baseSetSmall[j]=Select[baseSetPrimePower[n,m-1,p,e],EvenQ[#1-Length[Select[Range[0,n-1],Mod[#1,q]==j&]]]&],{j,0,q-1}];
indexSets=Table[Range[j,q-1, q/p], {j, 0, p^(e-1)-1}];  (* typo here in Bereng&Golan*) 
Do[goodtups[indset]= Join@@
Table[Select[Tuples[baseSetSmall/@indset],
Total[#]==dataForp[[First[indset]+1]]&&
And@@Table[Mod[#[[ii]],p^s]==cong,{ii,Length[indset]}]&],
 {cong,0,p^s-1}],
{indset,indexSets}];
tups=Tuples[goodtups/@ indexSets];
ans=Select[Table[Flatten[Transpose[t]],{t, tups}], Total[#]==0&&If[aQ, antiSymmetricQ[n,#], True]&&If[sQ, SymmetricQ[n,#], True]&]];
(* GetLegalPrimePowerBasic uses the bounds, the congruence, and zero-sum condition; note that by BG 3.1 & 3.3 the congruence condition is valid for all r. *) 



GetLegalPrimePowerBasicAndBinomial[n_, m_, p_, e_, dataForp_, opts___] := Module[{q=p^e,s,r},
{s, r} = QuotientRemainder[m, EulerPhi[q]]; 
basic=GetLegalPrimePowerBasic[n, m, p, e, dataForp, opts] ;
(* next we ask that several binomial sums are each div. by p *) 
Select[basic,(reduced = transformPrime[m,#,p,e];
And @@ Table[Divisible[\!\(
\*UnderoverscriptBox[\(\[Sum]\), \(z = j\), \(q - 1\)]\(Binomial[z, j]\ reduced[\([z + 1]\)]\)\),p], {j,0,r-1}])&]];


(* ::Input::Initialization:: *)
(* assumes all data is in good[p] or good[q] or goodChoice *) 
Options[GetSurvivors] = {UseSymmetryConjecture->False,UseAntisymmetry->False, UseSymmetry->False, TraceQ->False, TraceStep -> 1, MainBound->Automatic, OmitPrimes->{}, Method->"GUROBI"};GetSurvivors[ n_, m_, pMain_, primesToIterate_ , composites_, opts___] :=Module[{ans={}, var,jj},
{ aQ,sQ, trQMain, trsMain,mb,omit, useSymCon,met} = {UseAntisymmetry,UseSymmetry,TraceQ, TraceStep, MainBound,OmitPrimes, UseSymmetryConjecture, Method}/. {opts} /. Options[GetSurvivors];
If[useSymCon, If[EvenQ[m], sQ=True, aQ=True]];
omit=Flatten[{omit}];
ansGlobal={};
all=Join[primesToIterate,composites,{pMain}];
var = jj/@ all;
iterator=Sequence@@Table[{jj[pp], Min[Length[good[pp]], If[pp==pMain, mb/. Automatic -> Length[good[pp]],\[Infinity]]]}, {pp, Reverse@all}];
mPrint[iterator];
Do [(*If[trQ&&Mod[Length[jj[pMain]], trs]\[Equal]0, Print[{jj[pMain], Length[ans]}]];*) 
If[trQ ,mPrint[var]];

Do[
goodChoice[pp]=good[pp][[jj[pp]]], {pp,all}];
If[CheckFeasibilityTuple[n,m-1,pMain,goodChoice[pMain], UseAntisymmetry->aQ, UseSumConstraint->sQ, CompositesToUse->composites, OmitPrimes->omit, Method->met],
 AppendTo[ans, goodChoice/@ Sort[all]];ansGlobal=ans; If[trQMain &&Mod[Length[ans], trsMain]==0, Print[{jj[pMain], Length[ans]}]]], Evaluate[iterator]];
ans]


(* ::Input::Initialization:: *)
Options[GetLegal] = {UseAntisymmetry->False, UseSymmetry->False};

GetLegal[n_,m_,p_,opts___]:=Module[{ans,j},{s,r}=QuotientRemainder[m,p-1];{aQ,sQ}={UseAntisymmetry,UseSymmetry}/.{opts}/.Options[GetLegal];Do[baseSetSmall[j]=Select[If[r==0,baseSetrZero,baseSet][n,m-1,p],EvenQ[#1-Length[Select[Range[0,n-1],Mod[#1,p]==j&]]]&],{j,r,p-1}];ans=If[r!=0,Flatten[(FindLegal[n,m-1,#1,p]&)/@Tuples[Table[baseSetSmall[j],{j,r,p-1}]],1],Select[Flatten[Table[Tuples[Table[Select[baseSetSmall[j],Mod[#,p^s]==cong&],{j,0,p-1}]],{cong,0,p^s-1}],1],Total[#]==0&]];
Which[
aQ, Select[ans, antiSymmetricQ[n,#]&],
sQ, Select[ans, SymmetricQ[n,#]&],
!aQ && !sQ, ans]];


(* ::Text::RGBColor[0., 0., 0.]:: *)
(*(*(*(*(*(*Redo this as loop so I can check progress? NonGeneric case.   Table[]*)*)*)*)*)*)


(* ::Input::Initialization:: *)
Options[GetLegalGenericCaseMemorySave] = {TailBounds->All, CheckFeasibility->True, OmitPrimes ->{}, TraceQ->False,TraceStep->1, BalancedCases->{}, MainBound->\[Infinity]};
GetLegalGenericCaseMemorySave[n_,m_,p_, opts___]:=Module[{j,s,r}, (
{s,r}=QuotientRemainder[m,p-1];
{mb,checkQ,tb, omit,tr, bal,trStep}={MainBound,CheckFeasibility,TailBounds,OmitPrimes,TraceQ, BalancedCases, TraceStep}/. {opts} /. Options[GetLegalGenericCaseMemorySave];
Do[baseSetSmall[j]=Select[If[r==0,Print["r error"],baseSet][n,m-1,p],EvenQ[#-Length[Select[Range[0,n-1],Mod[#,p]==j&]]]&],{j,r,p-1}];
tups=Tuples[Table[baseSetSmall[j],{j,r,p-1}]];
tb = tb /. All -> {1, Length[tups]};
Flatten[Table[jTrace=j;If[tr&&Divisible[j,trStep], Print[{j, tb}]];
FL=FindLegalFaster[n,m-1,tups[[j]],p];
If[checkQ, Select[FL,CheckFeasibilityTuple[n,m-1, p, #, OmitPrimes->omit, BalancedCases->bal]&], FL], {j,tb[[1]],Min[mb, tb[[2]]]}],1])];


(* ::Text:: *)
(*Change this so that option is PrimeDataToFilterBy -> { {{0,0}}, {{0,0,0}} }   etc. Default can be {}, but I can then add what I want.  Alternative is to default the CheckFeasibility to FALSE*)


(* ::Input::Initialization:: *)
Options[GetLegalGenericCaseMemorySaveUseSymmetry] = { CheckFeasibility->True, OmitPrimes ->{}, MainBound->\[Infinity], TraceQ->False, TraceStep-> 100};
GetLegalGenericCaseMemorySaveUseSymmetry[n_,m_,p_, opts___]:=Module[{j,s,r}, (
{checkQ,omit, mb,trQ, step}={CheckFeasibility, OmitPrimes,MainBound, TraceQ, TraceStep}/. {opts}/. Options[GetLegalGenericCaseMemorySaveUseSymmetry];
{s,r}=QuotientRemainder[m,p-1];Do[baseSetSmall[j]=Select[If[r==0,Print["r error"],baseSet][n,m-1,p],EvenQ[#-Length[Select[Range[0,n-1],Mod[#,p]==j&]]]&],{j,r,p-1}];
tups=Tuples[Table[baseSetSmall[j],{j,r,p-1}]];
Print[Length[tups]];
Flatten[Table[If[trQ &&Mod[jjj,step]==0,Print[jjj]];
FL=Select[FindLegalFaster[n,m-1,tups[[jjj]],p],If[OddQ[m],antiSymmetricQ, SymmetricQ][n,p,#]&];
If[checkQ && Complement[Select[Range[p-1],PrimeQ],omit]!={},  Select[FL,If[OddQ[m],CheckFeasibilityTuple[n,m-1, p, #, UseAntisymmetry->True, opts], CheckFeasibilityTuple[n,m-1, p, #, UseSymmetry->True, opts]]&],FL], {jjj,Min[mb,Length[tups]]}],1])]


differenceToResidueCount[n_, d_] := Table[1/2  ( countRes[Length[d], i, n] + d[[i+1]]),
    {i,0,Length[d] - 1}];


(* ::Input::Initialization:: *)
definetups[n_, k_, p_] := (m=k+1;
s=Quotient[m,p-1];r=Mod[m,p-1];
baseSet[n,k,p];
baseSetSmall[p-1] =Select[baseSet[n,k,p], EvenQ[#-Length[Select[Range[0, n-1], Mod[#,p]==p-1&]]]&];
tups=Tuples[baseSetSmall[p-1], 1]);
antiSymmetricQ//Clear;
antiSymmetricQ[n_,p_, dvec_]:=And@@Table[dvec[[jj+1]]==-dvec[[Mod[n-jj,p,1]]],{jj,0,p-1}];
antiSymmetricQ[n_, dvec_]:=And@@Table[dvec[[jj+1]]==-dvec[[Mod[n-jj,Length[dvec],1]]],{jj,0,Length[dvec]-1}];
SymmetricQ[n_,p_, dvec_]:=And@@Table[dvec[[jj+1]]==dvec[[Mod[n-jj,p,1]]],{jj,0,p-1}];
SymmetricQ[n_,dvec_]:=And@@Table[dvec[[jj+1]]==dvec[[Mod[n-jj,Length[dvec],1]]],{jj,0,Length[dvec]-1}];
SymmetricQRules[n_,p_]:=Table[{jj+1,Mod[n-jj,p,1]},{jj,0,p-1}];


(* ::Input::Initialization:: *)
meld[fail1_, fail2_]:=SortBy[DeleteDuplicates[ Join@@#], Length]& /@ Select[Tuples[{fail1,fail2}],DuplicateFreeQ[Length/@DeleteDuplicates[ Join@@#]]&];

meldFast[a_,b_,indscommona_,indscommonb_] := Flatten[Table[Table[
SortBy[DeleteDuplicates[Join[f,s]],Length],{s,Select[a,#[[indscommona]]==f[[indscommonb]]&]}],{f,b}],1];


(* ::Input::Initialization:: *)
HexCode[A_]:=Module[{digs,p,n=Max[A]},pp=p=Table[If[MemberQ[A,i],1,0],{i,0,n}];digs=(FromDigits[#1,2]&)/@(qq=Partition[p,4, 4,1,0]);StringJoin@@(ToString/@( digs/. Thread[{10,11,12,13,14,15}->{"A","B","C","D","E","F"}]))];

HexDecode[c_String]:=-1+Flatten[Position[
Join@@(PadLeft[IntegerDigits[#1,2],4]&)/@ToExpression/@(Characters[c]/. Thread[{"A","B","C","D","E","F"}->{10,11,12,13,14,15}]),1]]



Clear[d, countRes];
countRes[p_,i_,n_]:=countRes[p,i,n]=Length[Select[Range[0,n-1],Mod[#1,p]==i&]]
countRes[p_,i_, p1_, i1_,n_]:=countRes[p,i,p1,i1,n]=Length[Select[Range[0,n-1],Mod[#1,p]==i&& Mod[#1,p1]==i1&]];
FindSetGoodQ[n_,p_, example_]:= Module[{A,B},
var=Flatten[{A/@Range[0,p-1],B/@Range[0,p-1]}];{}!=Solve[Join[Table[A[i]-B[i]==example[[i+1]],{i,0,p-1}],Table[A[i]+B[i]==countRes[p,i,n],{i,0,p-1}]],var,Integers]];
FindSet[n_,p_, example_]:= (
varFS=Flatten[{A/@Range[0,p-1],B/@Range[0,p-1]}];Solve[Join[
Table[A[i]-B[i]==example[[i+1]],{i,0,p-1}],
Table[A[i]+B[i]==countRes[p,i,n],{i,0,p-1}]],varFS]);

FindSetNotFull//Clear
FindSetNotFull[n_,p_, example_, locs_]:=FindSetNotFull[n,p, example, locs]= (
varFS=Flatten[{A/@locs,B/@locs}];
(A/@ locs )/. First@Solve[Join[
Table[A[locs[[i]]]-B[locs[[i]]]==example[[i]],{i,Length@locs}],
Table[A[i]+B[i]==countRes[p,i,n],{i,locs}]],varFS]);

(* below are for k = 6 *) 
(*Clear[good] *)

(* these below are special for 184 *) 

startVals[p_]:=Last/@ good[p];

dVectors2[n_, k_]:= Module[{bound=Ceiling[n/2], s=k+1},
Select[Tuples[Range[-bound, bound], 2], Total[#]==0 && Mod[#[[1]]-#[[2]],2^s]==0 
Mod[#[[1]]-countRes[2,0,n],2]==0  &&
Mod[#[[2]]-countRes[2,1,n],2]==0  &&
(q=IntegerExponent[n,2]; If[k==2^q-2, Abs[#[[1]]-#[[2]]]>=2^(2^q-1), True])&]];

dVectors3Caser0[n_,k_]:=Module[{bound=Ceiling[n/3],s=Floor[(k+1)/2]},
Select[Tuples[Range[-bound,bound],3],
Total[#1]==0&&Mod[#1[[1]]-#1[[2]],3^s]==0&&Mod[#1[[1]]-#1[[3]],3^s]==0&&
Mod[#1[[1]]-countRes[3,0,n],2]==0&&
Mod[#1[[2]]-countRes[3,1,n],2]==0&&
Mod[#1[[3]]-countRes[3,2,n],2]==0&]];

dVectors3CaserNot0[n_,k_]:=Module[{bound=Ceiling[n/3],s=Floor[(k+1)/2], r=Mod[k+1,2]},
Select[ttt=Tuples[Range[-bound,bound],2],(vec=#;
PrependTo[vec, -Total[vec]];
Mod[vec[[1]],3^s]==0&&Mod[vec[[2]],3^s]==0&&Mod[vec[[3]],3^s]==0&&
Mod[vec[[1]]-countRes[3,0,n],2]==0&&
Mod[vec[[2]]-countRes[3,1,n],2]==0&&
Mod[vec[[3]]-countRes[3,2,n],2]==0&&
And@@Table[Divisible[\!\(
\*UnderoverscriptBox[\(\[Sum]\), \(z = j\), \(3 - 1\)]\(Binomial[z, j]\ vec[\([z + 1]\)]\)\),3^(s+1)], {j,0,r-1}])&]];


(* ::Input::Initialization:: *)
bound[n_, p_]:=Ceiling[n/p];
baseSet[n_,k_, p_]:=With[{s=Quotient[k+1,p-1] },Select[Range[-bound[n,p],bound[n,p]],Divisible[#,p^s]&&Abs[#]<=Max[Table[countRes[p,j,n],{j,0,p-1}]]&]];

baseSetrZero[n_,k_, p_]:=With[{s=Quotient[k+1,p-1] },Select[Range[-bound[n,p],bound[n,p]],Abs[#]<=Max[Table[countRes[p,j,n],{j,0,p-1}]]&]];

PossibledValues[n_,k_,p_,j_]:=Select[baseSet[n,k,p], Mod[#-countRes[p,j,n],2]==0&];  

(* this fills our by binomial coeffs and then selects those that sum to 0  *) 

Options[FindLegal]={SpecialConditions->(True&)};
FindLegal[n_, k_, start_, p_, opts___]:= Module[{i,d,new,newans,s=Floor[(k+1)/(p-1)], r=Mod[k+1,p-1],eqns,bb=baseSet[n,k,p],ans={start}},
spec=SpecialConditions /. {opts}/.Options[FindLegal];
eqns=Table[Divisible[\!\(
\*UnderoverscriptBox[\(\[Sum]\), \(z = j\), \(p - 1\)]\(Binomial[z, j]\ d[z]\)\),p^(s+1)], {j,0,r-1}];
Do[newans={};
Do[new=Select[bb,( Divisible[eqns[[i+1,1]]/.d[i]->#,p^(s+1)]/. Thread[d/@Range[i+1,p-1] -> Take[a, p-i-1]])
&&Mod[#-countRes[p,i,n],2]==0&];
newans=Join[newans,Prepend[a,#]& /@ new],  {a, ans}]; ans=newans, {i,r-1,0,-1}];
newans=Select[newans, Total[#]==0&];
Select[newans, spec]];
Options[FindLegalFaster]={SpecialConditions->(True&), RangeStartFinish->Automatic};
FindLegalFaster[n_, k_, start_, p_, opts___]:= Module[{i,d,new,newans,s=Floor[(k+1)/(p-1)], r=Mod[k+1,p-1],eqns,bb,ans={start}},
{rsf,spec}={RangeStartFinish,SpecialConditions} /. {opts}/.Options[FindLegalFaster];

bb=baseSet[n,k,p];
eqns=Table[Divisible[\!\(
\*UnderoverscriptBox[\(\[Sum]\), \(z = j\), \(p - 1\)]\(Binomial[z, j]\ d[z]\)\),p^(s+1)], {j,0,r-1}];
Do[bbsmall[i]= Select[bb, Mod[#-countRes[p,i,n],2]==0&], {i, r-1, 0, -1}];

Do[newans={};

Do[new=Select[If[!ListQ[rsf], bbsmall[i], bbsmall[i][[rsf[[1]];;rsf[[2]]]]],( Divisible[eqns[[i+1,1]]/.d[i]->#,p^(s+1)]/. Thread[d/@Range[i+1,p-1] -> Take[a, p-i-1]])&];
newans=Join[newans,Prepend[a,#]& /@ new],  {a, ans}]; ans=newans, {i,r-1,0,-1}];
newans=Select[newans, Total[#]==0&];
Select[newans, spec]];




FillInListFromFeasibleStart//Clear;
Options[FillInListFromFeasibleStart]= {TraceQ->False, OmitPrimes->{}, UseSumConstraint->False,PowersToUse->{1}, NumberAtStartToSkip->0, InitialCase->True, ExtendAndCheckFeasibles->False,CompositesToUse->{}, UseAntisymmetry->False, UseSymmetry->False};
FillInListFromFeasibleStart[n_, k_, p_, dList_, opts___]/; (Length[dList]==p):=dList ;
FillInListFromFeasibleStart[n_, k_, p_, dList_, opts___]/;(Length[dList]<=p-1) := Module[{FLcheck, 
s=Quotient[k+1,p-1], r=Mod[k+1,p-1],primes,ans,kParity, kBin, dTry, dVal, varILP, varParity,varBin, varAll, con1, con2, con3,con3A,sumQconPrime, conParity,conSum0, conBinomial,sol, conAll, dj,x, trQ, mPrint,newans, omitP, sumQ, numskip, initQ},

{FLcheck,pow,omitP, trQ, sumQ,numskip, initQ,nonprimes, asQ, symQ} ={ExtendAndCheckFeasibles,PowersToUse,OmitPrimes,  TraceQ, UseSumConstraint, NumberAtStartToSkip,InitialCase,CompositesToUse, UseAntisymmetry, UseSymmetry} /. {opts} /. Options[FillInListFromFeasibleStart]; 
If[!ListQ[pow], pow={pow}];
If[initQ,finalAnswer={}];
primes = Complement[Select[Range[2,p-1], PrimeQ],omitP];

If[r==0, Return["Residue is 0, bad case"]];
mPrint = If[trQ, Print, mPrint];
mPrint[primes];
mPrint["trying for a vector of length ", p-r];
mPrint[Row[{"starting ", dList}]];
dTry[j_]:=Select[baseSet[n,k,p], Mod[#-countRes[p,j,n],2]==0&]; (* constraint (c) *) (* using only positives is NOT adequate *) 
ans=dList;
dj=p-1-Length[dList];

Do[dVal[x]=dList[[x-dj]], {x,dj+1 ,p-1}];
Do[dVal[dj]=ddd;
mPrint[Row[{"Residue is ", dj, "; trying for d(",p,",", dj, ")= ", dVal[dj]}]];
varILP = x/@Range[0,n-1];

varBin =Table[kBin[j], {j,0,r-1}]; 
varAll=Join[varILP, varBin];
con1 = Thread[varAll\[Element]Integers];con2 = Thread[0<=varILP<=1];
con3 = Total[varILP]==n/2; con3A = Table[Range[0,n-1]^pp . varILP==Sum[i^pp,{i,0,n-1}]/2, {pp,pow}]; 

Do[conPrime[pp]=Table[Total[Select[varILP,Mod[#[[1]],pp]==j&]]==(A[j]/. FindSet[n,pp,goodChoice[pp]][[1]]), 
{j,0,pp-2}],{pp,primes}];

Do[conNonprime[pp]=Table[Total[Select[varILP,Mod[#[[1]],pp]==j&]]==(A[j]/. FindSet[n,pp,goodChoice[pp]][[1]]), 
{j,0,pp-2}],{pp, nonprimes}];

conAntisym = If[asQ,And@@ Table[x[i] == 1- x[n-1-i], {i, 0, n/2}], True];
conSym = If[symQ,And@@ Table[x[i] ==  x[n-1-i], {i, 0, n/2}], True];

Do[dVal[j]=-countRes[p,j,n]+2Total[Select[varILP,Mod[#[[1]],p]==j&]],{j,0,dj-1}];

     conSum0 = Sum[dVal[j], {j,0,p-1}]==0;  (* constraint (b) *)
conBinomial=Table[\!\(
\*UnderoverscriptBox[\(\[Sum]\), \(z = j\), \(p - 1\)]\(Binomial[z, j]\ dVal[z]\)\)==kBin[j] p^(s+1),{j,0,r-1}]; (* constraint (e) *) 
solTemp=sol=Quiet@NMinimize[{0,
conAllTemp=conAll=Flatten[{con1,con2,con3,If[sumQ, con3A,{}], conPrime/@ primes, conNonprime/@ nonprimes,conSum0,conBinomial, conAntisym, conSym}]},varAll];
If[And@@conAll/.sol[[2]],newans=Prepend[ans, ddd];mPrint["newans ", newans];
If[Length[newans]==p-r , Print["Found partial feasible vector: " ,newans];AppendTo[finalAnswer, newans]];
Print[{newans, ddd,  successsuccesssuccesssuccesssuccesssuccesssuccesssuccesssuccesssuccesssuccess}];
 If[Length[newans]<p-r, FillInListFromFeasibleStart[n,k,p,newans, TraceQ->trQ, OmitPrimes->omitP, ExtendAndCheckFeasibles->False, UseSumConstraint->sumQ, NumberAtStartToSkip->0, InitialCase->False], Print[{stopping,Length[newans], finalAnswer}]]],
{ddd, Drop[dTry[dj],numskip]}]; 

If[FLcheck,
     mPrint[Row[{"Found these ", finalAnswer, " and now extending and checking"}]];
Table[{t, CheckFeasibilityTuple[n,k,p,t]}, {t, Flatten[FindLegal[n,k,#,p] &/@  finalAnswer,1]}], finalAnswer]];

Options[FillInListFromFeasibleStartrZero]= {TraceQ->False, OmitPrimes->{}, UseSumConstraint->False, NumberAtStartToSkip->0, InitialCase->True, ExtendAndCheckFeasibles->False};
FillInListFromFeasibleStartrZero[n_, k_, p_, dList_/; (Length[dList]==p), opts___]:=dList ;
FillInListFromFeasibleStartrZero[n_, k_, p_, dList_/; (Length[dList]<=p-1), opts___] := Module[{
s=Quotient[k+1,p-1], r=Mod[k+1,p-1],primes,ans,kParity, kBin, dTry, dVal, varILP, varParity,varBin, varAll, con1, con2, con3,con3A,sumQconPrime, conParity,conSum0, conBinomial,sol, conAll, dj,x, trQ, mPrint,newans, omitP, sumQ, numskip, initQ},

{FLcheck, omitP, trQ, sumQ,numskip, initQ} ={ExtendAndCheckFeasibles, OmitPrimes,  TraceQ, UseSumConstraint, NumberAtStartToSkip,InitialCase} /. {opts} /. Options[FillInListFromFeasibleStartrZero]; 
If[initQ,finalAnswer={}];
primes = Complement[Select[Range[2,p-1], PrimeQ],omitP];
If[r>=1, Return["Residue is not 0, bad case"]];
mPrint = If[trQ, Print, mPrint];
mPrint["trying for a vector of length ", p-r];
mPrint[Row[{"starting ", dList}]];
dTry[j_]:=Select[baseSetrZero[n,k,p], Mod[#-countRes[p,j,n],2]==0&]; (* constraint (c) *) (* using only positives is NOT adequate *) 
ans=dList;
dj=p-1-Length[dList];

Do[dVal[x]=dList[[x-dj]], {x,dj+1 ,p-1}];
Do[dVal[dj]=ddd;
mPrint[Row[{"Residue is ", dj, "; trying for d(",p,",", dj, ")= ", dVal[dj]}]];
varILP = x/@Range[0,n-1];

varAll=Join[varILP];
con1 = Thread[varAll\[Element]Integers];con2 = Thread[0<=varILP<=1];
con3 = Total[varILP]==n/2; con3A = Range[0,n-1] . varILP==(1/4 (-1+n) n); 

Do[conPrime[pp]=Table[Total[Select[varILP,Mod[#[[1]],pp]==j&]]==(A[j]/. FindSet[n,pp,goodChoice[pp]][[1]]), 
{j,0,pp-2}],{pp,primes}];

Do[dVal[j]=-countRes[p,j,n]+2Total[Select[varILP,Mod[#[[1]],p]==j&]],{j,0,dj-1}];
conAllEqual = Table[dVal[0]==dVal[j], {j,1, dj-1}];
     conSum0 = Sum[dVal[j], {j,0,p-1}]==0;  (* constraint (b) *)
conBinomial=Table[\!\(
\*UnderoverscriptBox[\(\[Sum]\), \(z = j\), \(p - 1\)]\(Binomial[z, j]\ dVal[z]\)\)==kBin[j] p^(s+1),{j,0,r-1}]; (* constraint (e) *) 
sol=Quiet@NMinimize[{0,
conAllTemp=conAll=Flatten[{con1,con2,con3,If[sumQ, con3A,{}], conPrime/@ primes,conSum0,conAllEqual}]},varAll];
If[And@@conAll/.sol[[2]],newans=Prepend[ans, ddd];
If[Length[newans]==p-r, Print["Found partial feasible vector: " ,newans];AppendTo[finalAnswer, newans]];
mPrint[{newans, ddd,  success}];
 If[Length[newans]<p-r, FillInListFromFeasibleStartrZero[n,k,p,newans, TraceQ->trQ, OmitPrimes->omitP, UseSumConstraint->sumQ, NumberAtStartToSkip->0, InitialCase->False], Print[{stopping}]]],
{ddd, Drop[dTry[dj],numskip]}]; 
If[FLcheck,Flatten[FindLegal[n,k,#,p] &/@  finalAnswer,1], finalAnswer]];




(* ::Input::Initialization:: *)
(* Try again with no kMult b/c divisibility is included in dTry and baseset !!  

But conBinomial seems important --  Yes. All dvals used to find feasibility ???
*) 
Options[CheckFeasibilityTuple] = {UseSumConstraint->False, TraceQ->False, PowersToUse->{1}, OmitPrimes->{}, CompositesToUse->{}, UseAntisymmetry->False,
 UseSymmetry->False, UseTailBounds -> Full, BalancedCases->{}, Method->"GUROBI"} ;
CheckFeasibilityTuple[n_,k_,p_, dList_, opts___]:= Module[{
s=Quotient[k+1,p-1], r=Mod[k+1,p-1],primes ,ans,  dTry, dVal, varILP, varAll,
(* con1, con2, con3, conPrime,conSum0, x,  mPrint, *) sumQ,conPrimeLast,var,j},
{met,sumQ,trQ,powers, omit, nonprimes, antisym, sym, tailBds, balData} ={ Method,UseSumConstraint, TraceQ, PowersToUse,OmitPrimes, CompositesToUse, UseAntisymmetry, UseSymmetry, UseTailBounds,BalancedCases} /. {opts} /. Options[CheckFeasibilityTuple];
primes = Complement[Select[Range[2,p-1], PrimeQ], omit];
If[r==0, XXReturn["Residue is 0, bad case"]];
If[trQ, mPrint=Print];
tailBds = tailBds /. Full -> {0,p-1};
(*Do[dVal[x]=dList\[LeftDoubleBracket]x+1\[RightDoubleBracket], Prepend[tailBds, x]];*)
var = x/@Range[0,n-1];

con1 = Thread[var\[Element]Integers];con2 = Thread[0<=var<=1];con3 = Total[var]==n/2;
con3A =If[sumQ, Table[Range[0,n-1]^pow . var==Sum[i^pow, {i, 0, n-1}]/2, {pow, powers}], True]; 
con3A =If[sumQ, Table[Binomial[Range[0,n-1],pow] . var==Sum[Binomial[i,pow], {i, 0, n-1}]/2, {pow, powers}], True]; 
conAntisym = If[antisym,And@@ Table[x[i] == 1- x[n-1-i], {i, 0, n-1}], True];
conSym = If[sym,And@@ Table[x[i] == x[n-1-i], {i, 0, n-1}], True];

If[sumQ===UseSumConstraints, Print[{ERROR, sumQ, powers}]];

Do[conPrime[pp]=Table[Total[Select[var,Mod[#[[1]],pp]==j&]]==(A[j]/. FindSet[n,pp,goodChoice[pp]][[1]]), 
{j,0,pp-2}],{pp, Complement[primes, omit]}];

conBal=Table[Total[Select[var,MemberQ[caseBal=balData[[i,2]],Mod[#[[1]],pBal=balData[[i,1]]]]&]]==
1/2 Sum[countRes[pBal,j,n], {j, caseBal}], {i, Length[balData]}];  (* this constraint is for things like { {5,{0,1}}, {7, {6}}}, which means that certain classses or sets of classes are balanced *) 

Do[conNonprime[pp]=Table[Total[Select[var,Mod[#[[1]],pp]==j&]]==(A[j]/. FindSet[n,pp,goodChoice[pp]][[1]]), 
{j,0,pp-2}],{pp, nonprimes}];  

(* check next one carefully; it is fine *) 
conPrimeLast=Table[dList[[j+1]]==-countRes[p,j,n]+2Total[Select[var,Mod[#[[1]],p]==j&]],Evaluate@Prepend[tailBds,j]];

sol=Quiet@NMinimize[{0,conAll=Flatten[{con1,con2,con3, conAntisym,conSym, conPrime/@ primes,conBal,conNonprime/@ nonprimes,conPrimeLast,If[sumQ,con3A,{}]}]},var,
Method->met];

If[And@@conAll/.sol[[2]],True,False, False]];

MakeAntisymmetric[A_, n_]:= Union[A,Complement[Range[n/2,n-1],n-1-A]]
MakeSymmetric[A_, n_]:= Union[A,n-1-A]



(* ::Section:: *)
(*ILPFilter*)


(* ::Input::Initialization:: *)
ILPFilterFeasibleQ[n_, m_, rule_,variable_ ,opts___] := ListQ[ILPFilter[n, m, rule,variable,opts]];

qr[m_,p_] := QuotientRemainder[m,p-1];    (* gets the s and r values; I should have called this sr[] for clarity *) 
genericQ[p_,m_] := qr[m,p][[2]]!=0;       
nongenericQ[p_,m_] := qr[m,p][[2]]==0;

Options[ILPFilter] = {UseSymmetryConjecture->False,UsePowerSumUpTo->-1, ExtraConstraints->{}, IncludeSet->{}, NotIncludeSet->{}};   (* three options; default is to use no symmetry and no power sums *) 

(* 4 and 9 are allowed in fixed primes *)


(* ::Text:: *)
(*The function below works thus: *)
(*Input is n and m of course. *)
(*Then the fixedprimerules (4 and 9 can also be used -- I have not studied 8 much, but surely it could be used to) set the completely specified d-vectors in the form  2 -> {0,0}, say. *)
(*variablePrimes must be prime, can be the generic or nongeneric cases, and should be a list, such as {11} or {17,19}. *)
(**)
(*The program will then set up very simple constraints for all the fixed cases, and set up the more complex constraints for the variable cases. *)
(**)
(*The variables include kbin and kdiv which are the multipliers when a number is forced to be even, or divisible by, say, 11^2.*)
(**)
(*The output is either a set A that is the witness, or $Failed. Some care is needed, b/c we want $Failed only if it fails to find a solution, but not if there is some error in the constraints causing failure of the ILP.*)
(**)


ILPFilter::usage = "variablePrimes can be a list or a single prime";

ILPFilter[n_,m_,fixedPrimesVectors_ /; Depth[fixedPrimesVectors] == 3, variablePrimes_, opts___] :=
ILPFilter[n,m, Table[Length[fp] -> fp, {fp,fixedPrimesVectors}], variablePrimes, opts]; 


ILPFilter[n_,m_,fixedPrimesRules_, variablePrimes_, opts___]:= Module[{p,j, varMain, varDiv, pGen, pNotGen,
fixedPrimes, dvec,varParity, varDivNotGen,varBinDiv, conSym, conAntisym, conDivNotGen, conMain1,conBin1, donDiv2, conDiv1, dVal,
symConjQ, powMax,extra,asQ, symQ,varAll, conIntegers, conDiv2, kdiv, kbin, kdivnotgen, kparitynotgen, kparity,
varParityNotGen, conBin2, conPrimeFixedDivisibility, sol, conAll, conParity1, conParity2, conParityNotGen, conPowers,conPrimeFixed},
{symConjQ, powMax,extra, inc,notinc} = {UseSymmetryConjecture, UsePowerSumUpTo, ExtraConstraints, IncludeSet, NotIncludeSet} /. {opts} /. Options[ILPFilter];
asQ = symQ = False;

If[symConjQ, If[EvenQ[m], symQ = True, asQ = True]];   (* use the Symmetry Conjecture *) 
mmPrint@{asQ, symQ, powMax};

fixedPrimes = First /@ fixedPrimesRules;     (* get the fixed primes *) 
Do[dvec[p] = p /.fixedPrimesRules,{p, fixedPrimes}];

pGen = Select[Flatten[{variablePrimes}], genericQ[#,m]&];    (* define the variable primes that have r \[GreaterEqual] 1 *) 
pNotGen = Select[Flatten[{variablePrimes}], nongenericQ[#,m]&];   (* define the variable primes that have r = 0 *)

varMain = x /@ Range[0,n-1];
varDiv=Flatten[Table[kdiv[p,j], {p, pGen}, {j,0,p-1}]];
varDivNotGen=Flatten[Table[kdivnotgen[p,j], {p, pNotGen}, {j,0,p-1}]];
varBinDiv=Flatten[Table[kbin[p,j], {p, pGen}, {j,0,p-1}]];
varParity = Flatten[Table[kparity[p,j], {p, pGen}, {j,0,p-1}]];
varParityNotGen = Flatten[Table[kparitynotgen[p,j], {p, pNotGen}, {j,0,p-1}]];
varAll=Flatten[{varMain, varDiv, varBinDiv, varParity,varParityNotGen,varDivNotGen}];


conAntisym = If[asQ,And@@ Table[x[i] == 1- x[n-1-i], {i, 0, n/2}], True];
conSym = If[symQ,And@@ Table[x[i] ==  x[n-1-i], {i, 0, n/2}], True];
conInc = x[#] == 1 & /@ inc;
conNotInc = x[#] == 0 & /@ notinc;
(* The next uses the simple countRes subroutine to get the values of the d-vectors from the x[i] where i is in the right class. This code is the same for generic and nongeneric case. 
So from here one dVal can be used to get the values of the d-vectors *) 

Do[dVal[p,j] = -countRes[p,j,n]+2 Total[Select[varMain,Mod[#[[1]],p]==j&]],{p, pGen},{j,0,p-1}];
Do[dVal[p,j]=-countRes[p,j,n]+2 Total[Select[varMain,Mod[#[[1]],p]==j&]],{p, pNotGen},{j,0,p-1}];

conIntegers = Thread[varAll\[Element]Integers];

conMain1 = Thread[0 <= varMain <= 1];
conDiv1 = Flatten[Table [- Ceiling[n/p]-1<= kdiv[p,j]<= Ceiling[n/p], {p, pGen}, {j,0,p-1}]]/. {}->True;
conDiv2 = Flatten[Table [p^qr[m,p][[1]]  kdiv[p,j]== dVal[p,j], {p, pGen}, {j,0,p-1}]]/. {}->True;

conDivNotGen = Flatten[Table [p^qr[m,p][[1]]  kdivnotgen[p,j]== dVal[p,j] - dVal[p,0], {p, pNotGen}, {j,1,p-1}]]/. {}->True;

mPrint[{pGen, pNotGen, conDivNotGen}];

conBin1 = Flatten[Table[
-1+Floor[(((p-j) Binomial[p,j]) n)/((1+j) p)] <= kbin[p,j]<=Floor[(((p-j) Binomial[p,j]) n)/((1+j) p)],{p,pGen},{j,qr[m,p][[2]],p-1}]]/. {}->True;

conBin2=Flatten[Table[
\!\(
\*UnderoverscriptBox[\(\[Sum]\), \(z = j\), \(p - 1\)]\(Binomial[z, j]\ dVal[p, z]\)\) == kbin[p,j] p^(qr[m,p][[1]]+1),{p,pGen},{j,0,qr[m,p][[2]]-1}]]/. {}->True;
  
Do[conPrimeFixedDivisibility[pp]=Table[Total[Select[varMain,Mod[#1[[1]],pp]==j&]]==(A[j]/. FindSet[n,pp,dvec[pp]][[1]]),{j,0,pp-1}],{pp,fixedPrimes}];

conPrimeFixed=Flatten[conPrimeFixedDivisibility/@ fixedPrimes]/. {}->True;
mmPrint[conPrimeFixed];

conParity1 = Table[-(dVal[p,j]- countRes[p,j,n])<=kparity[p,j] <= (dVal[p,j]- countRes[p,j,n]), {p, pGen},{j,0,p-1}]/. {}->True;   (* BAD b/c sign of bounds is not known *) 

conParity1 =True;

conParity2=Flatten[Table[kparity[p,j] * 2 == dVal[p,j]- countRes[p,j,n], {p, pGen},{j,0,p-1}]]/. {}->True; 

conParityNotGen=Flatten[Table[2 kparitynotgen[p,j] == dVal[p,j]- countRes[p,j,n], {p, pNotGen},{j,0,p-1}]]/. {}->True; 
mPrint[conParityNotGen];
conPowers=If[powMax>=0,Prepend[Table[ Range[0,n-1]^exp . varMain==Sum[i^exp, {i, 0, n-1}]/2, {exp, 1, powMax}], 2 Total[varMain]==n], True];   (* set up any power-sum constraints *) 

(* next is the call to NMinimize which calls ILP in the form of COIN-OR *) 
extra = extra /. {} -> True;
sol=NMinimize[{0,conAllGlobal = Flatten[{
conSym, conAntisym, conMain1,conIntegers, (* conDiv1, *) 
conDiv2,(* conBin1,*)  conBin2, conPrimeFixed, (* conParity1,*) 
 conParity2, conPowers, conDivNotGen, conParityNotGen, extra, conInc}]}, varAll];
Which[Head[sol]===List &&IntegerQ[x[1]/. sol[[2]]],First/@ First/@ Select[sol[[2]],Head[#[[1]]]===x&&  #[[2]]==1&],
(x[1]/. sol[[2]])===Indeterminate, $Failed, 
True, $Failed] ]


Options[ILPCall] = {UseSymmetry->False, UseAntisymmetry->False, UseZeroPowerSum->False};

ILPCall[maxpower_, opts___]:= Module[{p},
{asQ, symQ, powQ} =  {UseSymmetry, UseAntisymmetry, UseZeroPowerSum}/.{opts} /. Options[ILPCall];

varMain = x/@ Range[0,n-1];
varDiv=Flatten[Table[kdiv[p,j], {p, pGen}, {j,0,p-1}]];
varDivNotGen=Flatten[Table[kdivnotgen[p,j], {p, pNotGen}, {j,0,p-1}]];
varBinDiv=Flatten[Table[kbin[p,j], {p, pGen}, {j,0,p-1}]];
varParity = Flatten[Table[kparity[p,j], {p, pGen}, {j,0,p-1}]];
varParityNotGen = Flatten[Table[kparitynotgen[p,j], {p, pNotGen}, {j,0,p-1}]];
varAll=Flatten[{varMain, varDiv, varBinDiv, varParity,varParityNotGen,varDivNotGen}];


conAntisym = If[asQ,And@@ Table[x[i] == 1- x[n-1-i], {i, 0, n/2}], True];
conSym = If[symQ,And@@ Table[x[i] ==  x[n-1-i], {i, 0, n/2}], True];

Do[dVal[p,j]=-countRes[p,j,n]+2Total[Select[varMain,Mod[#[[1]],p]==j&]],{p, pGen},{j,0,p-1}];
Do[dVal[p,j]=-countRes[p,j,n]+2Total[Select[varMain,Mod[#[[1]],p]==j&]],{p, pNotGen},{j,0,p-1}];

conIntegers = Thread[varAll\[Element]Integers];

conMain1 = Thread[0<=varMain<=1];
conDiv1 = Flatten[Table [- Ceiling[n/p]-1<= kdiv[p,j]<= Ceiling[n/p], {p, pGen}, {j,0,p-1}]]/. {}->True;
conDiv2 = Flatten[Table [p^qr[m,p][[1]]  kdiv[p,j]== dVal[p,j], {p, pGen}, {j,0,p-1}]]/. {}->True;

conDivNotGen = Flatten[Table [p^qr[m,p][[1]]  kdivnotgen[p,j]== dVal[p,j]-dVal[p,0], {p, pNotGen}, {j,1,p-1}]]/. {}->True;


conBin1 = Flatten[Table[-1+Floor[(((p-j) Binomial[p,j]) n)/((1+j) p)]<=kbin[p,j]<=Floor[(((p-j) Binomial[p,j]) n)/((1+j) p)],{p,pGen},{j,qr[m,p][[2]],p-1}]]/. {}->True;
conBin2=Flatten[Table[\!\(
\*UnderoverscriptBox[\(\[Sum]\), \(z = j\), \(p - 1\)]\(Binomial[z, j]\ dVal[p, z]\)\)==kbin[p,j] p^(qr[m,p][[1]]+1),{p,pGen},{j,0,qr[m,p][[2]]-1}]]/. {}->True;
  Do[conPrimeFixedDivisibility[pp]=Table[Total[Select[varMain,Mod[#1[[1]],pp]==j&]]==(A[j]/. FindSet[n,pp,dvec[pp]][[1]]),{j,0,pp-1}],{pp,fixedPrimes}];

conPrimeFixed=Flatten[conPrimeFixedDivisibility/@ fixedPrimes]/. {}->True;
mPrint[conPrimeFixed];

conParity1 = Table[-(dVal[p,j]- countRes[p,j,n])<=kparity[p,j] <= (dVal[p,j]- countRes[p,j,n]), {p, pGen},{j,0,p-1}]/. {}->True;   (* BAD b/c sign of bounds is not known *) 

conParity1 =True;

conParity2=Flatten[Table[kparity[p,j] * 2 == dVal[p,j]- countRes[p,j,n], {p, pGen},{j,0,p-1}]]/. {}->True; 

conParityNotGen=Flatten[Table[2 kparitynotgen[p,j] == dVal[p,j]- countRes[p,j,n], {p, pNotGen},{j,0,p-1}]]/. {}->True; 

conPowers=If[powQ,Prepend[Table[ Range[0,n-1]^exp . varMain==Sum[i^exp, {i, 0, n-1}]/2, {exp, 1, maxpower}], 2 Total[varMain]==n], True];

conAll=Flatten[{
conSym,conAntisym,conMain1,conIntegers, (* conDiv1, *) 
conDiv2,(* conBin1,*)  conBin2, conPrimeFixed, (* conParity1,*) 
 conParity2, conPowers, conDivNotGen, conParityNotGen}];
 
sol=NMinimize[{0, conAll=Flatten[{
conSym,conAntisym,conMain1,conIntegers, (* conDiv1, *) 
conDiv2,(* conBin1,*)  conBin2, conPrimeFixed, (* conParity1,*) 
 conParity2, conPowers, conDivNotGen, conParityNotGen}]}, varAll];
Which[Head[sol]===List &&IntegerQ[x[1]/. sol[[2]]],First/@ First/@ Select[sol[[2]],Head[#[[1]]]===x&&  #[[2]]==1&],
(x[1]/. sol[[2]])===Indeterminate, $Failed, 
True, $Failed] ]



(* ::Input::Initialization:: *)
qr[m_,p_] := QuotientRemainder[m,p-1];
genericQ[p_,m_] := qr[m,p][[2]]!=0;
nongenericQ[p_,m_] := qr[m,p][[2]]==0;
GetdVectors[n_, A_, dset_]:=(
Table[
Table[Length[Select[A, Mod[#, p]==j&]]-Length[Select[Complement[Range[0,n-1], A], Mod[#, p]==j&]], {j,0,p-1}], {p,dset}]) ;


ILPCallLinOpt[maxpower_]:= Module[{p},
varMain = x/@ Range[0,n-1];
varDiv=Flatten[Table[kdiv[p,j], {p, pGen}, {j,0,p-1}]];
varDivNotGen=Flatten[Table[kdivnotgen[p,j], {p, pNotGen}, {j,0,p-1}]];
varBinDiv=Flatten[Table[kbin[p,j], {p, pGen}, {j,0,p-1}]];
varParity = Flatten[Table[kparity[p,j], {p, pGen}, {j,0,p-1}]];
varParityNotGen = Flatten[Table[kparitynotgen[p,j], {p, pNotGen}, {j,0,p-1}]];
varAll=Flatten[{varMain, varDiv, varBinDiv, varParity,varParityNotGen,varDivNotGen}];

conAntisym = If[asQ,And@@ Table[x[i] == 1- x[n-1-i], {i, 0, n/2}], True];
conSym = If[symQ,And@@ Table[x[i] ==  x[n-1-i], {i, 0, n/2}], True];

Do[dVal[p,j]=-countRes[p,j,n]+2Total[Select[varMain,Mod[#[[1]],p]==j&]],{p, pGen},{j,0,p-1}];
Do[dVal[p,j]=-countRes[p,j,n]+2Total[Select[varMain,Mod[#[[1]],p]==j&]],{p, pNotGen},{j,0,p-1}];

conIntegers = Thread[varAll\[Element]Integers];

conMain1 = Thread[0<=varMain<=1];
conDiv1 = Flatten[Table [- Ceiling[n/p]-1<= kdiv[p,j]<= Ceiling[n/p], {p, pGen}, {j,0,p-1}]]/. {}->True;
conDiv2 = Flatten[Table [p^qr[m,p][[1]]  kdiv[p,j]== dVal[p,j], {p, pGen}, {j,0,p-1}]]/. {}->True;

conDivNotGen = Flatten[Table [p^qr[m,p][[1]]  kdivnotgen[p,j]== dVal[p,j]-dVal[p,0], {p, pNotGen}, {j,1,p-1}]]/. {}->True;


conBin1 = Flatten[Table[-1+Floor[(((p-j) Binomial[p,j]) n)/((1+j) p)]<=kbin[p,j]<=Floor[(((p-j) Binomial[p,j]) n)/((1+j) p)],{p,pGen},{j,qr[m,p][[2]],p-1}]]/. {}->True;
conBin2=Flatten[Table[\!\(
\*UnderoverscriptBox[\(\[Sum]\), \(z = j\), \(p - 1\)]\(Binomial[z, j]\ dVal[p, z]\)\)==kbin[p,j] p^(qr[m,p][[1]]+1),{p,pGen},{j,0,qr[m,p][[2]]-1}]]/. {}->True;
  Do[conPrimeFixedDivisibility[pp]=Table[Total[Select[varMain,Mod[#1[[1]],pp]==j&]]==(A[j]/. FindSet[n,pp,dvec[pp]][[1]]),{j,0,pp-1}],{pp,fixedPrimes}];

conPrimeFixed=Flatten[conPrimeFixedDivisibility/@ fixedPrimes]/. {}->True;
mPrint[conPrimeFixed];

conParity1 = Table[-(dVal[p,j]- countRes[p,j,n])<=kparity[p,j] <= (dVal[p,j]- countRes[p,j,n]), {p, pGen},{j,0,p-1}]/. {}->True;   (* BAD b/c sign of bounds is not known *) 

conParity1 =True;

conParity2=Flatten[Table[kparity[p,j] * 2 == dVal[p,j]- countRes[p,j,n], {p, pGen},{j,0,p-1}]]/. {}->True; 

conParityNotGen=Flatten[Table[2 kparitynotgen[p,j] == dVal[p,j]- countRes[p,j,n], {p, pNotGen},{j,0,p-1}]]/. {}->True; 

conPowers=Prepend[Table[ Range[0,n-1]^exp . varMain==Sum[i^exp, {i, 0, n-1}]/2, {exp, 1, maxpower}], 2 Total[varMain]==n];

calltemp=LLinearOptimization[0,conAll=Flatten[{
conSym,conAntisym,conMain1,conIntegers; (* conDiv1, *) 
conDiv2,(* conBin1,*)  conBin2, conPrimeFixed, (* conParity1,*) 
 conParity2, conPowers, conDivNotGen, conParityNotGen}],Table[v\[Element]Integers,{v,varAll}]];



sol=LinearOptimization[0,conAll=Flatten[{
conSym,conAntisym,conMain1,conIntegers; (* conDiv1, *) 
conDiv2,(* conBin1,*)  conBin2, conPrimeFixed, (* conParity1,*) 
 conParity2, conPowers, conDivNotGen, conParityNotGen}],Table[v\[Element]Integers,{v,varAll}]];
Which[Head[sol]===List &&IntegerQ[x[1]/. sol[[2]]],First/@ First/@ Select[sol[[2]],Head[#[[1]]]===x&&  #[[2]]==1&],
(x[1]/. sol[[2]])===Indeterminate, "indeterminate", True,
 $Failed] ]



(* ::Input::Initialization:: *)
GetLegalUsingSymmetryConjectureModpOriginal[n_,m_,p_]:= Module[{s, sign=(-1)^m,r,d,j,tups},
{s,r}=QuotientRemainder[m,p-1];
If[s>0, Print["The quotient of m by p-1 is not zero"]; Return[$Failed]];If[r==0, Print["r is 0; bad case"]; Return[$Failed]];
Do[baseSetSmall[j]=Select[baseSet[n,m-1,p],EvenQ[#1-Length[Select[Range[0,n-1],Mod[#1,p]==j&]]]&],{j,0,p-1}];matching=DeleteDuplicates[Sort/@ SymmetricQRules[n,p]-1]/.  {z_Integer, zz_Integer}:>{ d[z], sign d[zz]};
matchingRule = Rule @@@ matching;
freeVbles = Last/@ matching/. -d[z_] :> d[z];
try = d/@ Range[0,p-1]/. matchingRule;
eqns=Table[\!\(
\*UnderoverscriptBox[\(\[Sum]\), \(z = j\), \(p - 1\)]\(Binomial[z, j]\ try[\([z + 1]\)]\)\), {j,1,r-1}] /. x_Integer :> Mod[x,p];
eqns1=List@@Reduce[Thread[eqns==0],freeVbles,Modulus->p^(s+1)];
cons=DeleteDuplicates[Cases[eqns1,C[_],\[Infinity]]];
eqns2= Select[eqns1, !MemberQ[cons,#[[2]] ]&];
consRule=Rule @@@Reverse/@ Select[eqns1, MemberQ[cons,#[[2]] ]&];
varToIterate=Sort[Last/@ consRule];
varToIterateInd=First/@ varToIterate;
varDependent=First/@ eqns2;
varDependentInd=First/@ varDependent;
eqns3=Sort[eqns2/.consRule];
If[Length[varToIterate]>1, 
Do[coefficients[ind]=List@@(Select[eqns3,#1[[1,1]]==ind&][[1,2]])/. d[_]->1,{ind,varDependentInd}];
Do[coefficients[ind]=If[coefficients[ind]===0,(0&)/@varToIterate,coefficients[ind]],{ind,varDependentInd}],
Do[coefficients[ind]=Flatten[{List@@(Select[eqns3,#1[[1,1]]==ind&][[1,2]]/. d[_]->1)}],{ind,varDependentInd}];
Do[coefficients[ind]=If[coefficients[ind]==={0},(0&)/@varToIterate,coefficients[ind]],{ind,varDependentInd}];
];
Do[dVals[ind]=baseSetSmall[ind], {ind, varToIterateInd}];
tups = Tuples[dVals/@ varToIterateInd];
Flatten[Table[Do[ dVals[ind]=Select[baseSetSmall[ind], Mod[coefficients[ind] . t-#, p]==0&], {ind, varDependentInd}];
Table[try/.Thread[varToIterate->t]/. Thread[d/@ varDependentInd->tt], {tt, Tuples[dVals/@ varDependentInd]}], {t, tups}],1]];

TMPolynomial[q_] := \!\(TraditionalForm\`
\*UnderoverscriptBox[\(\[Product]\), \(i = 0\), \(q - 1\)]\((1 - 
\*SuperscriptBox[\(x\), 
SuperscriptBox[\(2\), \(i\)]])\)\)
TMSeq= Position[ThueMorse[Range[0,4100]],0]//Flatten;
TMSet[powerof2_] := Select[TMSeq, #<=powerof2&]-1


(* ::Input::Initialization:: *)
S[9][368]={0,3,5,6,8,9,12,15,17,18,21,23,24,27,30,33,35,36,38,39,41,42,43,45,47,48,50,51,56,57,60,62,63,66,69,72,75,76,77,78,81,83,84,90,91,92,93,96,97,98,99,102,105,106,108,110,111,114,116,117,118,120,126,127,129,130,132,133,138,139,143,144,145,147,148,150,152,153,156,161,162,163,165,168,170,171,173,174,177,178,179,180,181,183,185,191,192,195,198,200,201,203,207,208,209,210,212,213,216,218,221,225,226,227,230,231,232,233,236,239,242,243,244,245,246,248,252,254,255,258,260,263,264,266,267,272,273,278,279,280,281,282,285,287,288,293,294,296,297,299,300,302,303,306,308,309,312,313,314,315,318,321,323,327,330,333,335,336,338,339,341,342,345,347,348,351,353,354,356,357,360,363,365,366};
S[9][416]={1,2,4,7,10,11,13,16,17,19,20,22,23,25,26,31,32,34,37,38,40,41,44,46,47,50,52,55,56,58,61,64,65,67,70,71,73,76,77,79,81,82,86,88,91,92,94,95,97,100,101,105,106,107,109,111,112,113,115,116,119,121,122,124,127,130,131,132,136,138,140,141,142,145,148,149,151,152,156,158,161,166,167,168,169,170,175,176,178,179,184,185,186,187,189,190,191,192,197,198,199,202,205,207,209,211,212,214,215,219,220,221,222,227,232,233,234,235,238,241,242,243,244,250,251,252,253,255,256,258,260,261,262,265,268,269,271,272,276,278,280,281,282,286,287,289,290,292,295,297,298,301,305,307,311,312,313,316,317,319,322,325,326,328,330,331,332,335,337,340,341,343,346,347,349,352,353,355,356,358,361,362,364,366,367,370,372,373,376,379,380,382,385,386,387,388,391,394,397,400,401,403,406,407,409,410,412,415};

S[9][432]={1,2,6,7,8,11,13,14,16,17,21,22,24,26,28,31,33,34,36,38,41,42,44,47,48,49,51,55,57,59,61,63,66,68,69,70,73,76,77,78,81,82,85,88,89,90,93,94,97,99,101,102,104,106,108,110,112,113,117,118,119,124,125,127,130,131,132,134,135,140,142,143,144,145,146,147,150,153,155,156,157,164,166,168,169,171,174,175,176,181,183,186,188,190,191,192,193,194,197,198,199,200,201,203,206,211,213,215,217,219,221,222,223,224,226,227,229,235,236,242,244,246,247,249,251,252,253,254,258,259,261,264,266,268,269,270,271,272,273,277,279,280,282,283,290,292,293,294,295,298,302,303,305,308,309,310,311,315,316,317,320,322,324,326,328,331,333,335,336,339,340,344,345,347,348,351,352,356,357,359,360,364,366,367,369,371,373,375,377,378,379,381,385,386,388,391,392,394,396,399,401,402,404,406,408,411,412,413,416,419,421,422,426,427,428,431};

S[9][464]={0,3,6,7,8,9,12,15,17,18,21,23,24,27,29,30,32,33,36,38,39,42,45,47,48,53,54,56,57,59,60,62,63,67,68,69,72,75,77,78,81,83,84,87,89,90,93,96,97,98,101,102,104,107,108,111,113,114,115,117,119,120,122,126,133,134,135,137,138,139,141,143,145,147,148,150,151,152,153,154,158,164,167,168,169,172,173,174,177,179,180,181,182,186,188,192,193,194,195,198,200,201,206,207,209,211,212,214,216,219,222,224,226,227,228,230,232,234,238,240,242,243,245,246,248,250,253,255,258,259,260,261,264,266,267,272,273,274,276,278,279,280,285,287,288,292,293,297,298,300,301,302,303,304,306,307,308,314,317,319,321,323,327,331,332,333,334,335,336,338,339,340,342,345,347,351,353,354,357,358,360,363,364,368,369,371,372,375,377,378,381,383,384,387,389,390,392,393,397,398,399,402,405,408,411,412,413,414,417,419,420,422,423,426,428,429,432,435,437,438,441,443,444,447,449,450,452,453,458,459,461,462};

S[9][496]={0,1,4,7,9,10,12,15,16,19,22,24,25,27,28,31,34,36,37,39,40,42,43,46,49,52,54,55,57,58,59,61,63,64,67,69,70,73,76,79,81,82,84,85,87,91,92,94,97,99,102,103,108,109,111,112,114,115,117,119,120,123,124,127,129,132,133,134,136,138,141,142,144,147,148,151,152,154,156,159,160,162,164,165,168,169,170,177,178,179,182,184,186,187,188,189,191,192,193,197,199,201,202,203,205,214,215,216,218,219,222,223,226,227,228,231,232,234,237,240,241,244,245,246,248,252,253,256,257,259,260,262,265,266,270,271,274,275,278,282,283,284,285,286,287,288,289,291,295,297,299,300,301,305,310,312,314,315,319,320,321,322,323,324,328,329,332,334,337,338,340,342,345,346,349,350,352,355,356,358,360,364,365,367,369,370,373,374,377,379,382,385,388,389,390,391,394,395,397,399,400,402,405,406,407,409,412,415,417,418,420,421,423,424,427,429,430,433,435,439,442,444,445,447,448,450,451,454,457,460,462,463,465,466,469,472,474,475,477,478,481,482,484,487,489,490,492,493}; (* by Stan and ChatGPT I think *) 

S[9][400]={2,3,5,8,9,11,12,14,15,17,18,20,23,26,29,30,32,35,36,38,41,42,44,47,50,53,54,56,59,60,62,65,66,68,69,71,74,75,77,78,79,80,83,84,86,88,92,93,95,99,100,101,105,107,109,110,111,113,117,119,120,123,124,125,129,131,132,134,135,137,141,143,144,145,146,149,151,155,164,165,167,168,170,171,172,174,176,177,178,179,181,182,183,184,185,186,188,190,192,194,196,198,200,202,204,206,208,210,212,219,224,226,230,233,236,237,238,239,240,241,242,243,245,246,247,249,251,252,257,259,260,261,263,266,269,271,272,273,277,278,281,283,284,285,287,291,293,295,296,297,301,302,303,305,308,309,310,312,314,317,318,323,326,327,329,332,335,336,338,341,342,344,347,348,350,351,353,354,356,359,360,362,365,366,368,371,372,374,375,377,378,380,383,386,389,392,393,395,398,399};

S[9][352]={0,2,5,8,9,11,12,14,15,17,20,23,26,29,30,32,33,35,36,38,39,41,44,45,47,50,51,53,54,57,59,60,65,68,70,71,74,77,78,80,83,86,87,89,90,92,93,95,98,100,101,104,105,106,107,108,110,113,115,117,120,122,123,125,126,128,129,130,131,137,140,142,143,146,148,149,155,158,159,160,161,163,165,168,170,174,176,178,179,180,182,184,185,187,189,194,195,197,198,199,200,201,204,206,207,210,212,213,215,216,217,218,219,224,227,230,232,233,235,237,239,240,242,248,249,252,254,255,257,260,263,266,267,269,270,272,275,276,278,279,282,284,285,287,288,289,290,293,295,296,299,302,303,305,308,309,311,314,317,320,323,324,326,327,329,330,332,333,335,338,341,344,345,347,348,350};

S[9][320]={0,2,3,6,9,12,14,15,17,18,21,23,24,27,29,30,33,35,36,39,41,42,44,45,48,50,51,54,56,57,62,63,66,68,69,71,72,74,75,78,80,81,83,84,87,90,93,96,97,98,101,105,106,108,111,113,114,117,119,120,122,123,125,126,127,128,129,133,134,135,140,141,144,147,150,151,152,156,157,158,160,164,165,166,170,171,173,174,176,177,180,181,182,183,187,188,189,195,198,201,203,204,207,209,210,212,215,216,217,219,220,224,225,227,228,230,231,233,234,237,240,242,243,246,249,252,254,255,258,259,260,261,264,266,267,270,272,273,276,279,281,282,285,287,288,291,293,294,297,299,300,303,306,308,309,311,312,314,315,318};

S[10][336]={0,1,4,9,10,11,13,14,16,19,21,23,24,26,27,29,34,35,36,37,38,44,45,46,48,49,51,54,57,59,60,64,66,68,70,71,74,76,79,80,81,85,86,87,89,90,91,92,95,98,99,100,101,103,104,109,111,114,119,120,121,123,124,126,127,130,134,137,138,139,140,141,148,150,151,153,154,155,157,161,162,164,165,167,168,170,171,173,174,178,180,181,182,184,185,187,194,195,196,197,198,201,205,208,209,211,212,214,215,216,221,224,226,231,232,234,235,236,237,240,243,244,245,246,248,249,250,254,255,256,259,261,264,265,267,269,271,275,276,278,281,284,286,287,289,290,291,297,298,299,300,301,306,308,309,311,312,314,316,319,321,322,324,325,326,331,334,335};

S[10][240]={0,1,6,7,8,11,13,16,17,18,21,22,25,27,28,30,32,34,35,36,39,40,44,47,49,53,55,57,58,59,60,62,64,69,70,72,74,75,77,78,79,80,81,83,88,89,91,92,95,98,103,105,106,110,111,113,114,116,117,118,121,122,123,125,126,128,129,133,134,136,141,144,147,148,150,151,156,158,159,160,161,162,164,165,167,169,170,175,177,179,180,181,182,184,186,190,192,195,199,200,203,204,205,207,209,211,212,214,217,218,221,222,223,226,228,231,232,233,238,239};

S[10][432]={0,2,5,6,9,11,12,15,16,19,20,22,25,26,30,31,32,34,35,40,41,44,45,46,49,51,54,55,56,59,60,61,65,66,69,70,72,74,76,77,79,81,84,86,88,90,91,94,96,99,100,102,104,105,109,110,113,115,117,120,122,123,125,128,131,132,136,137,139,140,141,142,145,150,151,152,153,154,155,156,159,161,164,165,169,170,171,172,174,176,178,180,183,184,186,187,194,196,197,198,202,205,206,207,208,212,214,215,216,217,219,223,224,225,226,229,233,234,235,237,244,245,247,248,251,253,255,257,259,260,261,262,266,267,270,272,275,276,277,278,279,280,281,286,289,290,291,292,294,295,299,300,303,306,308,309,311,314,316,318,321,322,326,327,329,331,332,335,337,340,341,343,345,347,350,352,354,355,357,359,361,362,365,366,370,371,372,375,376,377,380,382,385,386,387,390,391,396,397,399,400,401,405,406,409,411,412,415,416,419,420,422,425,426,429,431};

S[10][528]={0,2,4,7,9,12,13,14,17,18,19,23,24,27,28,30,32,33,37,39,42,43,44,47,49,52,53,54,58,59,60,63,65,67,68,69,73,74,77,78,79,82,83,87,88,89,93,94,95,97,100,103,105,107,108,112,113,115,117,118,121,122,124,127,128,131,133,134,136,138,140,142,144,147,149,150,152,155,160,161,162,163,164,165,168,170,173,174,179,181,182,184,185,187,188,190,191,195,197,198,199,203,205,207,208,209,213,214,216,217,219,221,224,226,227,228,230,236,238,239,241,242,243,246,248,249,250,256,257,258,260,261,266,267,269,270,271,277,278,279,281,284,285,286,288,289,291,297,299,300,301,303,306,308,310,311,313,314,318,319,320,322,324,328,329,330,332,336,337,339,340,342,343,345,346,348,353,354,357,359,362,363,364,365,366,367,372,375,377,378,380,383,385,387,389,391,393,394,396,399,400,403,405,406,409,410,412,414,415,419,420,422,424,427,430,432,433,434,438,439,440,444,445,448,449,450,453,454,458,459,460,462,464,467,468,469,473,474,475,478,480,483,484,485,488,490,494,495,497,499,500,503,504,508,509,510,513,514,515,518,520,523,525,527};

SClaude[11][432]={0,1,3,6,8,9,11,13,16,18,21,22,23,24,28,32,33,34,36,37,38,41,43,44,48,50,51,52,53,58,59,61,63,64,66,68,71,76,77,78,83,85,86,87,88,91,92,93,94,98,99,100,101,103,104,109,113,114,116,118,120,121,123,127,128,129,132,133,134,138,140,142,143,144,146,151,153,156,157,159,161,162,163,164,165,166,169,171,176,181,182,183,184,185,186,187,189,191,194,197,202,203,204,206,209,211,212,213,216,218,219,223,225,226,228,232,233,234,235,237,238,240,241,243,245,253,254,255,256,258,259,260,261,263,265,266,273,275,278,279,281,283,284,285,286,288,292,294,296,297,298,302,303,307,308,309,311,314,316,318,321,322,323,325,326,327,328,331,336,337,338,343,344,349,351,352,353,354,358,359,360,361,363,364,366,368,371,373,376,377,378,379,384,386,387,388,391,393,394,398,402,403,404,406,407,408,413,414,416,418,419,421,423,426,428,429,431};  

SClaude[12][480]={0,2,3,8,9,12,14,15,16,17,20,23,25,28,29,30,31,35,36,37,38,42,44,45,49,50,52,56,57,59,63,64,65,66,70,71,72,74,77,78,82,83,85,86,87,91,92,93,98,99,101,103,105,106,107,108,109,113,116,118,119,123,126,127,129,133,134,135,136,139,141,143,146,148,150,151,152,154,155,156,159,161,162,164,170,174,175,177,178,180,181,184,185,186,187,189,190,192,193,196,202,204,205,208,209,211,212,215,216,217,220,221,222,231,232,233,234,235,238,239,240,241,244,245,246,247,248,257,258,259,262,263,264,267,268,270,271,274,275,277,283,286,287,289,290,292,293,294,295,298,299,301,302,304,305,309,315,317,318,320,323,324,325,327,328,329,331,333,336,338,340,343,344,345,346,350,352,353,356,360,361,363,366,370,371,372,373,374,376,378,380,381,386,387,388,392,393,394,396,397,401,402,405,407,408,409,413,414,415,416,420,422,423,427,429,430,434,435,437,441,442,443,444,448,449,450,451,454,456,459,462,463,464,465,467,470,471,476,477,479};


lp[h_,m_]:=With[{l=2 IntegerDigits[FromDigits[h,16],2,4 StringLength[h]]-1},Join[l,(-1)^m Reverse[l]]];
X=Flatten[Position[lp["B0CBC94F1E2C68D1E3A6371C357C4B1347952BB968236CF6C82CD9CE01F3",12],1]];
Table[Total[X^k]-Sum[i^k,{i,480}]/2,{k,0,12}]   (*expect twelve 0s,then nonzero*)



(* ::Input::Initialization:: *)
double[S_,n_] := Join[S,Complement[Range[0,n-1],S]+n];
polynomialLength[lp_]:= Length[CoefficientList[lp,x]];
polynomialDegree[lp_]:=polynomialLength[lp]-1;
polynomialJoin[f_, g_]:= f+ x^polynomialLength[f] g//Expand;
polynomialSharp[f_, g_]:= f (g /. x-> x^polynomialLength[f])//Expand;
polynomialReverse[lp_] := x^polynomialDegree[lp]  (lp /. x-> 1/x) //Expand;
symmetrize[lp_] := polynomialJoin[lp, polynomialReverse[lp]];
antisymmetrize[lp_] := polynomialJoin[lp, -polynomialReverse[lp]];


(* ::Input::Initialization:: *)
mValQ[0][x_]:=IntegerExponent[x,2]==0;
mValQ[1][x_]:=IntegerExponent[x,2]==1;
mValQ[2][x_]:=x==4;
mValQ[3][x_]:=x==8||(IntegerExponent[x,2]==2&&x>=12)
mValQ[4][x_]:=x==16||MemberQ[{24},x]
mValQ[5][x_]:=x==32||MemberQ[{40,56},x]
mValQ[6][x_]:=x==64||MemberQ[{48,72,80,88,104,120},x]||(IntegerExponent[x,2]==3&&x<=192)
(* the previous disappear from 5 to 6 *) 
mValQ[7][x_]:=x==128||MemberQ[{96,160,112,176},x]||(IntegerExponent[x,2]==3)
mValQ[8][x_]:=x==256||MemberQ[{144},x]
Clear[mStar];
mStar[144]=8;
mStar[192]=9;
mStar[208]=8;
mStar[224]=8;
mStar[256]=8;
mStar[272]=8;
mStarSet[240]={9,10,11};

mStar[n_]:=Which[mValQ[0][n],0,
mValQ[1][n],1,
mValQ[2][n],2,
mValQ[3][n],3,
mValQ[4][n],4,
mValQ[5][n],5,
mValQ[6][n],6,
mValQ[7][n],7,
True,XX];
