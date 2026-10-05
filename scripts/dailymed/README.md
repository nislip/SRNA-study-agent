# DailyMed refresh

Keeps the drug-conversions skill's label excerpts current. Runs monthly via
`.github/workflows/update-dailymed.yml`.

## Files
- `update_dailymed.py`: fetches labels and writes `<skill>/references/*.md` and `INDEX.md`.
- `drugs.yaml`: the curated drug list. Edit this to add, remove, or pin drugs.
- `manifest.json`: generated. Records which label (setid) and version each file came from.
  Don't edit by hand; delete an entry to force that drug to be re-selected.

## Common tasks
- **Add a drug:** add a line to `drugs.yaml`, then run the workflow manually or wait for the 1st.
- **Wrong label picked:** find the right label on dailymed.nlm.nih.gov, copy the `setid`
  from its URL, and add `setid: ...` to that drug's line.
- **Remove a drug:** delete its line. Its file is removed on the next run.
- **Test locally:** `pip install -r requirements.txt`, then
  `python update_dailymed.py --skill-dir ../../space/skills/drug-conversions --only rocuronium`

## Behaviour notes
- Only labels whose `spl_version` changed are downloaded, so monthly runs are quick.
- A failed fetch never changes an existing file; failures are listed in the PR.
- The run fails (red X) only if every drug failed, which usually means DailyMed is down.
- Sections kept and the per-section size cap are set at the top of the script.
