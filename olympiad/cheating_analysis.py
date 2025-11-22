import pandas as pd
import numpy as np
from itertools import combinations
from sklearn.cluster import AgglomerativeClustering

# ------------------------------
# CHEATING INDEX FUNCTIONS
# ------------------------------

def wrong_answer_match(a, b, questions):
    """Буруу хариултын таарал"""
    count = 0
    total_wrong = 0
    for q in questions:
        ca, cb = a.get(q), b.get(q)
        if pd.isna(ca) or pd.isna(cb):
            continue
        # Хоёулаа буруу эсвэл аль нэг нь буруу
        total_wrong += 1
        if ca == cb:
            count += 1
    return count / total_wrong if total_wrong else 0


def exact_match(a, b, questions):
    """Яг ижил хариултын хувь"""
    count = 0
    total = 0
    for q in questions:
        ca, cb = a.get(q), b.get(q)
        if pd.isna(ca) or pd.isna(cb):
            continue
        total += 1
        if ca == cb:
            count += 1
    return count / total if total else 0


def cheating_index(a, b, questions):
    """
    Хуулалтын индекс тооцоолох
    - wrong_answer_match: 70%
    - exact_match: 30%
    """
    return (
        0.7 * wrong_answer_match(a, b, questions) +
        0.3 * exact_match(a, b, questions)
    )


def analyze_school(students_df, questions, min_students=5):
    """
    Нэг сургуулийн сурагчдын хуулалтын шинжилгээ хийх

    Args:
        students_df: DataFrame with contestant_id as index, questions as columns
        questions: List of question column names
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
        ci = cheating_index(students[id_i], students[id_j], questions)
        CI_values.append(ci)

    CI_values = np.array(CI_values)

    # METRICS
    CPS = np.mean(CI_values)  # Cheating Prevalence Score
    HRP = np.mean(CI_values > 0.75)  # High-risk pair ratio
    Integrity = 1 - CPS

    # Copy Clusters
    CI_matrix = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            if i != j:
                id_i, id_j = student_ids[i], student_ids[j]
                CI_matrix[i][j] = cheating_index(students[id_i], students[id_j], questions)

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
