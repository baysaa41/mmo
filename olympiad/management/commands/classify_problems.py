# olympiad/management/commands/classify_problems.py
"""
Олимпиадын бодлогын statement-г түлхүүр үг + LaTeX тэмдэглэгээнд суурилж
Алгебр / Комбинаторик / Геометр / Тооны онол гэж ангилна.

Түлхүүр үгс нь үгийн эхнээс таарах ёстой (жишээ нь "лог" гэдэг хэсэг
"бодлого", "олонлог" дотроос таарч байсан алдааг засав). Монгол хэл
нөхцөл залгадаг тул үгийн төгсгөлийг хязгаарлахгүй.

Анхдагч горимд зөвхөн ангилалгүй бодлогод ангилал онооно. Өмнө нь
оноосон ангиллыг дарж бичих бол --overwrite ашиглана.
"""
import csv
import re

from django.core.management.base import BaseCommand
from django.db import transaction

from olympiad.models import Problem, Topic

# (үгийн эх, жин). Үгийн эхнээс таарна.
LEXICON = {
    "ALG": [
        ("тэгшитгэл", 2), ("тэнцэтгэл биш", 3), ("функц", 3),
        ("олон гишүүнт", 3), ("прогресс", 2), ("илэрхийлл", 3),
        ("илэрхийлэл", 3), ("язгуур", 2), ("бодит тоо", 2), ("радикал", 2),
        ("логарифм", 3), ("парабол", 2), ("систем", 1), ("дараалал", 1),
        ("хурд", 2), ("үнэ", 1), ("хамгийн бага утга", 1),
        ("хамгийн их утга", 1), ("шугаман", 1), ("хувьсагч", 1),
        # текстэн бодлого: хөдөлгөөн, ажил, нас, хувь, үнэ, хэмжээ
        ("хурдан", 2), ("удаан", 1), ("минут", 2), ("секунд", 2), ("км", 1),
        ("метр", 1), ("кг", 2), ("литр", 2), ("грамм", 2), ("настай", 2),
        ("насны", 2), ("насан", 2), ("төгрөг", 2), ("төг", 1), ("ажилла", 2),
        ("дундаж", 1), ("хувиар", 2), ("хувийн", 2), ("бутархай", 1),
        ("гишүүн", 1), ("тэгшитгэлийг бод", 2), ("системийг бод", 2),
        ("адилтгал", 2), ("тэнцэтгэлийг батал", 2), ("зүй тогтол", 2),
    ],
    "COM": [
        ("янзаар", 4), ("сэлгэмэл", 3), ("магадлал", 3), ("санамсаргүй", 2),
        ("хүснэгт", 3), ("нүд", 2), ("шатар", 3), ("тоглогч", 3),
        ("тоглоом", 3), ("тоглолт", 2), ("олонлог", 2), ("дэд олонлог", 2),
        ("өнгө", 2), ("будаж", 2), ("будсан", 2), ("будна", 2),
        ("хайрцаг", 2), ("зоос", 3), ("карт", 2), ("граф", 3), ("ирмэг", 2),
        ("зам", 1), ("сурагч", 1), ("найз", 1), ("тэмцээн", 1), ("үсэг", 2),
        ("суудал", 2), ("пермутац", 3), ("комбинац", 3), ("комбинаторик", 3),
        ("байрлуул", 1), ("хэдэн арга", 2), ("хуваарил", 1),
        ("боломж", 2), ("хувааж болох", 2), ("хэсэгт хуваа", 2),
        ("танил", 3), ("таньдаг", 3), ("найзууд", 1), ("хүүхэд", 1),
        ("хөлөг", 3), ("хөлгийн", 3), ("бэрс", 3), ("морь", 2), ("тэрэг", 1),
        ("палиндром", 3), ("арал", 2), ("гүүр", 2), ("хот", 1),
        ("хамгийн олондоо", 1), ("хамгийн цөөндөө", 1), ("ядаж", 1),
        ("олддог", 1), ("олдоно", 1), ("үг", 1), ("дүрс", 1), ("хөрш", 2),
        ("гар барил", 3), ("тэмдэглэ", 1), ("бүлэгт", 1), ("баг", 1),
    ],
    "GEO": [
        ("гурвалж", 3), ("өнцөг", 2), ("тойрог", 3), ("тойрг", 3),
        ("радиус", 2), ("диаметр", 3), ("хэрчим", 2), ("хэрчм", 2),
        ("перпендикуляр", 2), ("биссектрис", 3), ("медиан", 2), ("шүргэ", 2),
        ("диагонал", 2), ("трапец", 3), ("ромб", 3), ("параллелограм", 3),
        ("параллелграм", 3), ("квадрат", 1), ("тэгш өнцөгт", 2), ("талбай", 2),
        ("периметр", 2), ("пирамид", 3), ("цилиндр", 3), ("конус", 3),
        ("бөмбөрцөг", 3), ("тетраэдр", 3), ("параллелепипед", 3),
        ("вектор", 2), ("координат", 2), ("пифагор", 2), ("градус", 2),
        ("огтлолц", 1), ("огтолно", 1), ("хавтгай", 1), ("шулуун", 1),
        ("орой", 1), ("муруй", 1), ("куб", 1),
    ],
    "NUM": [
        ("анхны тоо", 3), ("харилцан анхны", 3), ("хуваагч", 3),
        ("хуваагд", 3), ("үлдэгдэл", 2), ("цифр", 3), ("оронтой", 2),
        ("бүтэн квадрат", 4), ("бүтэн куб", 4), ("зохиомол", 3),
        ("сондгой", 2), ("тэгш тоо", 2), ("бүхэл тоон шийд", 3),
        ("ерөнхий хуваагч", 3), ("модул", 2), ("конгруэнц", 3),
        ("факториал", 2), ("диофант", 3), ("евклид", 2), ("иррационал", 1),
        ("рационал тоо", 1),
        ("натурал тоон шийд", 3), ("натурал шийд", 3), ("бүхэл шийд", 3),
        ("бүхэл тоон", 1), ("хуваахад", 2), ("тэгээр төгс", 3),
        ("сүүлийн цифр", 2), ("сүүлийн хоёр орон", 3), ("сүүлийн 2 орон", 3),
        ("анхны", 1), ("зэрэгт", 1), ("хосыг ол", 1), ("ноогдвор", 2),
        ("ногдвор", 2), ("бүхэл байх", 2), ("бүхэл байдаг", 2),
    ],
}

