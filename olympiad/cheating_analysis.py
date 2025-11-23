import pandas as pd
import numpy as np
from itertools import combinations
from sklearn.cluster import AgglomerativeClustering
from django.core.cache import cache

# ------------------------------
# CHEATING INDEX FUNCTIONS
# ------------------------------

def wrong_answer_match(a, b, questions, correct_answers):
    """Буруу хариултын таарал - хоёулаа ижил буруу хариулт өгсөн"""
    count = 0
    total = 0
    for q in questions:
        ca, cb = a.get(q), b.get(q)
        correct = correct_answers.get(q)
        if pd.isna(ca) or pd.isna(cb) or correct is None:
            continue
        total += 1
        # Хоёулаа ижил буруу хариулт өгсөн эсэх
        if ca == cb and ca != correct:
            count += 1
    return count / total if total else 0


def correct_answer_match(a, b, questions, correct_answers):
    """Зөв хариултын таарал - хоёулаа зөв хариулт өгсөн"""
    count = 0
    total = 0
    for q in questions:
        ca, cb = a.get(q), b.get(q)
        correct = correct_answers.get(q)
        if pd.isna(ca) or pd.isna(cb) or correct is None:
            continue
        total += 1
        # Хоёулаа зөв хариулт өгсөн эсэх
        if ca == cb and ca == correct:
            count += 1
    return count / total if total else 0


def cheating_index(a, b, questions, correct_answers):
    """
    Хуулалтын индекс тооцоолох
    - Зөв хариулт ижил: 0.2
    - Буруу хариулт ижил: 0.8
    """
    return (
        0.65 * correct_answer_match(a, b, questions, correct_answers) +
        1 * wrong_answer_match(a, b, questions, correct_answers)
    )


def has_matching_wrong_answer(a, b, questions):
    """
    Дор хаяж нэг буруу хариулт ижил байгаа эсэхийг шалгах
    """
    for q in questions:
        ca, cb = a.get(q), b.get(q)
        if pd.isna(ca) or pd.isna(cb):
            continue
        # Хоёулаа ижил буруу хариулттай эсэх
        if ca == cb:
            return True
    return False


def analyze_school(students_df, questions, correct_answers, min_students=5):
    """
    Нэг сургуулийн сурагчдын хуулалтын шинжилгээ хийх

    Args:
        students_df: DataFrame with contestant_id as index, questions as columns
        questions: List of question column names
        correct_answers: Dict mapping question name to correct answer
        min_students: Хамгийн багадаа хэдэн сурагчтай байх (default: 5)

    Returns:
        dict with CPS, HRP, IntegrityScore, ClusterCount
    """
    n = len(students_df)

    if n < min_students:
        return None

    # Convert to list of dicts for easier access
    students = students_df.to_dict('index')
    student_ids = list(students.keys())

    CI_values = []

    # Pairwise CI for the school
    for i, j in combinations(range(n), 2):
        id_i, id_j = student_ids[i], student_ids[j]
        ci = cheating_index(students[id_i], students[id_j], questions, correct_answers)
        CI_values.append(ci)

    CI_values = np.array(CI_values)

    # METRICS
    CPS = np.mean(CI_values)  # Cheating Prevalence Score
    HRP = np.mean(CI_values > 0.7)  # High-risk pair ratio (CI > 0.7)
    Integrity = 1 - CPS

    # Copy Clusters
    CI_matrix = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            if i != j:
                id_i, id_j = student_ids[i], student_ids[j]
                CI_matrix[i][j] = cheating_index(students[id_i], students[id_j], questions, correct_answers)

    dist = 1 - CI_matrix
    try:
        clustering = AgglomerativeClustering(
            n_clusters=None,
            distance_threshold=0.5,
            metric="precomputed",
            linkage="average"
        ).fit(dist)
        cluster_count = len(set(clustering.labels_))
    except Exception:
        cluster_count = 0

    return {
        'CPS': round(CPS, 4),
        'HRP': round(HRP, 4),
        'ClusterCount': cluster_count,
        'IntegrityScore': round(Integrity, 4)
    }


