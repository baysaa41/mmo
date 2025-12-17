# olympiad/management/commands/classify_problems.py
from django.core.management.base import BaseCommand
from olympiad.models import Problem, Topic
import re

LEXICON = {
    "ALG": [
        r"тэгшитгэл", r"тэгш бус", r"функц", r"олон гишүүнт", r"прогресс",
        r"илэрхийлэл", r"радикал", r"лог", r"хувьсагч", r"шугаман"
    ],
    "COM": [
        r"комбинаторик", r"пермутац", r"комбинац", r"байршил", r"граф",
        r"зам", r"суудал", r"тавих", r"тооллог", r"магадлал", r"сонгох", r"зоос"
    ],
    "GEO": [
        r"геометр", r"гурвалжин", r"квадрат", r"дөрвөлжин", r"тойрог",
        r"диаметр", r"радиус", r"муруй", r"талбай", r"өнцөг",
        r"параллелепипед", r"вектор", r"координат", r"пифагор",
        r"синус", r"косинус", r"огтлолцол", r"куб"
    ],
    "NUM": [
        r"анхдагч", r"хуваагч", r"Евклид", r"диофант", r"модуляр",
        r"модул", r"хуваагдах", r"конгруэнц", r"факториал", r"арифметик"
    ],
}

CATEGORY_NAME = {
    "ALG": "Алгебр",
    "COM": "Комбинаторик",
    "GEO": "Геометр",
    "NUM": "Тооны онол",
}


def normalize_text(s: str) -> str:
    s = re.sub(r"\$.*?\$", " ", s)  # inline math
    s = re.sub(r"\\[a-zA-Z]+", " ", s)  # LaTeX команд
    return s.lower() if s else ""


def classify_statement(statement: str):
    text = normalize_text(statement or "")
    scores = {}
    for cat, patterns in LEXICON.items():
        scores[cat] = sum(1 for pat in patterns if re.search(pat, text))
    best_cat = max(scores, key=scores.get)
    return best_cat if scores[best_cat] > 0 else None


class Command(BaseCommand):
    help = "Олимпиадын бодлогын statement-г keyword-д суурилж ангилах"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Өөрчлөлт хадгалахгүй, зөвхөн консолд хэвлэх")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        assigned = 0
        skipped = 0

        for p in Problem.objects.all().order_by("id"):
            category = classify_statement(p.statement)
            if category:
                topic, _ = Topic.objects.get_or_create(
                    category=category,
                    name=CATEGORY_NAME[category]
                )
                if dry_run:
                    self.stdout.write(f"[DRY] Problem#{p.id} → {topic.name}")
                else:
                    p.topics.set([topic])
                    assigned += 1
            else:
                skipped += 1

        self.stdout.write(self.style.SUCCESS(
            f"Done. {assigned} бодлогод ангилал оноов, {skipped} бодлого тодорхойгүй үлдлээ."
        ))
