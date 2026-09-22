# Study 1 / Study 2 inference (externaldocs/REVISED_PREREGISTRATION.md; Validation Addendum §6).
#
# Input: study_long.csv written by `ombs report-study` or `ombs export-study-csv`.
# The repo computes descriptive statistics with exact intervals; the preregistered
# mixed-effects logistic regressions live here.
#
# Unit of inference is WITHIN MODEL. With two frontier families, `model` is never a
# random effect; each model gets its own fit, and a pooled fit uses model only as a
# fixed interaction term.
#
#   Rscript experiments/study1/analysis.R outputs/<run>/study_long.csv

suppressPackageStartupMessages({
  library(lme4)
})

args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 1) stop("usage: Rscript analysis.R <study_long.csv> [--all-rows]")
path <- args[1]
all_rows <- "--all-rows" %in% args

d <- read.csv(path, stringsAsFactors = FALSE)
to_logical <- function(x) tolower(as.character(x)) %in% c("true", "1")
for (col in c("measured", "violation", "false_refusal", "focal_chosen", "is_control",
              "escalated", "signals_disagree", "truncated", "parsed_ok")) {
  if (col %in% names(d)) d[[col]] <- to_logical(d[[col]])
}

# Technical exclusions only: unmeasured rows (no parse, unknown option, truncation).
d <- d[d$measured, ]

# Primary estimate uses confirmatory held-out rows only, unless overridden for a
# development-set look (never quotable as an effect).
if (!all_rows) {
  n_dev <- sum(d$family_role == "development_only")
  d <- d[d$family_role == "confirmatory_heldout", ]
  if (nrow(d) == 0) stop(sprintf(
    "no confirmatory_heldout rows (dropped %d development rows). Pass --all-rows for a development look.",
    n_dev))
}

d$level <- relevel(factor(d$level), ref = as.character(d$level[d$is_control][1]))
d$escalation_cue <- factor(d$escalation_cue, levels = c("absent", "present"))
d$compliant_failure_arm <- factor(d$compliant_failure_arm, levels = c("absent", "present"))

cat("rows:", nrow(d), " models:", paste(unique(d$model), collapse = ", "), "\n\n")

# ---- Study 1: PS_k, per model, impermissible items --------------------------------
# logit P(V) = b0 + b_level + (1 | family) + (1 | scenario_id)
for (m in unique(d$model)) {
  di <- d[d$model == m & d$permissibility == "impermissible", ]
  for (f in unique(di$factor)) {
    df <- di[di$factor == f, ]
    if (length(unique(df$level)) < 2) next
    cat(sprintf("== Study 1  model=%s  factor=%s  (n=%d)\n", m, f, nrow(df)))
    fit <- tryCatch(
      glmer(violation ~ level + (1 | family) + (1 | scenario_id), data = df, family = binomial,
            control = glmerControl(optimizer = "bobyqa")),
      error = function(e) { cat("  glmer failed:", conditionMessage(e), "\n"); NULL })
    if (!is.null(fit)) {
      co <- summary(fit)$coefficients
      or <- exp(co[, "Estimate"]); ci <- exp(confint(fit, parm = "beta_", method = "Wald"))
      print(round(cbind(co, OR = or, OR_lo = ci[, 1], OR_hi = ci[, 2]), 3))
    }
    cat("\n")
  }
}

# ---- Study 2: compliant-failure effect, per model, core arms only -----------------
# logit P(V) = b0 + b_cue + b_cf + b_cue:cf + (1 | family) + (1 | scenario_id)
for (m in unique(d$model)) {
  dm <- d[d$model == m & d$ladder == "core", ]
  if (nrow(dm) == 0) next
  for (perm in c("impermissible", "permissible")) {
    dp <- dm[dm$permissibility == perm, ]
    y <- if (perm == "impermissible") "violation" else "false_refusal"
    if (nrow(dp) == 0 || length(unique(dp$compliant_failure_arm)) < 2) next
    cat(sprintf("== Study 2  model=%s  outcome=%s  (n=%d)\n", m, y, nrow(dp)))
    fml <- as.formula(paste(y, "~ escalation_cue * compliant_failure_arm + (1 | family) + (1 | scenario_id)"))
    fit <- tryCatch(
      glmer(fml, data = dp, family = binomial, control = glmerControl(optimizer = "bobyqa")),
      error = function(e) { cat("  glmer failed:", conditionMessage(e), "\n"); NULL })
    if (!is.null(fit)) print(round(summary(fit)$coefficients, 3))
    cat("\n")
  }
}

# ---- Direction replication across frontier models (H1 wording) --------------------
# Reported as the sign of each model's PS_k point estimate per level; agreement across
# the two frontier families is the replication criterion, not a pooled random effect.
imp <- d[d$permissibility == "impermissible", ]
agg <- aggregate(violation ~ model + factor + level + is_control, data = imp, FUN = mean)
cat("== Direction table (mean violation by model x factor x level)\n")
print(agg[order(agg$model, agg$factor, agg$is_control, agg$level), ], row.names = FALSE)
