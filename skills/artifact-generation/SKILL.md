---
name: artifact-generation
description: Generate the CV for every card in the board's `to apply` column. A cover letter is produced only when he asks for one, by name. Use when he asks to generate artifacts, build the documents, or run the apply pack. This is the only entry point to document generation, and the board column is its only trigger.
---

# Artifact generation

A card reaches the `to apply` column one of two ways. `scripts/score.py` moves it
there when `skills/scoring` gives it tier A or B, which are bands 3 and 2, inside his
three caps. Or he moves it there himself, which he may do with any card at any time.

Either way the column is the decision and it was made before this skill runs. This
skill acts on that column and on nothing else, and it never moves a card.

## Step 1. Read the work list

```bash
cd ~/job-application && .venv/bin/python scripts/pending.py
```

The script is the authority on what is work. It reports a card as `WORK` when the
card sits in `to apply` and its `cv` or `coverletter` key is still empty, as `done`
when both keys are filled, and as `BLOCKED` when the archived description is shorter
than 200 characters.

A card reported as `APPROVE` is waiting for him to tick its tailoring edits, per rule 83. It is not work, and the report lists it so he knows it is waiting.

Never read the board yourself and never generate for a card the script did not list.
A card he has not moved is not work, however good it looks.

## Step 2. Stop on anything blocked

A `BLOCKED` card has no readable description, so rule 1 forbids acting on it. Report
it to him by name and generate nothing for it. Do not fetch the description to repair
it, because the sweep's own path is where that belongs.

A `missing` card means a board link points at no file. Report it and stop for that
card alone.

## Step 3. Dispatch one agent per card

Cards are independent, so they run in parallel. The stages inside one card are not,
so they run in series.

For each `WORK` card, one agent does two stages in this order.

1. `skills/resume-generation`, which produces the `.tex`, compiles it, runs
   `scripts/market_gate.py` and sets the card's `cv` key.
2. `skills/adversarial-verification-artifacts`, on the CV.

A critic FAIL is fixed inside that same agent and the document is recompiled and
re-reviewed. Nothing reaches him before it passes, and a document is never handed
over with an open flag attached as a note.

## No cover letters unless he asks

He ruled that every card in `to apply` carries a CV and that the letters produced so
far are not usable. So a letter is written only when he names a card and asks for
one, through `skills/coverletter-generation`.

A card with no letter is finished, not pending. `pending.py` tests the `cv` key
alone, and `scripts/market_gate.py` no longer fails a card for a missing letter,
though it still checks a letter that exists for the right market.

`pending.py --letters` lists the cards that have no letter yet, for when he asks.

A card that cannot be finished reports what blocked it. It does not stop the other
cards, and a half-finished card keeps whichever key did pass.

## Step 4. Report

One line per card, naming the company, the role, the page count, the market gate
verdict and the critic verdict. Then the cards that failed and why.

Do not move any card. The `applied` column is his, because the pipeline never submits
an application and the column records a thing he did rather than a thing a run did.

## Caps

His three caps are 20 cards at band 3, 30 at band 2 and 35 in total per run, held in
rule 62. They are already applied by `scripts/score.py`, which is what decides how
many cards reach `to apply` in the first place.

So this skill generates for every card the column holds and adds no cap of its own.
Rule 62 forbids inventing one.

## Never

Generate for a card outside the `to apply` column.

Generate again for a card whose `cv` key is already filled. The nearest passed
variant is diffed instead.

Write a cover letter in a scheduled or batch run. Letters are on request only.

Write a score, a band or a tier onto a card. Scoring belongs to `skills/scoring`,
and his correction of a card goes through that skill.

Submit, send or post anything. The pipeline produces documents and he applies.
