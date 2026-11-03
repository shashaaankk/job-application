---
name: adversarial-verification-artifacts
description: Hostile review of a generated CV or cover letter before it reaches Shashank. Runs automatically after resume-generation or coverletter-generation, and on request when he asks to check, critique or verify a document. A document is never presented without it.
---

# Artifact verification

Two passes on every document, in order. Pass one asks whether it is honest. Pass two asks whether it works. A document failing either does not reach him.

The passes are deliberately different readers. Pass one assumes the document lies and goes looking. Pass two forgets truthfulness entirely and becomes a recruiter with twenty seconds.

## Why this exists as a separate step

A six-agent review once passed ten letters that each broke the same rules, because every sentence in them was true. Truth is necessary and not sufficient, which is why the mechanical gates run inside this skill rather than beside it, and why their output is not re-argued.

## Inputs

| Input | Role |
| --- | --- |
| the document under review | the `.tex` source, never the PDF, since the source is what a diff can read |
| the base template | `resume/sbm_de_26.tex` or `resume/sbm_in_26.tex`, which is the baseline for every CV diff |
| the card | the posting, the archived description and the evaluation |
| [knowledge/](../../knowledge/) | the evidence, where only `cv-ready: true` notes count and a NOT evidenced line is binding |
| [05. profile](../../05.%20profile.md) | the summary and the contact details |
| [11. views](../../11.%20views.md) | his stated positions, with their applicability lines |
| [06. rules](../../06.%20rules.md) | the rules the document is checked against |
| [10. lessons learnt](../../10.%20lessons%20learnt.md) | the failures that must not recur |

The old project's `cv.md` is not an input. It carries claims the knowledge notes reject, so checking a document against it would pass the very errors this skill exists to catch.

When no `.tex` source exists, which is true of most migrated documents, say so and run only the checks that read the text itself. A diff-based check with no baseline is reported as not run, never as passed.

---

# Pass one, hostile truthfulness

Assume the document contains at least one unevidenced claim and one misalignment. Find them.

## Checks on any document

1. **Claim audit.** Every factual claim, meaning every skill, tool, metric, standard, version, language level and date, is traced to a `cv-ready: true` note or to [05. profile](../../05.%20profile.md). No evidence is the verdict INVENTED. A note's NOT evidenced line overrules the note's own summary.
2. **Lessons compliance.** The document is read against [10. lessons learnt](../../10.%20lessons%20learnt.md). A repeat of a recorded failure is CRITICAL rather than a flag, because it was already paid for once.
3. **Fabricated term.** Any activity, artefact or practice term present in the document and absent from both the baseline and the evidence is presumed INVENTED rather than assumed to be a rewording. It has to be a real recognised practice in that domain and within the documented scope of that role. Failing either test means deletion, not rewording.
4. **Alignment.** The framing matches his current position and honest level. Overselling seniority or misstating the enrolment is a flag.
5. **Internal consistency.** Dates cohere, no bullet contradicts another, the contact block matches the market, and the email is right.
6. **Named standard by transfer.** ISO 26262, DO-178C, DO-254 and AUTOSAR are gaps unless the record holds them. The adjacent discipline is stated factually and nothing more.
7. **AI prose.** Read it as a manager screening 200 applications a week. The tells are copulative dodges, negative parallelism, trailing participles carrying no fact, the AI vocabulary set, stiff verb synonyms, rule-of-three padding where the real count is two, the same referent renamed across sentences, and significance inflation. The fix is plainer wording, never softer wording.

## Checks on a CV only

The freeze makes these stronger here than they were in the old project. Only the projects section, the `\professional{}` tagline and a triggered course line may differ from the base, so any other difference is a rule 24 violation on its face and needs no interpretation.

