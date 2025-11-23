"""
cheating_analysis_pro.py

Professional cheating analysis module — upgraded from the user's original
cheating_analysis.py (see source). Implements:
  - Infer item correct answers (mode) when explicit answers missing
  - Compute item difficulty (p-value) and weights
  - Weighted Wrong-Match (WWM) and Weighted Correct-Match (WCM)
  - Omega index (standardized statistic)
  - Composite Cheating Index (CI) combining omega, WWM, WCM
  - Memory-aware school/olympiad analysis functions
  - Updated print_cheating_matrix

Notes:
  - This file expects pandas/numpy and Django models available when used
  - When possible, pass `correct_answers` dict into analyze_school_pro to
    use authoritative keys; otherwise the code will infer correct answers
    from the sample (mode).

"""

import math
import numpy as np
import pandas as pd
from itertools import combinations
from sklearn.cluster import AgglomerativeClustering
from django.core.cache import cache

# ------------------------------
# Helpers: infer correct answers, compute difficulty
# ------------------------------

def infer_correct_answers(students_df):
    """Infer the most-likely correct answer for each question using mode.

    Args:
        students_df: DataFrame with questions as columns (answers as values)

    Returns:
        dict mapping question -> inferred_correct_answer
    """
    correct = {}
    for q in students_df.columns:
        # Dropna then take mode; if no mode, use first non-null
        s = students_df[q].dropna()
        if s.empty:
            correct[q] = None
            continue
        modes = s.mode()
        if not modes.empty:
            correct[q] = modes.iloc[0]
        else:
            correct[q] = s.iloc[0]
    return correct


def compute_item_difficulty_and_weights(students_df, correct_answers=None):
    """Compute p-values and weights for each question.

    If correct_answers is None, infer using modes.

    Returns:
        p: dict question->p-value (fraction correct)
        w: dict question->weight (1 - p)
        correct_answers: dict filled used for computation
    """
    if correct_answers is None:
        correct_answers = infer_correct_answers(students_df)

    n = len(students_df)
    p = {}
    w = {}
    for q in students_df.columns:
        if correct_answers.get(q) is None:
            p[q] = 0.0
            w[q] = 1.0
            continue
        correct_count = (students_df[q] == correct_answers[q]).sum()
        p[q] = float(correct_count) / max(n, 1)
        w[q] = 1.0 - p[q]
    return p, w, correct_answers


# ------------------------------
# Core pairwise statistics
# ------------------------------

def weighted_wrong_match(a: dict, b: dict, questions, correct, w):
    """Weighted count of items where both answered the same wrong answer.

    Returns non-normalized sum of weights.
    """
    score = 0.0
    for q in questions:
        ca = a.get(q)
        cb = b.get(q)
        if pd.isna(ca) or pd.isna(cb):
            continue
        if ca == cb and correct.get(q) is not None and ca != correct[q]:
            score += w[q]
    return score


def weighted_correct_match(a: dict, b: dict, questions, correct, p):
    """Weighted count of items where both answered the (inferred) correct answer.

    Uses p (difficulty) as weight for normalization rationale (easy items
    contribute less to suspicion).
    """
    score = 0.0
    for q in questions:
        ca = a.get(q)
        cb = b.get(q)
        if pd.isna(ca) or pd.isna(cb):
            continue
        if ca == cb and correct.get(q) is not None and ca == correct[q]:
            # Using p[q] (fraction correct) means easy items (high p)
            # produce larger p but later we'll normalize so their
            # relative impact can be downweighted.
            score += p[q]
    return score


def omega_index(a: dict, b: dict, questions, correct, p):
    """Compute a standardized omega statistic for wrong matches.

    WM observed is count of wrong matches (unweighted). E[WM] and Var(WM)
    derived from p-values: for each item q, probability both are wrong
    is (1-p[q])**2. E = sum prob, Var = sum prob*(1-prob).

    Returns standardized omega (float). If variance is zero returns 0.
    """
    WM = 0
    probs = []
    for q in questions:
        ca = a.get(q)
        cb = b.get(q)
        if pd.isna(ca) or pd.isna(cb):
            probs.append(0.0)
            continue
        if ca == cb and correct.get(q) is not None and ca != correct[q]:
            WM += 1
        probs.append((1.0 - p[q]) ** 2)

    E = sum(probs)
    Var = sum(px * (1 - px) for px in probs)
    if Var <= 0:
        return 0.0
    return (WM - E) / math.sqrt(Var)


def cheating_index_pro(a: dict, b: dict, questions, correct, p, w):
    """Composite cheating index combining omega, WWM and WCM.

    Normalizes components and returns CI in [0, 1].
    """
    # Raw components
    wwm = weighted_wrong_match(a, b, questions, correct, w)
    wcm = weighted_correct_match(a, b, questions, correct, p)
    omg = omega_index(a, b, questions, correct, p)

    # Normalization baselines
    max_wwm = sum(w[q] for q in questions) or 1.0
    max_wcm = sum(p[q] for q in questions) or 1.0

    wwm_norm = wwm / max_wwm
    wcm_norm = wcm / max_wcm

    # omega scaled via sigmoid to map (-inf,inf) -> (0,1)
    omg_norm = 1.0 / (1.0 + math.exp(-omg))

    # Combine: heavier weight to wrong-match & omega
    ci = 0.4 * omg_norm + 0.4 * wwm_norm + 0.2 * wcm_norm
    # Ensure numeric stability
    return float(min(max(ci, 0.0), 1.0))