def analyze_olympiad_cheating(olympiad_id):
    """
    Олимпиадын бүх сургуулиудын хуулалтын шинжилгээ хийх

    Args:
        olympiad_id: Olympiad ID

    Returns:
        DataFrame with school cheating analysis results
    """
    from olympiad.models import Result, Problem
    from schools.models import School

    # Get all results for this olympiad
    results = Result.objects.filter(
        olympiad_id=olympiad_id
    ).select_related(
        'contestant__data__school',
        'contestant__data__school__province',
        'problem'
    ).values(
        'contestant_id',
        'contestant__data__school_id',
        'contestant__data__school__name',
        'contestant__data__school__province_id',
        'contestant__data__school__province__name',
        'problem__order',
        'answer'
    )

    if not results:
        return pd.DataFrame()

    # Convert to DataFrame
    df = pd.DataFrame(list(results))
    df.columns = ['contestant_id', 'school_id', 'school_name', 'province_id', 'province_name', 'problem_order', 'answer']

    # Remove rows without school
    df = df[df['school_id'].notna()]

    if df.empty:
        return pd.DataFrame()

    # Get question columns
    questions = [f'Q{i:02d}' for i in sorted(df['problem_order'].unique())]

    # Pivot to get answers per student
    pivot_df = df.pivot_table(
        index=['school_id', 'school_name', 'province_id', 'province_name', 'contestant_id'],
        columns='problem_order',
        values='answer',
        aggfunc='first'
    ).reset_index()

    # Rename columns
    pivot_df.columns = ['school_id', 'school_name', 'province_id', 'province_name', 'contestant_id'] + [f'Q{int(c):02d}' for c in pivot_df.columns[5:]]

    results_list = []

    # Analyze each school
    for (school_id, school_name, province_id, province_name), group in pivot_df.groupby(['school_id', 'school_name', 'province_id', 'province_name']):
        students_df = group.set_index('contestant_id')[questions]

        analysis = analyze_school(students_df, questions)

        if analysis:
            results_list.append({
                'school_id': int(school_id),
                'school_name': school_name,
                'province_id': int(province_id) if pd.notna(province_id) else 0,
                'province_name': province_name if pd.notna(province_name) else 'Тодорхойгүй',
                'student_count': len(group),
                **analysis
            })

    if not results_list:
        return pd.DataFrame()

    results_df = pd.DataFrame(results_list)
    results_df = results_df.sort_values('CPS', ascending=False)

    return results_df


def analyze_olympiad_cheating_cached(olympiad_id, refresh=False, cache_timeout=3600):
    """
    Memory-friendly, cached version of cheating analysis.

    Args:
        olympiad_id: Olympiad ID
        refresh: Force refresh cache
        cache_timeout: Cache timeout in seconds (default: 1 hour)

    Returns:
        List of dicts with school cheating analysis results
    """
    cache_key = f'cheating_analysis_{olympiad_id}'

    # Check cache first
    if not refresh:
        cached_results = cache.get(cache_key)
        if cached_results is not None:
            return cached_results

    # Run analysis
    results_df = analyze_olympiad_cheating_memory_efficient(olympiad_id)

    # Convert to list and cache
    if not results_df.empty:
        results_data = results_df.to_dict('records')
    else:
        results_data = []

    cache.set(cache_key, results_data, cache_timeout)

    return results_data


