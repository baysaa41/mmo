"""
Ad hoc one-off script (run directly with python).

Fixes the 3 content-mismatch rows found in olympiad 146 (ММО-60, II даваа I шат)
during the 2026-09-16 Award<->ScoreSheet.prizes audit:

    user 22208:  Award='II шат эрх, дүүрэг'  ScoreSheet.prizes='Хүрэл медаль'
    user 103399: Award='II шат эрх, дүүрэг'  ScoreSheet.prizes='Мөнгөн медаль'
    user 70505:  Award='II шат эрх, дүүрэг'  ScoreSheet.prizes='Алтан медаль'

Both values are confirmed correct (user's decision) and should coexist:
each student earned BOTH the district round-2 qualification AND the medal,
but only one side had an Award row. This script adds the missing medal
Award row for each, then reruns generate_scoresheets for olympiad 146 so
ScoreSheet.prizes (and rankings) are rebuilt from the now-complete Award data.

Usage:
    cd /var/www/mmo
    source venv/bin/activate
    python fix_award_146_medals.py

Safe to re-run: uses get_or_create, and generate_scoresheets is idempotent.
"""
import os
import sys

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mmo.settings")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from django.core.management import call_command  # noqa: E402
from olympiad.models import Award  # noqa: E402

FIXES = [
    (146, 22208, "Хүрэл медаль"),
    (146, 103399, "Мөнгөн медаль"),
    (146, 70505, "Алтан медаль"),
]


def main():
    print("=== Adding missing medal Award rows for olympiad 146 ===")
    for oid, cid, medal in FIXES:
        obj, created = Award.objects.get_or_create(
            olympiad_id=oid, contestant_id=cid, place=medal
        )
        print(f"  olympiad={oid} user={cid} place={medal!r}: "
              f"{'created' if created else 'already existed'} (award_id={obj.id})")

    print()
    print("=== Rerunning generate_scoresheets for olympiad 146 ===")
    call_command("generate_scoresheets", 146, verbosity=2)


if __name__ == "__main__":
    main()