8. **Freeze diff.** Diff the variant against its base. Every changed line outside the three licensed slots is a FAIL, named FROZEN-EDIT, with the line quoted.
9. **Vocabulary graft.** For any bullet that did change, any new term that also appears in the posting is suspect. Ask whether it is the natural name he would use unprompted or a relabel of his work into their language. A relabel is NEEDY-GRAFT and the fix is reverting. A device label is never a discipline claim.
10. **Activity drift.** Compare each changed bullet's primary claimed activity and its purpose slot against the baseline. Added words are fine. A changed activity, or a downstream use promoted into the purpose slot, is CONTEXT-DRIFT and an automatic FAIL even when every word is true. The test is whether the baseline and the rewrite would lead an interviewer to open with the same sentence.
11. **Undermining.** Diff the bullet count per entry. A dropped or merged bullet must justify itself as genuine redundancy, meaning the same work described twice. Reducing emphasis for this posting is not a reason. Removal is UNDERMINED and the fix is restoring the bullet, since ordering is the legitimate emphasis tool.
12. **Head verb.** The opening verb phrase states the same accomplishment as the baseline. Replacing it with the posting's responsibility language is HEAD-GRAFT and an automatic FAIL. Also check method coherence, since a claimed activity has to be something the listed methods can actually accomplish.
13. **Project pool.** Every selected project is from the five-item pool. SofDCar and the HVAC project are eliminated and their presence is a FAIL. The maze project carries its ongoing marker.
14. **Two pages**, measured with `pdfinfo` rather than estimated.

## Gates, run rather than reasoned about

A FAIL from either script is terminal and is not re-argued. Its REVIEW findings are each read and answered, since they exist for a human to settle.

```bash
cd ~/job-application
.venv/bin/python scripts/market_gate.py "application artifacts/job cards/<card>.md"
.venv/bin/python scripts/letter_gate.py "application artifacts/coverletters/<letter>.tex"
```

`market_gate.py` runs on every document, because it is the market check. `letter_gate.py` runs on letters only.

## Letter doctrine, the half no script can decide

Run these on any cover letter, after the gate and before pass two. Each verdict name is a FAIL.

15. **NO-WHY.** Point at the sentence answering each of the three questions, why this company, why this role and why him. A missing answer is a FAIL. A fit claim says he can, not why he wants, and a poetically inverted why fails equally, since the test is whether he could say it aloud across a table.
16. **SHALLOW-DEPTH.** Paragraph two names an experience and explains nothing inside it, with no decision, no difficulty and no reason. Depth that traces to neither the vault nor his card answers is INVENTED and terminal.
17. **ORPHAN-EXPERIENCE.** An experience recounted with methods and results that answers nothing the letter raised. The fix is cutting it and deepening what remains, never bolting a takeaway onto it.
18. **CIRCULAR.** List the distinct facts and count each fact's tellings. Any fact told twice in new words is a hit, however well each telling reads.
19. **JD-RECITAL.** Any sentence restating the role summary or the requirements back to the reader, who wrote them. Only the position title and location may come from the advert.
20. **LECTURE.** A company fact restated as a sentence of its own, such as their mission or careers-page wording. The company's stated goal may appear only as the hook for his own position, in the same sentence. Also a LECTURE is any sentence explaining his field to the reader, for example that estimation and planning share a vehicle model, which a team lead already knows.
21. **PHANTOM-PLATFORM.** A product, platform or team named that neither the posting nor a fetched source ties to the advertised role. Keyword overlap is inference, not evidence.
22. **COLD-JUMP and SIGNPOST.** Paragraph two opening with no linker from paragraph one, and any sentence whose only job is to label what follows. Delete it, and if no fact is lost it was a signpost.
23. **MANUFACTURED-CONVICTION and VIEWS-OVERREACH.** A belief derived from what he did rather than from a [11. views](../../11.%20views.md) entry, and an entry deployed outside its stated applicability line.
24. **INVENTORY-FALLBACK and CONFLATION.** Paragraph two padded with tool names, standards, coverage numbers or validation stages, which usually means the evidence held no depth. And distinct work items fused into one continuous work.
25. **ENTRY-RECITAL.** A resume fact rendered as a CV entry rather than as a capability statement.
26. **TITLE-CONFLICT and CV-MISMATCH.** The opening labels him with a job title that conflicts with the advertised role, or any date, duration, degree name or employer fact differs from the CV he applies with. A summed duration counts. The degree is an M.Sc. in Embedded Systems Engineering. Employers are named, which reverses the earlier EX-NAMING check.
27. **STRANGER-TEST.** Any sentence assuming knowledge the letter has not given.
28. **VENTRILOQUISM.** Any want, preference, ease or relocation claim not traceable to his own words.
29. **BOX-FIRST.** The letter arguing fit by qualifications before it states a motivation. The paragraph one introduction is not a violation, a fit argument placed before the motivation is.
30. **NO-CAUSE-ENGAGEMENT.** The letter is entirely about him, with nothing showing he engaged with their work or their stated problem.
31. **GAP-SPOTLIGHT.** Any sentence that draws attention to what he has not done, such as a project stopping short of the role's work or the work being outside its scope. The posting is a wish list and the letter must not undermine the application.
32. **PASTED-CONTEXT.** Wording he supplied for understanding, such as "the left side of the V model", pasted into the letter. Ownership is shown through plain verbs for what he did.
33. **AI-CADENCE.** Read every sentence against the [human-voice skill](/home/shashaank/.claude/skills/human-voice/SKILL.md) and the SESSION-FLAGGED list in `scripts/letter_gate.py`. Crafted stand-alone sentences, slogans, syllogisms ending in "so I applied", stock closers and equal-weight template paragraphs are each a hit, even when the gate passes them.
34. **FRAMING-UNTRUE.** A sentence that groups several experiences and is false for one of them. "A learned model had to work inside a system that acts" was false for a model that only classified signals.
35. **STORY-BEYOND-NOTE.** A cause, a failure or a before-and-after the knowledge note does not record. A note saying a fix made something reliable does not say it failed first, or why.
36. **TEMPLATE-COPY.** Paragraphs copied from the shape of the reference letter where the role gives them no job, such as a production-ownership paragraph on a robot learning letter.
37. **STRETCH.** The letter recasts unrelated work as the role's field, or states a transfer the knowledge notes do not support. A transfer is valid when the same methods, tools or problem appear in his work. The fix is rewriting from the writer skill's bridge map with honest transfers, never dropping the letter.
38. **VIEWS-LECTURE.** A views position stated as telling the company how it should think, or used outside its applicability line.

