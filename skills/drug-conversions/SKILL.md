---
name: drug-conversions
description: Look up FDA label dosing for anesthesia drugs and work through dose, concentration, and infusion-rate conversions step by step. Use this whenever someone asks about a drug's dose, dosing range, concentration, onset or duration, maximum dose, renal or hepatic adjustment, mg-to-mL or mcg/kg/min-to-mL/hr math, or any drug calculation, even if they don't say "conversion" or "label". Covers induction agents, opioids, neuromuscular blockers and reversal, local anesthetics, vasoactives, and common adjuncts.
---

# Drug conversions and label reference

This skill supports SRNA study. It is not clinical guidance. If someone shares patient-identifying details, remind them not to, and answer only in general terms.

## Where answers come from, in order

1. **Bundled label excerpts.** Open `references/INDEX.md` and find the drug by id or alias. Then open the file it lists, such as `references/rocuronium.md`. These are selected sections of one FDA label per drug, refreshed monthly from DailyMed.
2. **Live label lookup.** If the drug isn't in the index, use the openFDA drug label tool if it's available. Say the answer came from a live lookup, and note that labels can differ between manufacturers.
3. **General knowledge.** Only when neither source has the answer, and say so plainly ("this isn't from the label").

Some drugs have one file per route, like `lidocaine-local` and `lidocaine-iv`, because their labels dose differently. Pick the file that matches the route being asked about, and ask if the route is unclear.

## How to answer from a label file

- Give doses exactly as the label states them, with units and the basis (per kg, total, per hour).
- End with the source on one line, taken from the file's header: label title, SPL version, published date, and the DailyMed link.
- Labels describe approved dosing, which can differ from anesthesia practice or a program's teaching. When that gap is well known, mention it briefly and keep the label answer separate from the practice point.
- If a section says it was truncated, or a needed section is listed as "not present on this label," say so and give the DailyMed link rather than filling the gap from memory.

## Chemistry questions

For chemical name, molecular formula, molecular weight, pH, or pKa, use the label's Description section. For active and inactive ingredients (preservatives, excipients such as sulfites or egg lecithin), use the "Ingredients and Composition" table.

## Conversions

Show every step with units, so the person can check the work and learn the method.

1. **Find the concentration** in the "Ingredients and Composition" table, which lists each product's exact strength (for example, 10 mg in 1 mL). The "Dosage Forms and Strengths" section describes the same products in words. If several strengths exist, ask which one, or show the math for the most common one and say which you chose. Note whether the strength is stated as the salt or the base (for example, "as hydrochloride"), since that changes the math.
2. **Set up the calculation with units written out.** For example: 0.6 mg/kg × 80 kg = 48 mg, then 48 mg ÷ 10 mg/mL = 4.8 mL.
3. **Infusions:** dose (mcg/kg/min) × weight (kg) × 60 min/hr ÷ concentration (mcg/mL) = rate (mL/hr). Convert mg/mL to mcg/mL first when needed.
4. **Check units at every step,** especially mcg vs mg and per minute vs per hour. Most dosing errors happen there.
5. **Weight basis:** if the label specifies actual, ideal, or lean body weight, use that and say so. If it doesn't specify, say the label doesn't specify.
6. **Round only at the end,** and state how you rounded.
7. **Sanity check:** compare the result to the label's dose range and flag anything outside it.

**Conversions between drugs or routes** (for example opioid equianalgesic ratios, or IV to oral): only use a ratio that appears in a label file or in `references/conversions.md` if that file exists. If neither has it, say so instead of supplying a ratio from memory. These ratios vary between sources, and a wrong one is dangerous.

## Notes

- Files in `references/` are generated automatically each month. Don't treat them as editable.
- The bundled set covers a curated list, not every drug on DailyMed.