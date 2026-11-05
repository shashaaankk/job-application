---
name: coverletter-generation
description: Write one cover letter for a posting, in Shashank's voice and format. The only skill permitted to produce a cover letter in this vault. Use ONLY when he names a posting or card and asks for a letter. Letters are never produced in a batch or a scheduled run. Never use a stock or marketplace cover letter skill instead.
---

# Cover letter generation

This skill tells the writer how to write a good letter. What a letter must not do lives with the critics, in the letter doctrine of `skills/adversarial-verification-artifacts`, in `scripts/letter_gate.py`, and in [06. rules](../../06.%20rules.md) Letters, which wins on any disagreement. He ruled on 2026-10-15 that a writer is taught what to do and the anti-patterns belong to the critics.

Follow every step in order.

## What a good letter does

A cover letter answers three questions for a recruiter, why this company, why this role and why him. A good letter answers them the way an engineer would explain it to another engineer across a table, with one real story, plain sentences and true facts. Recruiters say they want original, specific letters that connect to the company, and they reject letters that read generic.

## Inputs

1. The full job description. Read it through the card, or fetch a LinkedIn posting at `https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/<id>`.
2. The CV he applies with, `~/Job Applications/resume/sbm_de_26.tex`, or `sbm_in_26.tex` for India. Every fact in the letter is written the way the CV states it.
3. [05. profile](../../05.%20profile.md), [11. views](../../11.%20views.md) and the [knowledge](../../knowledge/) notes. The notes hold the depth, the corrections and the scope of each experience.
4. `~/.claude/skills/human-voice/SKILL.md`, which describes the plain register the letter is written in.
5. The accepted MOTOR Ai letter, `application artifacts/coverletters/sbm_motorai_15_10-coverletter.tex`, as an example of the register and of an opening that flows. Each letter takes its paragraphs from its own three answers.

A card is optional. When there is one, its Evaluation holds the scorer's must-have table. Rows scored 3 are candidates for Done, rows scored 2 for Transfers, and rows scored 0 or 1 for Missing. Use it as the first draft of the Step 1 bridge map, never as the map itself, because Step 1 still reads every cv-ready note.

## Step 1. Map the bridge

He applies across domains on purpose. The German automotive market is cutting jobs and senior engineers fill the roles in his own field, so a posting's requirements are a wish list and a role he can grow into is a valid application. Every request gets a letter, and this step finds the honest strongest case for it.

1. Write the role's central work from the description as three to five short lines.
2. Mark each line with one of three labels, using the knowledge notes.
   - **Done.** He has done this work. Name the experience.
   - **Transfers.** He has done the same kind of work in a neighbouring field, with the same methods, tools or problem. Name the experience and write the transfer as one plain clause, for example that deploying a perception model on a Jetson under a latency budget transfers to running a learned policy on robot hardware.
   - **Missing.** Nothing in his record does this work.
3. Name the views entry whose applicability line covers this kind of role.
4. When no views entry covers the role, ask him one question before drafting, why he wants this kind of work. Write his answer into [11. views](../../11.%20views.md) as a new entry in his words, with its applicability line, so the next letter in that domain has it.

The letter is built on the Done and Transfers lines. Missing lines are left for the interview.

## Step 2. Write the three answers as notes

1. **Why this role.** Pick the experience from a Done line, or else from the strongest Transfers line, whose work is closest to the role's. Write down the problem it dealt with, one concrete scenario from the note, what he did, and the measured result. Write down the link from that problem to the problem the role works on.
2. **Why him.** Write down what he can do for this team from day one, taken from the Done and Transfers lines and written in the role's terms. Write each transfer as one plain clause, for example that vehicle dynamics estimation is the vehicle state a planner depends on. Where most lines are Transfers, also write down the evidence that he gets up to speed in a new field, from a project where the note records him learning a new stack and delivering with it.
3. **Why this company.** Write down what the company is working toward, from the description, and the views entry position that meets it. Use the position as it applies to the company's goal.

