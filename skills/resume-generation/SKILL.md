---
name: resume-generation
description: Generate a tailored LaTeX CV for one job card he has moved into the board's `to apply` column. Use when the artifact generation skill dispatches it, or when he names a card and asks for a CV. Never used to invent content, only to select and order evidenced work.
---

# Resume generation

One card, one CV. The document rules are not restated here, they live in [06. rules](../../06.%20rules.md) and that file wins on any disagreement. This skill is the procedure.

The base template is frozen. Almost nothing about a variant is a writing task, which is the point. Every past failure in this area came from a run deciding it could improve a bullet.

## Preconditions

Two, and a miss on either one stops the run.

1. The card sits in the board's `to apply` column, which is his judgement that this posting is worth applying to. `scripts/pending.py` is the authority on that, and nothing else releases a card.
2. The full job description is in the card's Job Description section. A stub, a truncated description or a prose pointer is a stop, per rule 1.

There is no band and no run limit. The card's Evaluation section carries the screen's reading, which records what the title and the description named. It is not a grade and it is not a precondition.

## Step 1. Read the inputs

Read these and nothing else. Nothing outside them counts as evidence.

| Input | What it gives |
| --- | --- |
| the card | the title, company, location, posting url and the archived description |
| [knowledge/](../../knowledge/) | the evidence, and only notes marked `cv-ready: true` may be cited |
| [05. profile](../../05.%20profile.md) | the summary and the contact details |
| `resume/sbm_de_26.tex` | the EU base |
| `resume/sbm_in_26.tex` | the India base |

The two bases are the fact authority together with the knowledge notes. The old project's `cv.md` is not a source and is not consulted, because it carries claims the notes reject, including a 5 to 7 millisecond control boundary and a sub-millimetre IK validation that the repositories do not support.

Where a note and a repository disagree, the repository wins, per rule 15.

## Step 2. Pick the base by market

India location means `sbm_in_26.tex`, anything else means `sbm_de_26.tex`. The two differ in exactly three lines, namely the contact line, the M.Sc. grade rendering and the B.E. grade rendering. Never build an India variant from the EU base, which is the failure `market_gate.py` exists to catch.

## Step 3. Change exactly two things

Rule 24 freezes everything else. Per variant only these may differ from the base.

**The projects section.** Selected from the exhaustive pool, namely Chess Robot Arms and Attitude Estimation on ARM Cortex-M4 as the canonical pair, with Autonomous Maze Navigation, the IoT Weight-Based Ignition System and the Seed Counting Machine swappable by relevance. SofDCar and the HVAC project are eliminated and never selected. The maze project carries its ongoing marker. The Seed Counting Machine's approved entry text is in its knowledge note and is used verbatim.

**The `\professional{}` tagline.** Changed only when the new tagline names an identity his record supports, which is a title he would defend with a plain yes in an interview.

One further change is licensed, which is a course line inside the Academics section. An AI or ML role, or a description naming TinyML, embedded ML, on-device inference or edge AI, brings the Edge Impulse course. A description naming Arm processors, Arm architecture, Cortex-M or Cortex-A brings the Arm course. Both may fire. It is a single `\academicsentry` line under the Certificate of Advanced Studies entry, never a section heading, and never the Google Cybersecurity course which has no trigger.

Everything else is byte-identical to the base. No bullet rewording, no reordering, no additions, no removals, no skills-line edits.

## Step 4. Select the projects on evidence

Read what the role actually needs from the description, meaning the disciplines, the responsibilities and the environment, rather than its word list. Then pick the projects whose work answers that need.

A term from the description enters only when the causal chain from something he did is written out, per rule 13. The keyword is not the qualification, the work is.

Fill the page. There is no project count, only the two page limit, so add the next most relevant project until a third page would appear.

## Step 5. Name and write the file

```
application artifacts/resume/sbm_<company-slug>_<dd>_<mm>.tex
```

A role slug is added when more than one role at the same company is produced on one day, per rule 30. `dd_mm` is today.

`bmsnkresume.cls` already sits in that folder, which the compile needs beside the source.

## Step 6. Compile and measure

```bash
cd ~/job-application && bash scripts/build_artifacts.sh "application artifacts/resume/sbm_<slug>_<dd>_<mm>.tex"
```

Two lualatex passes, with the PDF landing beside the source. The script checks for a silently substituted font, which lualatex does not report as an error, and it prints the page count and the overfull box count.

Two pages or it is not finished. Rule 25.

## Step 7. Run the market gate

```bash
cd ~/job-application && .venv/bin/python scripts/market_gate.py "application artifacts/job cards/<card>.md"
```

A FAIL blocks delivery. Fix and rerun. It is run rather than reasoned about, because the prose rule it enforces was skipped by a batch run and two truthfulness reviews passed the result, since a German phone number is true.

The gate reads the card's `cv` and `coverletter` keys, so those must point at the new files before it can pass.

## Step 8. Write the card and report

Set the card's `cv` key to a `file://` URL of the PDF, per rule 70. Report the page count, the overfull count, the gate verdict and which projects were selected with the reason.

## Step 9. Hand off to the critic, always

```
skills/adversarial-verification-artifacts
```

Rule 31 makes this mandatory, so it is a step rather than an option. Invoke it on the `.tex` source, not the PDF, since its CV checks diff against the base and a PDF cannot be diffed.

A FAIL is fixed and the document is recompiled and re-reviewed. Nothing reaches him before it passes, and a document is never presented with an open flag attached as a note.

The critic runs the market gate itself, so step 7 is the generation-time check and the critic's run is the gate of record.

## Never

Consult the old project's `cv.md`.

Change anything outside the projects section, the tagline and a triggered course line.

State a version or a standard the record does not hold, which means plain C++ with no standard number, and language levels exactly as evidenced.

Claim a named safety standard by transfer, which means ISO 26262, DO-178C, DO-254 and AUTOSAR stay gaps.

Drop or merge a true, distinct piece of work to fit the description's focus.

Ship a document carrying a flag the run raised itself. Resolve it or revert, per rule 33.