# LaTeX тэмдэглэгээ (эх текстээс хайна).
MATH_SIGNALS = {
    "ALG": [(r"\\sqrt", 1), (r"\b[fgP]\s*\(\s*[xyz]", 2), (r"\\mathbb\s*\{?R", 2),
            (r"\\log", 2), (r"\\[gl]eq?(?![a-zA-Z])", 1),
            (r"\\(sin|cos|tg|ctg|tan|cot)(?![a-zA-Z])", 3), (r"\\?%", 2),
            (r"[a-z]_\{?n\s*\+\s*1", 2), (r"\\sum", 1)],
    "COM": [(r"\\binom", 2), (r"\\times\s*\d+\$?\s*хүснэгт", 2)],
    "GEO": [(r"\\angle", 3), (r"\^\s*\{?\\circ", 2), (r"\\triangle", 3),
            (r"\\perp", 2), (r"\\parallel", 2), (r"\\overrightarrow", 2),
            (r"\$[A-Z]{3,}\$", 1), (r"S_\{?[A-Z]{3}", 2)],
    "NUM": [(r"\\pmod", 3), (r"\\equiv", 2), (r"\\mid", 2), (r"\\gcd", 3),
            (r"\\lfloor", 1), (r"\\mathbb\s*\{?[NZ]", 1), (r"\d!", 1),
            (r"\\overline\{?[a-z]{2}", 3), (r"\^\{?\d{3,}", 1), (r"[a-z]!", 1)],
}

# Нэг ангилалд харьяалагдах мэт боловч өөр ангиллын нөхцөлд хэрэглэгддэг
# хэллэгүүд: таарвал тухайн ангиллаас оноо хасна.
PENALTIES = [
    ("GEO", r"(?<!\w)геометр прогресс", 3),       # алгебр
    ("GEO", r"(?<!\w)бүтэн квадрат", 1),          # тооны онол
    ("GEO", r"(?<!\w)бүтэн куб", 1),
    ("GEO", r"(?<!\w)квадрат(ын|уудын)? нийлбэр", 1),
    ("NUM", r"олон гишүүнт\w* хуваа", 3),         # олон гишүүнтийн үлдэгдэл
    ("ALG", r"(?<!\w)дундаж цэг", 1),              # геометр
    ("ALG", r"(натурал|бүхэл)( тоон)? шийд", 2),   # диофант тэгшитгэл
    ("COM", r"(?<!\w)хуваахад", 2),                # "хувааж болох" биш
]

CATEGORY_NAME = dict(Topic.Category.choices)

MIN_SCORE = 3      # үүнээс бага оноотой бол тодорхойгүй гэж үзнэ
MIN_MARGIN = 1.25  # эхний/хоёр дахь онооны харьцаа үүнээс бага бол эргэлзээтэй

PLACEHOLDER_RE = re.compile(r"^\s*бодлого\s*№?\s*\d*\s*$", re.IGNORECASE)


def _compile(entries, word_start=True):
    prefix = r"(?<!\w)" if word_start else ""
    return [(re.compile(prefix + p), w) for p, w in entries]


_LEX = {c: _compile([(re.escape(s), w) for s, w in e]) for c, e in LEXICON.items()}
_MATH = {c: _compile(e, word_start=False) for c, e in MATH_SIGNALS.items()}
_PEN = [(c, re.compile(p), w) for c, p, w in PENALTIES]


