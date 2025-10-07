# ========================================
# olympiad/views_api.py (шинээр үүсгэх)
# ========================================

from django.http import JsonResponse
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
import json
from django.db import transaction

from .models import Result, Olympiad

@method_decorator(csrf_exempt, name='dispatch')
class SaveAnswerAPIView(LoginRequiredMixin, View):
    """Нэг хариултыг auto-save хийх API"""

    def post(self, request):
        try:
            # JSON data уншиж авах
            data = json.loads(request.body)
            result_id = data.get('result_id')
            answer = data.get('answer', '').strip()

            # Result авах - зөвхөн хэрэглэгчийнхийг
            try:
                result = Result.objects.select_related('olympiad').get(
                    pk=result_id,
                    contestant=request.user
                )
            except Result.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'message': 'Хариулт олдсонгүй'
                }, status=404)

            # Олимпиад хаагдсан эсэхийг шалгах
            if result.olympiad.is_closed():
                return JsonResponse({
                    'success': False,
                    'message': 'Хугацаа дууссан'
                }, status=403)

            # Хариултыг хадгалах
            if answer:
                try:
                    result.answer = int(answer)
                except ValueError:
                    return JsonResponse({
                        'success': False,
                        'message': 'Зөвхөн тоо оруулна уу'
                    }, status=400)
            else:
                result.answer = None

            # Зөвхөн answer талбарыг update хийх (хурдан)
            result.save(update_fields=['answer'])

            return JsonResponse({
                'success': True,
                'message': 'Амжилттай хадгалагдлаа'
            })

        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'message': 'Буруу өгөгдөл'
            }, status=400)

        except Exception as e:
            # Production-д log хийх
            print(f"Error in SaveAnswerAPIView: {e}")
            return JsonResponse({
                'success': False,
                'message': 'Алдаа гарлаа'
            }, status=500)

# ========================================
# БОНУС: Bulk save endpoint (нөөцөлж)
# ========================================

class BulkSaveAnswersAPIView(LoginRequiredMixin, View):
    """Олон хариултыг нэг дор хадгалах (нөөц)"""

    def post(self, request):
        try:
            data = json.loads(request.body)
            answers = data.get('answers', [])
            # Format: [{'result_id': 1, 'answer': 42}, ...]

            if not answers:
                return JsonResponse({
                    'success': False,
                    'message': 'Хоосон өгөгдөл'
                }, status=400)

            # Result ID-уудыг цуглуулах
            result_ids = [a['result_id'] for a in answers]

            # Хэрэглэгчийн result-үүдийг авах
            results = Result.objects.filter(
                pk__in=result_ids,
                contestant=request.user
            )

            # Dictionary болгох (хурдан хандалт)
            results_dict = {r.id: r for r in results}

            # Update хийх
            updated_count = 0
            for answer_data in answers:
                result_id = answer_data['result_id']
                answer_value = answer_data.get('answer', '').strip()

                if result_id in results_dict:
                    result = results_dict[result_id]

                    if answer_value:
                        try:
                            result.answer = int(answer_value)
                            updated_count += 1
                        except ValueError:
                            continue
                    else:
                        result.answer = None

            # Bulk update (1 query)
            if updated_count > 0:
                Result.objects.bulk_update(
                    list(results_dict.values()),
                    ['answer']
                )

            return JsonResponse({
                'success': True,
                'message': f'{updated_count} хариулт хадгалагдлаа'
            })

        except Exception as e:
            print(f"Error in BulkSaveAnswersAPIView: {e}")
            return JsonResponse({
                'success': False,
                'message': 'Алдаа гарлаа'
            }, status=500)