Check each note against the knowledge note it came from. Keep only what the note records, scoped the way the note scopes it. Where a note leaves an answer open, ask him.

## Step 3. Write the letter

Write it from the Step 2 notes, in his voice, in this order.

1. **Opening.** Start with "I am Shashank, a recent M.Sc. graduate in Embedded Systems Engineering from the University of Stuttgart." Then say what the work he will use in the letter was about, as what he built or shipped, and where. Name the employer. Let each sentence pick up from the one before. End the paragraph with the position title and city, joined to that work.
2. **Why the role.** Tell the experience from note 1 as a short story. Start with the problem as people met it. Give the concrete scenario as one example of several when the note says there were several. Say what he did in plain past-tense verbs. End on what came of it, with its number.
3. **Why him.** Say what he can do for this team from day one, in the role's terms, from note 2. Show ownership through the verbs of what he did. State each transfer in one clause. Where the role is in a neighbouring field, add the sentence that shows he gets up to speed, with its evidence.
4. **Why the company.** Carry the story's problem into the company's setting. Name the company, state what it is working toward in a few words, and state his position from note 3 as his own view.
5. **Close.** "I hold a German residence permit under § 20 AufenthG with full work authorisation. I look forward to hearing from you." Then "Kind regards," and "Shashank Birur Manjunatha". India letters close with only the second sentence.

Merge or split paragraphs 2 to 4 when the material reads better that way, so the paragraphs come out at different lengths. Aim for 300 to 450 words on one page.

A transfer is written as a thing he can do, never as where the work came from. He struck a letter on 2026-10-30 for naming the provenance first, as in a research project at Stuttgart set up to measure something. A reader does not care which employer or which semester produced the skill, and leading with provenance tells them the evidence is a student project before it tells them it is a capability. So the sentence opens on the ability in the role's terms, for example that he can take a timed path apart and say where its time goes, and the work that proves it follows inside the same sentence or the next one. The purpose-first rule for causality still holds, and it is satisfied inside the proof clause.

The letter shows that he cares by what it commits to, never by a justification. He asked for the parallels and the motivation, and got a defence of the choice of evidence instead. A paragraph that explains why an experience was selected is writing about the letter rather than writing the letter. Motivation is one plain statement of what he is in the field for, placed with the views position, and the rest of the letter is ability.

The motivation paragraph is said, not declared. He struck one on 2026-10-30 as robotic and without passion. It had failed in four ways at once. It opened on the template "What draws me to X is that Y". It announced the position with "My view is that", which no one says aloud. It argued in an abstract noun, the check, repeated four times in four sentences. And its four sentences were the same length and the same shape, which is what makes a paragraph sound like a machine reasoning. Write it instead as the thing he would actually say, with the belief carried by a concrete question such as how wrong a function can be, with the sentences at different lengths, and with the consequence named plainly at the end.

Their work is described from outside, modestly and with curiosity. He struck a line on 2026-10-30 that ranked their product, "ImFusion's SDK is one of the few places where", because it speaks about a company's work with an ownership and an authority he does not have. Write what he can observe and say that he can only observe it, for example "From what I can see of the SDK", and let the interest show as a question he wants answered rather than as a verdict on their engineering.

The professional work carries the letter and a university project is supplemental. He ruled on 2026-10-30 that the ADAS work at Continental is the parallel to draw, and that a research project belongs as a supplemental entry of a clause or two. A posting that says it is not entry level and discounts academic projects makes this worse, but the rule is not conditional on that. Build the evidence paragraph from the employment, and let the project add the one property the employment does not carry.

The motivation never tells the company anything about its own work. He struck a paragraph on 2026-10-30 that argued prototype code should ship and that the question to ask of a function is how wrong it can be. Both are true and both are the company's own business, so stating them reads as instruction from an applicant who has not worked there. Write the motivation as autobiography instead, meaning what he moved toward and why, with the company named once as the place that work happens. His own line for this role was that in driver assistance the consequence of a wrong output is spread thin across a traffic scene, and at the institute it is one patient and one liver.