def analyze_olympiad_cheating_memory_efficient(olympiad_id, top_n=10):
    """
    Memory-efficient version - processes schools one province at a time.
    Only analyzes top N students by score from each school.

    Args:
        olympiad_id: Olympiad ID
        top_n: Number of top students to analyze per school (default: 10)
    """
    from olympiad.models import Result, ScoreSheet, Problem
    from schools.models import School

    # Get correct answers from Problem model
    problems = Problem.objects.filter(
        olympiad_id=olympiad_id
    ).values('order', 'numerical_answer')

    correct_answers = {}
    for p in problems:
        q_name = f'Q{int(p["order"]):02d}'
        correct_answers[q_name] = p['numerical_answer']

    # Get unique schools with province info (only official participation)
    schools_data = Result.objects.filter(
        olympiad_id=olympiad_id,
        contestant__data__school__isnull=False,
        contestant__data__school__is_official_participation=True
    ).values(
        'contestant__data__school_id',
        'contestant__data__school__name',
        'contestant__data__school__province_id',
        'contestant__data__school__province__name'
    ).distinct()

    if not schools_data:
        return pd.DataFrame()

    # Group schools by province for batch processing
    schools_by_province = {}
    for s in schools_data:
        province_id = s['contestant__data__school__province_id'] or 0
        if province_id not in schools_by_province:
            schools_by_province[province_id] = []
        schools_by_province[province_id].append({
            'school_id': s['contestant__data__school_id'],
            'school_name': s['contestant__data__school__name'],
            'province_id': province_id,
            'province_name': s['contestant__data__school__province__name'] or 'Тодорхойгүй'
        })

    results_list = []

    # Process one province at a time to reduce memory
    for province_id, schools in schools_by_province.items():
        for school_info in schools:
            school_id = school_info['school_id']

            # Get top N students by score from ScoreSheet
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
            analysis = analyze_school(pivot_df, questions, correct_answers)

            if analysis:
                results_list.append({
                    'school_id': school_id,
                    'school_name': school_info['school_name'],
                    'province_id': school_info['province_id'],
                    'province_name': school_info['province_name'],
                    'student_count': len(pivot_df),
                    **analysis
                })

            # Clear memory
            del df, pivot_df

    if not results_list:
        return pd.DataFrame()

    results_df = pd.DataFrame(results_list)
    results_df = results_df.sort_values('CPS', ascending=False)

    return results_df


def print_cheating_matrix(olympiad_id, school_id, top_n=10):
    """
    Сургуулийн топ N сурагчдын хуулалтын индексийн матрицыг консолд хэвлэх.

    Ашиглах:
        from olympiad.cheating_analysis import print_cheating_matrix
        print_cheating_matrix(olympiad_id=1, school_id=123)

    Args:
        olympiad_id: Olympiad ID
        school_id: School ID
        top_n: Хамгийн өндөр оноотой хэдэн сурагч (default: 10)
    """
    from olympiad.models import Result, ScoreSheet

    # Get top N students by score
    top_students = ScoreSheet.objects.filter(
        olympiad_id=olympiad_id,
        school_id=school_id
    ).order_by('-total').values_list('user_id', flat=True)[:top_n]

    top_student_ids = list(top_students)

    if len(top_student_ids) < 2:
        print(f"Хангалттай сурагч олдсонгүй. Олдсон: {len(top_student_ids)}")
        return

    # Get results
    results = Result.objects.filter(
        olympiad_id=olympiad_id,
        contestant_id__in=top_student_ids
    ).values(
        'contestant_id',
        'problem__order',
        'answer'
    )

    if not results:
        print("Үр дүн олдсонгүй.")
        return

    # Convert to DataFrame and pivot
    df = pd.DataFrame(list(results))
    pivot_df = df.pivot_table(
        index='contestant_id',
        columns='problem__order',
        values='answer',
        aggfunc='first'
    )

    # Get questions
    questions = [f'Q{int(c):02d}' for c in pivot_df.columns]
    pivot_df.columns = questions

    # Convert to dict
    students = pivot_df.to_dict('index')
    student_ids = list(students.keys())
    n = len(student_ids)

    # Calculate CI matrix
    CI_matrix = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            if i == j:
                CI_matrix[i][j] = 1.0
            else:
                CI_matrix[i][j] = cheating_index(
                    students[student_ids[i]],
                    students[student_ids[j]],
                    questions
                )

    # Print matrix
    print(f"\n{'='*60}")
    print(f"Хуулалтын индекс матриц - Олимпиад: {olympiad_id}, Сургууль: {school_id}")
    print(f"Сурагчдын тоо: {n}")
    print(f"{'='*60}\n")

    # Header row with student numbers
    header = "      " + "".join([f"{i+1:>6}" for i in range(n)])
    print(header)
    print("-" * len(header))

    # Matrix rows
    for i in range(n):
        row = f"{i+1:>4} |"
        for j in range(n):
            if i == j:
                row += f"{'---':>6}"
            else:
                row += f"{CI_matrix[i][j]:>6.2f}"
        print(row)

    print(f"\n{'='*60}")
    print("Сурагчдын ID жагсаалт:")
    for i, sid in enumerate(student_ids):
        print(f"  {i+1}: {sid}")
    print(f"{'='*60}\n")