def normalize_text(s: str) -> str:
    if not s:
        return ""
    s = re.sub(r"<[^>]+>", " ", s)                     # HTML
    s = re.sub(r"\$\$.*?\$\$|\\\[.*?\\\]", " ", s, flags=re.S)
    s = re.sub(r"\$.*?\$", " ", s, flags=re.S)         # inline math
    s = re.sub(r"\\[a-zA-Z]+\*?", " ", s)              # LaTeX команд
    s = re.sub(r"\\-", "", s)                          # hyphenation
    return re.sub(r"\s+", " ", s).lower()


def score_statement(statement: str) -> dict:
    raw = statement or ""
    text = normalize_text(raw)
    scores = {c: 0 for c in LEXICON}
    for cat, pats in _LEX.items():
        scores[cat] += sum(w for rx, w in pats if rx.search(text))
    for cat, pats in _MATH.items():
        scores[cat] += sum(w for rx, w in pats if rx.search(raw))
    for cat, rx, w in _PEN:
        if rx.search(text):
            scores[cat] -= w
    return scores


def classify_statement(statement: str):
    """(ангилал эсвэл None, итгэл: 'high' | 'low' | None, оноо) буцаана."""
    if not statement or PLACEHOLDER_RE.match(normalize_text(statement)):
        return None, None, {}
    scores = score_statement(statement)
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    (best, top), (_, second) = ranked[0], ranked[1]
    if top < MIN_SCORE:
        return None, None, scores
    confident = second <= 0 or top / second >= MIN_MARGIN
    return best, ("high" if confident else "low"), scores


class Command(BaseCommand):
    help = "Олимпиадын бодлогын statement-г түлхүүр үгэнд суурилж ангилах"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true",
                            help="Өөрчлөлт хадгалахгүй, зөвхөн тайлан гаргах")
        parser.add_argument("--overwrite", action="store_true",
                            help="Өмнө нь ангилал оноосон бодлогын ангиллыг дарж бичих")
        parser.add_argument("--include-low", action="store_true",
                            help="Эргэлзээтэй (оноо ойролцоо) ангиллыг бас хадгалах")
        parser.add_argument("--olympiad", type=int, help="Зөвхөн энэ олимпиадын бодлогууд")
        parser.add_argument("--report", help="Үр дүнг CSV файлд бичих")
        parser.add_argument("-v2", "--verbose-list", action="store_true",
                            help="Бодлого бүрийн үр дүнг хэвлэх")

    def handle(self, *args, **opts):
        qs = Problem.objects.prefetch_related("topics").order_by("id")
        if opts["olympiad"]:
            qs = qs.filter(olympiad_id=opts["olympiad"])

        topics = {}
        stats = {"assigned": 0, "kept": 0, "low": 0, "unknown": 0, "changed": 0}
        per_cat = {c: 0 for c in LEXICON}
        rows = []

        with transaction.atomic():
            for p in qs:
                cat, conf, scores = classify_statement(p.statement)
                current = sorted(t.category for t in p.topics.all())
                action = ""
                if cat is None:
                    stats["unknown"] += 1
                    action = "unknown"
                elif conf == "low" and not opts["include_low"]:
                    stats["low"] += 1
                    action = "low-skip"
                elif current and (not opts["overwrite"] or cat in current):
                    # таамаг одоогийн ангилалд багтаж байвал (олон ангилалтайг
                    # оролцуулан) гараар оноосныг хадгална
                    stats["kept"] += 1
                    action = "kept"
                else:
                    per_cat[cat] += 1
                    stats["assigned"] += 1
                    if current and current != [cat]:
                        stats["changed"] += 1
                    action = "assign"
                    if not opts["dry_run"]:
                        if cat not in topics:
                            topics[cat] = self._topic(cat)
                        p.topics.set([topics[cat]])

                rows.append([p.id, p.olympiad_id, "|".join(current), cat or "",
                             conf or "", action,
                             " ".join(f"{k}={v}" for k, v in scores.items()),
                             " ".join((p.statement or "").split())[:200]])
                if opts["verbose_list"]:
                    self.stdout.write(f"#{p.id}: {'|'.join(current) or '-'} → "
                                      f"{cat or '?'} ({conf or '-'}) [{action}]")

        if opts["report"]:
            with open(opts["report"], "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["id", "olympiad", "current", "predicted", "confidence",
                            "action", "scores", "statement"])
                w.writerows(rows)

        prefix = "[DRY] " if opts["dry_run"] else ""
        self.stdout.write(self.style.SUCCESS(
            f"{prefix}Ангилал оноосон: {stats['assigned']} "
            f"({', '.join(f'{CATEGORY_NAME[c]} {n}' for c, n in per_cat.items())}); "
            f"үүнээс өөрчлөгдсөн: {stats['changed']}; "
            f"хуучин ангиллаа хадгалсан: {stats['kept']}; "
            f"эргэлзээтэй: {stats['low']}; тодорхойгүй: {stats['unknown']}."
        ))

    @staticmethod
    def _topic(category):
        topic = Topic.objects.filter(category=category, name=CATEGORY_NAME[category]).first()
        return topic or Topic.objects.create(category=category, name=CATEGORY_NAME[category])
