from ..models import ScoreSheet
from .constants import OLYMPIADS, KWOTS, PROVINCES, DISTRICTS, ZONES


def set_ulsiin_erh():
    for kwot in kwots:
        olympiad_id, third_kwot, city_kwot_by_order, city_kwot_by_province, zone_kwot = kwot
        #ulsiin erh
        sheets_0 = ScoreSheet.objects.filter(olympiad_id=olympiad_id,
                                             user__data__province_id__in=provinces,
                                             ranking_b_p__lte=third_kwot,
                                             ranking_b_p__gte=1)
        sheets_0.update(prizes='Улсын эрх')


def set_hotiin_jagsaalt_erh():
    for kwot in kwots:
        olympiad_id, third_kwot, city_kwot_by_order, city_kwot_by_province, zone_kwot = kwot
        #hotiin jagsaalt
        sheets_1 = ScoreSheet.objects.filter(olympiad_id=olympiad_id,
                                             user__data__province_id__in=districts,
                                             ranking_b_z__lte=city_kwot_by_order,
                                             ranking_b_z__gte=1,
                                             prizes__isnull=True)
        sheets_1.update(prizes='Хотын эрх, жагсаалт')

#aimgaas bused
def set_busiin_erh():
    for kwot in kwots:
        olympiad_id, third_kwot, city_kwot_by_order, city_kwot_by_province, zone_kwot = kwot
        sheets_2 = ScoreSheet.objects.filter(olympiad_id=olympiad_id,
                                     user__data__province_id__lte=21,
                                     ranking_b_p__lte=zone_kwot,
                                     ranking_b_p__gte=1,
                                     prizes__isnull=True)
        sheets_2.update(prizes='Бүсийн эрх')

def clear_kwots():
    ScoreSheet.objects.filter(olympiad_id__in=olympiads).update(prizes=None)

def set_kwots():
    clear_kwots()
    set_ulsiin_erh()
    set_hotiin_jagsaalt_erh()
    set_busiin_erh()
    for province_id in districts:
        set_district_kwots(province_id)



def set_district_kwots(province_id):
    for kwot in kwots:
        olympiad_id, third_kwot, city_kwot_by_order, city_kwot_by_province, zone_kwot = kwot
        sheets = list(ScoreSheet.objects.filter(olympiad_id=olympiad_id,
                                           user__data__province_id=province_id,
                                           prizes__isnull=True).order_by('ranking_b_p'))
        last_total=0
        for index, sheet in enumerate(sheets):
            if index < city_kwot_by_province:
                sheet.prizes='Хотын эрх, дүүргээс'
                sheet.save()
                last_total = sheet.total

        remaining_sheets = ScoreSheet.objects.filter(olympiad_id=olympiad_id,
                                           user__data__province_id=province_id,
                                           total=last_total,
                                           prizes__isnull=True).exists()
        if remaining_sheets:
            print(province_id, olympiad_id, city_kwot_by_province, last_total)
            ScoreSheet.objects.filter(olympiad_id=olympiad_id,
                                           user__data__province_id=province_id,
                                           total=last_total).update(prizes=None)

def copy_ulsiin_erh():
    score_sheets = ScoreSheet.objects.filter(prizes__icontains="улс",olympiad_id__in=[170,171,173])
    for score_sheet in score_sheets:
        if score_sheet.olympiad_id == 170:
            ScoreSheet.objects.filter(olympiad_id=177,user_id=score_sheet.user_id).update(prizes='Улсын эрх, дүүргээс')
        elif score_sheet.olympiad_id == 171:
            ScoreSheet.objects.filter(olympiad_id=178,user_id=score_sheet.user_id).update(prizes='Улсын эрх, дүүргээс')
        elif score_sheet.olympiad_id == 173:
            ScoreSheet.objects.filter(olympiad_id=180,user_id=score_sheet.user_id).update(prizes='Улсын эрх, дүүргээс')