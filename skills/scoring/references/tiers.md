# Tiers, the card, and why each rule exists

Read this when explaining a card's tier to the user, when the user disputes a score,
or before changing the tier logic in `scripts/score.py` (`grade()`).

## Contents

1. The formula
2. What the card shows
3. Why each rule exists
4. Changing the method

## 1. The formula

The agent returns numbers. `grade()` computes the tier, so two agents that return the
same numbers produce the same ranking.

```
can  = 0.75 × mean(must-have scores) + 0.25 × mean(nice-to-have scores)
want = (want_role + want_domain) / 2
```

Can is computed twice, from the base scores and from the tailored scores. A tailored
score below its base score is raised to the base score.

Tailoring counts only through edits whose slot is listed in
`scripts/data/cv-slots.txt`. Edits in any other slot are shown on the card as
dropped. When no edit is left, every tailored score falls back to its base score.
When some edits are left, the tailored scores are the agent's, so they can still be
generous. The test cases are the check on that.

| Tier | Condition, checked in this order | Band |
| --- | --- | --- |
| none | `preference_verdict` is reject | 0 |
| C | a must-have is still 0 after tailoring | 1 |
| C | want below 1.5 | 1 |
| C | tailored can below 1.5 | 1 |
| A | want at least 2.5, tailored can at least 2.25, tailored quick scan at least 2 | 3 |
| B | everything else | 2 |

The band is what `move_card.py`, its caps and `prune_matched.py` read. Tier A and B
cards move to `to apply` after the whole run is scored, A first, so A claims the caps.
The caps are 20 at band 3, 30 at band 2 and 35 in total.

Must-haves carry three quarters of can because they decide whether the user can
start the job. Nice-to-haves only separate candidates who can.

## 2. What the card shows

In order.

1. The English title, the tier and the one-line reason from `grade()`.
2. The knockout result.
3. A table of every axis for the base CV and the tailored CV.
4. The quick-scan reason, then the want reasons.
5. A table of must-haves and nice-to-haves. Each row has the posting's words, the user's evidence, the score, shown as `base → tailored` when they differ, the gap, meaning what the record does not show, the time to close it, and why. The why column is what the user corrects in User Comments.
6. The tailoring edits, as unticked boxes under "Tailoring edits for the user to approve", with "Use the base CV as it is" last. The CV generator applies only ticked boxes, and `pending.py` holds the card until one is ticked. Edits outside the CV slots follow under Dropped.
7. The questions, as unchecked boxes, each naming the decision it changes.

The Score field reads `band N, preference pass, tier X`.

## 3. Why each rule exists

Every rule below was added after a test on 5 November 2026 failed without it.

| Rule | Failure it fixes |
| --- | --- |
| Understand the work and write nothing about it | Asked to describe the role, the agent restated the posting at length. |
| Read between the lines | Told to answer "not stated" when unsure, the agent said a demonstrator role's main work was not stated. |
| Field knowledge is a valid basis | The agent would not say a robotics role almost certainly uses C++, Python and ROS. |
| One standard for every skill | The same agent counted listed GitHub Actions as held and listed CMake as unproven. |
| Sports-agent persona | Asked a neutral question, the agent judged a missing tool against the user although it closes in a weekend. |
| Be strict on want | With the persona alone, the agent matched an unnamed domain to the user's domains to help the user. |
| Boilerplate does not name the domain | A build-infrastructure role passed as automotive and robotics because the company's About text lists them. |
| Must-haves from the work | Must-haves copied from the requirements list made a years figure a bar. |
| Activity, system, constraints | Nothing told the agent what "transferable" means, so it decided case by case. |
| Questions must name the decision they change | Cards filled up with questions whose answers changed nothing. |
| Edits name their CV slot, enforced by the script | Told in prose to respect rule 24, the agent still proposed reordering the skills line, which raised tailored scores the CV generator could never deliver. |

The old band measured only how well the record covered the work. All 329 cards it
scored were band 2 or 3, and it gave the TU/e robotics role and the Capgemini build
role the same band 3. The tiers separate them as A and B.

## 4. Changing the method

1. The instructions the agent sees are `references/scorer-prompt.md`. The tier logic is `grade()` in `scripts/score.py`. Change both together when an axis changes.
2. Run `skills/scoring/scripts/check_cases.py` after any change. Each case in `evals/` states its expected tier, and a case that moves is a regression until the user says otherwise.
3. When the user corrects a card and the correction shows a rule is wrong, add that posting as a case before changing the rule, so the fix stays fixed.
4. Outcome calibration is not done yet. The replies so far are generic, so the weights are set by judgement, not fitted to outcomes.
