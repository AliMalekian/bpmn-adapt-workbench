"""Deterministic paired statistical analysis with multiplicity correction."""
from __future__ import annotations

from dataclasses import dataclass
import math
import random
from statistics import mean,stdev


@dataclass(frozen=True)
class StatisticalResult:
    test:str; statistic:float; p_value:float; effect_size:float
    confidence_interval:tuple[float,float]|None; n:int; assumptions:dict


class StatisticalAnalyzer:
    def __init__(self,seed=20260922,bootstrap_samples=2000,permutation_samples=10000):
        self.seed,self.bootstrap_samples,self.permutation_samples=seed,bootstrap_samples,permutation_samples

    def compare_binary(self,left,right):
        from scipy.stats import binomtest
        b=sum(a==1 and c==0 for a,c in zip(left,right)); c=sum(a==0 and c==1 for a,c in zip(left,right)); n=b+c
        p=binomtest(min(b,c),n,.5).pvalue if n else 1.0
        effect=(b-c)/n if n else 0.0
        return StatisticalResult("mcnemar_exact",float(abs(b-c)),float(p),effect,None,len(left),{})

    def compare_continuous(self,left,right):
        from scipy import stats
        differences=[float(b)-float(a) for a,b in zip(left,right)]; n=len(differences)
        if n<2: return StatisticalResult("permutation",0,1,0,None,n,{"reason":"insufficient pairs"})
        normal_p=float(stats.shapiro(differences).pvalue) if 3<=n<=5000 and len(set(differences))>1 else 0.0
        if normal_p>.05:
            result=stats.ttest_rel(right,left); test="paired_t"; statistic=float(result.statistic); p=float(result.pvalue)
        elif any(differences):
            try: result=stats.wilcoxon(differences); test="wilcoxon"; statistic=float(result.statistic); p=float(result.pvalue)
            except ValueError: statistic,p=self._permutation(differences); test="permutation"
        else: statistic,p,test=0.0,1.0,"permutation"
        effect=mean(differences)/(stdev(differences) or 1) if n>1 else 0.0
        return StatisticalResult(test,statistic,p,effect,self._bootstrap(differences),n,{"shapiro_p":normal_p})

    def _permutation(self,differences):
        rng=random.Random(self.seed); observed=abs(mean(differences)); extreme=0
        for _ in range(self.permutation_samples):
            value=abs(mean([item*(1 if rng.random()<.5 else -1) for item in differences]))
            extreme+=value>=observed
        return observed,(extreme+1)/(self.permutation_samples+1)

    def _bootstrap(self,differences):
        rng=random.Random(self.seed); n=len(differences)
        estimates=sorted(mean([differences[rng.randrange(n)] for _ in range(n)])
                         for _ in range(self.bootstrap_samples))
        return estimates[int(.025*(len(estimates)-1))],estimates[int(.975*(len(estimates)-1))]

    @staticmethod
    def holm(p_values,family_alpha=.05):
        ordered=sorted(p_values.items(),key=lambda item:item[1]); m=len(ordered); result={}; running=0.0
        for index,(name,p_value) in enumerate(ordered):
            adjusted=max(running,min(1.0,(m-index)*p_value)); running=adjusted
            result[name]={"raw_p":p_value,"adjusted_p":adjusted,"reject":adjusted<=family_alpha}
        return result