# ------------------------------
# School-level analysis (memory-aware)
# ------------------------------

def analyze_school_pro(students_df, questions=None, correct_answers=None, min_students=5):
    """Analyze a single school's students and return metrics.

    Args:
        students_df: DataFrame indexed by contestant_id, columns are question names
        questions: optional ordered list of question column names; if None, use df.columns
        correct_answers: optional dict question->correct answer; if None, infer via mode
        min_students: minimum students to run analysis
    Returns:
        dict with CPS, HRP, IntegrityScore, ClusterCount, PairCount
    """
    if questions is None:
        questions = list(students_df.columns)

    n = len(students_df)
    if n < min_students:
        return None

    # Ensure questions are present
    students_df = students_df[questions]

    # compute difficulties and (possibly infer) correct answers
    p, w, correct = compute_item_difficulty_and_weights(students_df, correct_answers)

    # Convert to dicts for faster row access
    students = students_df.to_dict('index')
    ids = list(students.keys())

    CI_values = []
    # pairwise loop
    for i_idx in range(len(ids)):
        for j_idx in range(i_idx + 1, len(ids)):
            a = students[ids[i_idx]]
            b = students[ids[j_idx]]
            ci = cheating_index_pro(a, b, questions, correct, p, w)
            CI_values.append(ci)

    CI_values = np.array(CI_values) if CI_values else np.array([0.0])

    CPS = float(np.mean(CI_values))
    HRP = float(np.mean(CI_values > 0.85))  # threshold for high-risk pair
    Integrity = float(1.0 - CPS)

    # Calculate average component scores for the school
    omega_vals = []
    wwm_vals = []
    wcm_vals = []

    for i_idx in range(len(ids)):
        for j_idx in range(i_idx + 1, len(ids)):
            a = students[ids[i_idx]]
            b = students[ids[j_idx]]

            # Raw components
            wwm = weighted_wrong_match(a, b, questions, correct, w)
            wcm = weighted_correct_match(a, b, questions, correct, p)
            omg = omega_index(a, b, questions, correct, p)

            # Normalize
            max_wwm = sum(w[q] for q in questions) or 1.0
            max_wcm = sum(p[q] for q in questions) or 1.0

            wwm_norm = wwm / max_wwm
            wcm_norm = wcm / max_wcm
            omg_norm = 1.0 / (1.0 + math.exp(-omg))

            omega_vals.append(omg_norm)
            wwm_vals.append(wwm_norm)
            wcm_vals.append(wcm_norm)

    avg_omega = float(np.mean(omega_vals)) if omega_vals else 0.0
    avg_wwm = float(np.mean(wwm_vals)) if wwm_vals else 0.0
    avg_wcm = float(np.mean(wcm_vals)) if wcm_vals else 0.0

    # Build CI matrix for clustering (small n ok)
    n_ids = len(ids)
    CI_matrix = np.eye(n_ids)
    for i in range(n_ids):
        for j in range(i + 1, n_ids):
            a = students[ids[i]]
            b = students[ids[j]]
            v = cheating_index_pro(a, b, questions, correct, p, w)
            CI_matrix[i, j] = v
            CI_matrix[j, i] = v

    # Cluster: convert to distance
    dist = 1.0 - CI_matrix
    cluster_count = 0
    try:
        # enforce minimum cluster size by post-filtering labels
        clustering = AgglomerativeClustering(
            n_clusters=None,
            distance_threshold=0.5,
            metric="precomputed",
            linkage="average"
        ).fit(dist)
        labels = clustering.labels_
        # remove small clusters
        unique, counts = np.unique(labels, return_counts=True)
        valid_clusters = sum(1 for c in counts if c >= 3)
        cluster_count = int(valid_clusters)
    except Exception:
        cluster_count = 0

    return {
        'CPS': round(CPS, 4),
        'HRP': round(HRP, 4),
        'ClusterCount': cluster_count,
        'IntegrityScore': round(Integrity, 4),
        'PairCount': int(len(CI_values)),
        'Omega': round(avg_omega, 4),
        'WWM': round(avg_wwm, 4),
        'WCM': round(avg_wcm, 4)
    }


# ------------------------------
# Olympiad-level functions (Django integration)
# ------------------------------

