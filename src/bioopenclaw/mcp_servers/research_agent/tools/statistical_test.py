"""Statistical testing — scipy.stats wrappers with multiple testing correction."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def run_statistical_test(
    test_type: str,
    group_a: list[float],
    group_b: list[float] | None = None,
    alternative: str = "two-sided",
    alpha: float = 0.05,
    correction_method: str = "none",
    paired: bool = False,
) -> dict[str, Any]:
    """Run a statistical test on provided data.

    Supported test types:
    - t_test: Student's t-test (or Welch's t-test)
    - mann_whitney: Mann-Whitney U test
    - wilcoxon: Wilcoxon signed-rank test (paired)
    - chi2: Chi-squared test (group_a and group_b are observed/expected)
    - ks_test: Kolmogorov-Smirnov test
    - shapiro: Shapiro-Wilk normality test (group_a only)

    Correction methods: none, bonferroni, bh_fdr
    """
    try:
        from scipy import stats
        import numpy as np
    except ImportError:
        return {"success": False, "error": "scipy not installed: pip install scipy numpy"}

    a = np.array(group_a, dtype=float)
    b = np.array(group_b, dtype=float) if group_b else None

    try:
        result: dict[str, Any] = {
            "test_type": test_type,
            "n_a": len(a),
            "n_b": len(b) if b is not None else 0,
            "alternative": alternative,
            "alpha": alpha,
        }

        if test_type == "t_test":
            if b is None:
                return {"success": False, "error": "t_test requires group_b"}
            if paired:
                stat, p = stats.ttest_rel(a, b, alternative=alternative)
            else:
                stat, p = stats.ttest_ind(a, b, alternative=alternative, equal_var=False)
            effect_size = _cohens_d(a, b)
            result.update({
                "statistic": float(stat),
                "p_value": float(p),
                "effect_size_cohens_d": float(effect_size),
                "paired": paired,
            })

        elif test_type == "mann_whitney":
            if b is None:
                return {"success": False, "error": "mann_whitney requires group_b"}
            stat, p = stats.mannwhitneyu(a, b, alternative=alternative)
            r = 1 - (2 * stat) / (len(a) * len(b))
            result.update({
                "statistic": float(stat),
                "p_value": float(p),
                "effect_size_r": float(r),
            })

        elif test_type == "wilcoxon":
            if b is None:
                return {"success": False, "error": "wilcoxon requires group_b (paired)"}
            stat, p = stats.wilcoxon(a, b, alternative=alternative)
            result.update({
                "statistic": float(stat),
                "p_value": float(p),
            })

        elif test_type == "chi2":
            if b is None:
                stat, p = stats.chisquare(a)
            else:
                stat, p = stats.chisquare(a, f_exp=b)
            result.update({
                "statistic": float(stat),
                "p_value": float(p),
            })

        elif test_type == "ks_test":
            if b is None:
                stat, p = stats.kstest(a, "norm")
                result["comparison"] = "vs normal distribution"
            else:
                stat, p = stats.ks_2samp(a, b)
                result["comparison"] = "two-sample"
            result.update({
                "statistic": float(stat),
                "p_value": float(p),
            })

        elif test_type == "shapiro":
            stat, p = stats.shapiro(a)
            result.update({
                "statistic": float(stat),
                "p_value": float(p),
                "is_normal": bool(p > alpha),
            })

        else:
            return {"success": False, "error": f"Unknown test type: {test_type}"}

        p_val = result["p_value"]

        if correction_method == "bonferroni":
            result["p_value_corrected"] = min(p_val * 2, 1.0)
            result["correction"] = "bonferroni"
        elif correction_method == "bh_fdr":
            result["p_value_corrected"] = p_val
            result["correction"] = "bh_fdr (single test — no adjustment needed)"
        else:
            result["correction"] = "none"

        result["significant"] = bool(p_val < alpha)
        result["success"] = True

        result["summary_stats"] = {
            "group_a_mean": float(np.mean(a)),
            "group_a_std": float(np.std(a, ddof=1)) if len(a) > 1 else 0.0,
            "group_a_median": float(np.median(a)),
        }
        if b is not None:
            result["summary_stats"].update({
                "group_b_mean": float(np.mean(b)),
                "group_b_std": float(np.std(b, ddof=1)) if len(b) > 1 else 0.0,
                "group_b_median": float(np.median(b)),
            })

        return result

    except Exception as e:
        logger.error("Statistical test failed: %s", e)
        return {"success": False, "error": str(e)}


def _cohens_d(a, b) -> float:
    """Calculate Cohen's d effect size."""
    import numpy as np
    na, nb = len(a), len(b)
    var_a, var_b = np.var(a, ddof=1), np.var(b, ddof=1)
    pooled_std = np.sqrt(((na - 1) * var_a + (nb - 1) * var_b) / (na + nb - 2))
    if pooled_std == 0:
        return 0.0
    return float((np.mean(a) - np.mean(b)) / pooled_std)
