"""
Ad hoc one-off script (run directly with python, NOT via manage.py test).

Reconciles Award <-> ScoreSheet.prizes gaps found during an audit on 2026-09-16.

Step 1: delete 2 orphaned test/placeholder Award rows (contestant_id=1, the
        admin's own account, olympiad 210/212, place text ending in "(ID)").
        Verified: no Result or ScoreSheet row exists for user 1 in either
        olympiad, so these are leftover test artifacts, not real awards.

Step 2 (generate_scoresheets reruns for olympiads 153/192/193/194/204/212/214/216)
        was already applied separately via the management command and is not
        repeated here.

Step 3: backfill Award rows for the 144 (olympiad, contestant) pairs where
        ScoreSheet.prizes has text but no matching Award row exists, using
        the exact same text as the place value, so future `generate_scoresheets`
        reruns don't silently wipe this data (that command treats Award as the
        sole source of truth for ScoreSheet.prizes).

Usage:
    cd /var/www/mmo
    source venv/bin/activate
    python fix_award_scoresheet_sync.py

Safe to re-run: both steps re-check current DB state before writing anything.
"""
import csv
import os
import sys

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mmo.settings")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from olympiad.models import Award, Result, ScoreSheet  # noqa: E402


def step1_delete_junk_awards():
    print("=== Step 1: delete junk test Award rows (contestant_id=1) ===")
    ids = [50514, 50515]
    qs = Award.objects.filter(id__in=ids)
    rows = list(qs.values("id", "olympiad_id", "contestant_id", "place"))
    if not rows:
        print("  Nothing to delete (already removed, or ids differ from expected).")
        return

    for r in rows:
        oid, cid = r["olympiad_id"], r["contestant_id"]
        has_result = Result.objects.filter(olympiad_id=oid, contestant_id=cid).exists()
        has_sheet = ScoreSheet.objects.filter(olympiad_id=oid, user_id=cid).exists()
        if has_result or has_sheet:
            print(f"  SAFETY ABORT: award {r['id']} (olympiad={oid}, user={cid}) now has a "
                  f"Result/ScoreSheet trace — not deleting, please review manually.")
            return

    print("  Deleting:", rows)
    qs.delete()
    print(f"  Deleted {len(rows)} row(s).")


def step3_backfill_awards():
    print("=== Step 3: backfill missing Award rows from ScoreSheet.prizes ===")
    csv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "_award_backfill_only_in_sheet.csv")
    rows = list(csv.DictReader(open(csv_path, encoding="utf-8")))

    to_create = []
    skipped = []
    for r in rows:
        oid = int(r["olympiad_id"])
        cid = int(r["contestant_id"])
        text = r["prizes_text"]

        if Award.objects.filter(olympiad_id=oid, contestant_id=cid, place=text).exists():
            skipped.append((oid, cid, text, "award already exists"))
            continue

        ss = ScoreSheet.objects.filter(olympiad_id=oid, user_id=cid).first()
        if not ss or (ss.prizes or "").strip() != text.strip():
            skipped.append((oid, cid, text, f"scoresheet prizes changed: {ss.prizes if ss else 'NO SHEET'!r}"))
            continue

        to_create.append(Award(olympiad_id=oid, contestant_id=cid, place=text))

    print(f"  Rows in CSV: {len(rows)}")
    print(f"  To create: {len(to_create)}")
    print(f"  Skipped: {len(skipped)}")
    for s in skipped:
        print("    SKIP:", s)

    created = Award.objects.bulk_create(to_create, batch_size=500)
    print(f"  Created {len(created)} Award rows.")


if __name__ == "__main__":
    step1_delete_junk_awards()
    print()
    step3_backfill_awards()