def analyze_olympiad_cheating(olympiad_id, top_n=10):
    """Analyzes top N students from each school for an olympiad.

    Uses database queries to construct per-school pivot tables and calls
    analyze_school_pro on each.

    Args:
        olympiad_id: Olympiad ID
        top_n: Number of top students to analyze per school (default: 10)
    """
    from olympiad.models import Result, ScoreSheet
    from schools.models import School

    # Get unique schools with province info
    schools_data = Result.objects.filter(
        olympiad_id=olympiad_id,
        contestant__data__school__isnull=False
    ).values(
        'contestant__data__school_id',
        'contestant__data__school__name',
        'contestant__data__school__province_id',
        'contestant__data__school__province__name'
    ).distinct()

    if not schools_data:
        return pd.DataFrame()

    results_list = []

    for school in schools_data:
        school_id = school['contestant__data__school_id']
        school_name = school['contestant__data__school__name']
        province_id = school['contestant__data__school__province_id'] or 0
        province_name = school['contestant__data__school__province__name'] or 'Тодорхойгүй'

        # Get top N students by score
        top_students = ScoreSheet.objects.filter(
            olympiad_id=olympiad_id,
            school_id=school_id
        ).order_by('-total').values_list('user_id', flat=True)[:top_n]

        top_student_ids = list(top_students)

        if len(top_student_ids) < 5:
            continue

        # Get results for top students only
        school_results = Result.objects.filter(
            olympiad_id=olympiad_id,
            contestant_id__in=top_student_ids
        ).values(
            'contestant_id',
            'problem__order',
            'answer'
        )

        if not school_results:
            continue

        # Convert to DataFrame
        df = pd.DataFrame(list(school_results))

        if df.empty or len(df['contestant_id'].unique()) < 5:
            continue

        # Pivot
        pivot_df = df.pivot_table(
            index='contestant_id',
            columns='problem__order',
            values='answer',
            aggfunc='first'
        )

        # Get questions
        questions = [f'Q{int(c):02d}' for c in pivot_df.columns]
        pivot_df.columns = questions

        # Analyze
        analysis = analyze_school_pro(pivot_df, questions=questions)

        if analysis:
            results_list.append({
                'school_id': int(school_id),
                'school_name': school_name,
                'province_id': int(province_id),
                'province_name': province_name,
                'student_count': len(pivot_df),
                **analysis
            })

    if not results_list:
        return pd.DataFrame()

    results_df = pd.DataFrame(results_list)
    results_df = results_df.sort_values('CPS', ascending=False)
    return results_df


def analyze_olympiad_cheating_cached(olympiad_id, refresh=False, cache_timeout=3600):
    cache_key = f'cheating_analysis_pro_{olympiad_id}'
    if not refresh:
        cached = cache.get(cache_key)
        if cached is not None:
            return cached
    df = analyze_olympiad_cheating(olympiad_id)
    records = df.to_dict('records') if not df.empty else []
    cache.set(cache_key, records, cache_timeout)
    return records


# ------------------------------
# Console matrix printer (updated)
# ------------------------------

def print_cheating_matrix(olympiad_id, school_id, top_n=10):
    from olympiad.models import Result, ScoreSheet

    top_students = ScoreSheet.objects.filter(
        olympiad_id=olympiad_id,
        school_id=school_id
    ).order_by('-total').values_list('user_id', flat=True)[:top_n]

    top_student_ids = list(top_students)
    if len(top_student_ids) < 2:
        print(f"Хангалттай сурагч олдсонгүй. Олдсон: {len(top_student_ids)}")
        return

    results = Result.objects.filter(
        olympiad_id=olympiad_id,
        contestant_id__in=top_student_ids
    ).values('contestant_id', 'problem__order', 'answer')

    if not results:
        print("Үр дүн олдсонгүй.")
        return

    df = pd.DataFrame(list(results))
    pivot_df = df.pivot_table(index='contestant_id', columns='problem__order', values='answer', aggfunc='first')
    questions = [f'Q{int(c):02d}' for c in pivot_df.columns]
    pivot_df.columns = questions

    students = pivot_df.to_dict('index')
    student_ids = list(students.keys())
    n = len(student_ids)

    CI_matrix = np.eye(n)
    # compute symmetric CI matrix
    for i in range(n):
        for j in range(i + 1, n):
            v = cheating_index_pro(students[student_ids[i]], students[student_ids[j]], questions,
                                    *compute_item_difficulty_and_weights(pivot_df))
            CI_matrix[i, j] = v
            CI_matrix[j, i] = v

    print(f"\n{'='*60}")
    print(f"Хуулалтын индекс матриц - Олимпиад: {olympiad_id}, Сургууль: {school_id}")
    print(f"Сурагчдын тоо: {n}")
    print(f"{'='*60}\n")

    header = "      " + "".join([f"{i+1:>6}" for i in range(n)])
    print(header)
    print("-" * len(header))

    for i in range(n):
        row = f"{i+1:>4} |"
        for j in range(n):
            if i == j:
                row += f"{'---':>6}"
            else:
                row += f"{CI_matrix[i, j]:>6.2f}"
        print(row)

    print(f"\n{'='*60}")
    print("Сурагчдын ID жагсаалт:")
    for i, sid in enumerate(student_ids):
        print(f"  {i+1}: {sid}")
    print(f"{'='*60}\n")
