# Нэмэлт эрх олгох - Богино заавар

## Хурдан эхлэх (5 минут)

### 1. Template үүсгэх
```bash
source /home/deploy/django/mmo/.venv/bin/activate
cd /home/deploy/django/mmo
python create_additional_quota_template.py
```

### 2. Excel бөглөх

**additional_quota.xlsx** файлыг нээж 2 хэсгийг бөглөнө:

**МЭДЭЭЛЭЛ хэсэг** - Ангилал бүрийн олимпиадын ID:
```
Ангилал | Олимпиадын ID
C       | 10
D       | 11
E       | 12
F       | 13
```

**АЙМГУУД хэсэг** - Аймаг бүрийн босго оноо:
```
ID | Нэр             | C | D | E | F
15 | Сүхбаатар аймаг | 4 | 3 | 5 |
16 | Сэлэнгэ аймаг   | 5 |   | 6 | 4
```

**Утга:**
- C ангилал = Олимпиад 10
- Сүхбаатар аймгийн C ангилалд ≥4 оноотой сурагчид нэмэлт эрх
- Хоосон нүд = нэмэлт эрх олгохгүй

### 3. Dry-run ажиллуулах
```bash
python manage.py first_to_second_by_ranking \
  --config-file additional_quota.xlsx \
  --dry-run
```

### 4. Зөв бол хадгалах
```bash
python manage.py first_to_second_by_ranking \
  --config-file additional_quota.xlsx
```

---

## Түгээмэл команд

### Өөр нэртэй template үүсгэх
```bash
python create_additional_quota_template.py -o quota_2024.xlsx
```

### Олимпиадын ID-тай template үүсгэх
```bash
python create_additional_quota_template.py --olympiad-ids "C:10,D:11,E:12,F:13"
```

### Тусламж харах
```bash
python manage.py first_to_second_by_ranking --help
```

---

## Үндсэн ойлголт

- **Ангилал → Олимпиад**: Олимпиад бүр нэг ангилалд харгалзана
- **Жагсаалтаас эрх**: Top 20 (аймаг) / Top 50 (дүүрэг) → "2.1 эрх жагсаалтаас"
- **Нэмэлт эрх**: Босго оноонд хүрсэн + жагсаалтаас эрх аваагүй → "2.1 эрх нэмэлтээр"
- **Хоосон нүд**: Тухайн аймаг/ангилалд нэмэлт эрх олгохгүй
- **0 оноо**: Автоматаар хасагдана
- **Олон олимпиад**: Нэг удаа олон олимпиад (C, D, E, F гэх мэт) боловсруулна

---

## Дэлгэрэнгүй

ADDITIONAL_QUOTA_GUIDE.md файлыг уншина уу.