A flag raised during generation that reaches this skill unresolved is an automatic FAIL. A document is never compiled or presented with an open flag attached as a note.

---

# Pass two, the recruiter skim

For a letter, the recruiter also reads with the 2026-10-15 research in mind. Hiring managers say they dislike AI-written letters, recognise them by generic, repetitive and personality-free prose, and look for original content and a link to the company. The verdict states whether the letter reads as written by a person and whether the first paragraph places him in the role's field.

Change role completely. Become a senior recruiter with roughly twenty seconds per CV, screening a stack against this posting. Accuracy is not the question now. The question is whether this one goes in the yes pile.

1. **List the must-haves.** Re-read the description and name the five to eight requirements a screener actually checks, separated from the nice-to-haves.
2. **Simulate the skim.** Look only at the tagline under the name, the most recent role title and its first bullet, the first bullet of every other entry, the project titles and their stack lines, the skills line, and anything bold or numeric. Everything else is unread on the first pass.
3. **Score each must-have** as HIT when a skimmer finds it, BURIED when it is in the document but below the skim line or on the wrong page, and MISSING when it is absent.
4. **Then read properly** and note what would make a recruiter hesitate, such as a title that does not match the role, a date gap, a first bullet that opens on method rather than accomplishment, or a project order leading with the least relevant work.

## The constraint that makes pass two safe

Every fix it proposes is a reorder, a reselection or a reword of true work. Pass two has no authority to add anything pass one would reject.

A BURIED item is fixed by moving the bullet or entry that already holds it, which is usually enough. A MISSING item is reported as a genuine gap and left alone, because the honest answer is that the CV cannot answer it and the letter or the interview must. The structure stays frozen.

If pass two produces a suggestion pass one would flag, pass two is wrong. Rerun pass one on any document changed as a result.

---

# Output

Pass one is a table.

```
| # | Claim or issue | Location | Verdict | Fix |
```

Verdicts are INVENTED, UNEVIDENCED, FROZEN-EDIT, NEEDY-GRAFT, CONTEXT-DRIFT, UNDERMINED, HEAD-GRAFT, AI-PROSE, CRITICAL, one of the letter doctrine names, or OK with a note. Then a plain PASS at zero flags, or FAIL with the required fixes listed.

Pass two is two lists in the recruiter's voice, namely what is off and what to tune, with the second ranked by how much each fix moves the yes or no. Then a one-line verdict naming the pile and the single change that moves it up one.

# Delivery

Findings go onto the card as unchecked checkboxes under Questions, and the card states the document is BLOCKED until they are resolved. Chat carries one line saying the card is ready.

A finding that lives only in chat has not been delivered, since he works from the board.

# The learning loop

A new flag type is appended to [10. lessons learnt](../../10.%20lessons%20learnt.md) in the same turn, with what it caught and why it was missed. If he later corrects something this skill passed, that goes in too.

That loop is the only reason the check list grew to this length, and it is why a rule here is never relaxed to make a document pass.
