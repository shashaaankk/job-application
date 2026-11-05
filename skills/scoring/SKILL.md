---
name: scoring
description: Score job cards for the user the way a recruiter and a hiring manager would, rank them into tiers A, B and C, and write the CV-tailoring brief for each. Use this skill whenever the user asks to score, rescore, rank or evaluate job cards or postings, asks why a card got its tier or band, disputes a score, asks which jobs to apply to first, or wants to change how scoring works, even if they only say "run scoring", "check this job", "is this a good fit" or "why is this a B".
---

# Scoring

The scorer decides which postings the user applies to and what the tailored CV
stresses, so a wrong score costs the user either a good job or an afternoon. It works
for the user, the way a sports agent works for an athlete. It argues for the user on
fit, because a missed good-chance role costs more than one extra application. It is
strict on what the user wants, because a job the user does not want is a bad deal for
the user. It never invents experience, because a CV claim the user cannot defend in
an interview loses the job.

Call the user "the user" in everything this skill writes. The pipeline is shipped to
other people, and a pronoun or a name ties it to one person.

## What the scorer reads

Only what the user supplies, plus the posting.

| Input | Where |
| --- | --- |
| Preferences | `04. preferences.md` |
| Profile | `05. profile.md` |
| Base CV | the first `.tex` file in `resume/` |
| Knowledge notes | `knowledge/*.md` with `cv-ready: true`, cut to 900 characters each |
| Binding rules | `06. rules.md`, which holds the out-of-scope rules such as rule 11 |
| The posting | the card's archived job description |

## Every decision carries its reason

Rule 90. The knockout, every score, every must-have's selection, every tailoring edit,
every question and the tier each carry a reason on the card, naming what in the posting
and what in the record decided it. The user decides from the card and corrects a false
premise in User Comments, which only works when the premise is written down. A missing
reason is shown as UNEXPLAINED, never hidden.

## The axes

Each card is scored on these, and the base CV and a tailored CV are scored separately.

1. Knockouts. Only the user's hard preferences, an out-of-scope rule, or a fact the posting states outright, such as no visa sponsorship. Unknown passes.
2. Quick scan, 0 to 3. Whether a recruiter puts the CV in the yes pile after about seven seconds on titles, employers, dates, education and the top third of page one.
3. Must-haves, 3 to 5, each 0 to 3. Capabilities the work cannot be done without, derived from the described work, never copied from the requirements list. Every score carries its reason, naming what matches, what the record does not show, and why the gap closes in the time given, so the user can correct it on the card.
4. Nice-to-haves, up to 4, each 0 to 3.
5. Want, role and domain, 0 to 3 each.
6. Tailoring. The same axes after honest changes to the CV parts a variant may change, plus the list of edits that gets there. Those parts are listed in `scripts/data/cv-slots.txt`, which the user fills in. Each edit names its part, and an edit outside them is dropped and raises nothing. The edits go on the card as unticked boxes. Nothing changes the CV until the user ticks them, per rule 83.

The full instructions, including how transferability is judged by activity, system
and constraints, are in `references/scorer-prompt.md`. That file is exactly what the
scoring agent receives, so read it before judging a card yourself.

## Score the cards in `matched`

```bash
.venv/bin/python scripts/score.py --dry-run
.venv/bin/python scripts/score.py
```

Run the dry run first. It lists the unscored cards and prints the prompt size, which
is about 80,000 characters per card. Then run the real thing. It starts one fresh
agent per card, five at a time, so nothing carries over between cards. It writes each
card's Evaluation, sets the English board title, and moves tier A and then tier B
cards to `to apply` within the user's caps.

Report the tier counts, the cards moved, and any failures from the run's summary.
A failed card stays unscored and is picked up by the next run.

The scoring agent is Antigravity by default, because its quota is separate and the
Claude budget is kept for the CV and the letter. To use another agent, set `SCORE_CMD`
to a command that takes the prompt on stdin and prints the JSON object, and
`SCORE_AGENT` to the name that goes on the card.

## Score one posting without the board

```bash
.venv/bin/python skills/scoring/scripts/score_posting.py posting.md
```

The posting file has `Title:`, `Company:`, `Location:` and `Posting:` lines, a line of
three dashes, then the description. Use this when the user pastes a posting and asks
whether it is worth applying to. It touches no card and no board.

## Explain or correct a card

When the user asks why a card got its tier, read the card's Evaluation and
`references/tiers.md`. The tier line names the condition that decided it. Point to the
axis and the row that drove it, quoting the card.

When the user disputes a score, the user is right about the user's own experience.
Re-score the affected must-have from what the user said, recompute the tier with the
formula in `references/tiers.md`, and update the card's Evaluation and Score field.
If the correction shows that a rule in the scorer prompt is wrong, say so and propose
the change rather than patching it silently.

## Change how scoring works

1. Edit `references/scorer-prompt.md` for what the agent does, and `grade()` in `scripts/score.py` for how numbers become a tier. An axis change needs both.
2. Run the test cases. Each one states its expected tier.
   ```bash
   .venv/bin/python skills/scoring/scripts/check_cases.py
   ```
3. A case that changes tier is a regression until the user agrees otherwise.
4. When a user's correction exposes a wrong rule, first save that posting as a new case under `evals/`, in the same layout as the existing ones, then change the rule.

`references/tiers.md` records why each rule exists. Read it before removing one,
because each rule fixes a failure that was observed.