The bridge map runs over the whole vault before a paragraph is chosen. On 2026-10-30 four drafts went out built on the ball balancing robot and the ADAS work while the thesis sat unused, and the thesis is the only place in his record where image data moves through a system at rate on a GPU, with throughput benchmarked across backends and the bound measured. He said the evidence itself was too weak, and he was right, because the strongest item had never been considered. Step 1 is not done until every cv-ready note has been read against the role's central work, not only the notes the role's job title suggests.

Relevance beats coverage, and an experience that does not answer the role's work is left out. On 2026-10-30 he rejected a letter for putting his thesis in a role about ultrasound streaming and C++ hardware integration. The thesis is an LLM inference project with a perception front end, and the memory bandwidth figure its note licenses is scoped to the language stage, so using it under a sentence about image data at rate was a stretch of exactly the kind doctrine 37 names. A letter carries the two experiences that answer the posting's central work and nothing else, even when a third would add a number or fill a must-have on paper. Breadth in a letter reads as a candidate who has not understood the job.

How to write each sentence.

1. Use plain words he would use, such as wrote, built, shipped, tested and found.
2. Use is, are and has, and keep the same word for the same thing throughout.
3. Write one idea per sentence and vary the sentence length.
4. Give the numbers that show a result, at most four in the letter.
5. Write dates, durations, titles and the degree exactly as the CV has them.
6. Keep each sentence true for every item it mentions.
7. End each paragraph on a fact.
8. Use commas and full stops, never colons, em-dashes or brackets.

## Step 4. Write the file

Copy `coverletter/sbm_coverletter_26.tex` and replace only the body after `\letterhead`, keeping the preamble and its tagline-free letterhead as they are. Separate paragraphs with `\\` and a blank `\\` line. Escape `&`, `%` and `#`, and write the permit as `\S~20 AufenthG`. India letters use the Indian number in the letterhead contact line.

```
application artifacts/coverletters/sbm_<company-slug>_<dd>_<mm>-coverletter.tex
```

The slug is the company name in lower case with spaces removed.

## Step 5. Compile and gate

```bash
cd ~/job-application
bash scripts/build_artifacts.sh "application artifacts/coverletters/sbm_<slug>_<dd>_<mm>-coverletter.tex"
.venv/bin/python scripts/letter_gate.py "application artifacts/coverletters/sbm_<slug>_<dd>_<mm>-coverletter.tex"
```

Fix every FAIL and answer every REVIEW. The gate checks phrases and format only.

## Step 6. Independent review

A reviewer that did not write the letter reads it, given the posting, the letter, the CV, the knowledge notes and the letter doctrine in `skills/adversarial-verification-artifacts`. It reads as a recruiter with twenty seconds and returns accept or reject with reasons. For a role outside his direct experience, the reviewer reads as a hiring manager in that field and judges whether that manager would believe he can get up to speed and contribute, which is the test for such a letter. When the writer is a subagent, it returns the letter as a draft and the dispatching session runs the reviewer. On a reject, rewrite from the Step 2 notes and review again with a fresh reviewer. After a second reject, redo the Step 1 bridge map and look for a stronger transfer.

Letters are written and reviewed by the same model as the session he is working in.

## Step 7. Deliver

Show him the letter text in chat and send the PDF. If a card exists, set its `coverletter` key as a `file://` URL. Under the letter, list any claim that needs his confirmation, one short line each.

## Step 8. Learn from his edits

Write each correction back in the same turn. A correction about how to write goes into this skill as an instruction. A pattern he strikes goes to the critics, as a doctrine item or a gate pattern. A fact goes into its knowledge note, and a decision goes into [06. rules](../../06.%20rules.md) with its story in [10. lessons learnt](../../10.%20lessons%20learnt.md).
