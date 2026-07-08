from django.contrib import admin

# Register your models here.

from .models import Olympiad, SchoolYear, Topic, Problem, AnswerChoice, Award, Result, Solution, Team, Upload, Tag

admin.site.register(SchoolYear)
admin.site.register(Topic)
admin.site.register(AnswerChoice)
admin.site.register(Team)
admin.site.register(Upload)
admin.site.register(Tag)


class AwardAdmin(admin.ModelAdmin):
    list_display = ("contestant", "olympiad", "grade", "place")
    list_select_related = ("contestant", "olympiad", "grade")
    autocomplete_fields = ['contestant', 'confirmed_by']

admin.site.register(Award, AwardAdmin)


class OlympiadAdmin(admin.ModelAdmin):
    list_display = ("name", "school_year", "level", "is_problems_confidential", "description")
    list_filter = ("level","school_year")
    list_select_related = ("school_year", "level")
    search_fields = ["name", "description"]

    def get_queryset(self, request):
        return Olympiad.objects.all().select_related("school_year", "level").order_by("school_year","-level","-is_open")

admin.site.register(Olympiad,OlympiadAdmin)


class ProblemAdmin(admin.ModelAdmin):
    list_display = ("olympiad", "order", "statement")
    list_filter = ("olympiad__school_year",)
    list_select_related = ("olympiad",)
    search_fields = ["olympiad", "statement"]

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        queryset = queryset.select_related("olympiad").order_by("olympiad__school_year","-olympiad__is_open","-olympiad","order")
        return queryset

admin.site.register(Problem,ProblemAdmin)

class SolutionAdmin(admin.ModelAdmin):
    list_display = ("problem", "author", "content")
    list_filter = ("problem__olympiad__school_year",)
    list_select_related = ("problem__olympiad__school_year", "author")
    search_fields = ["problem__olympiad", "content"]
    autocomplete_fields = ['author']

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        queryset = queryset.select_related("problem__olympiad__school_year", "author").order_by("problem__olympiad__school_year","-problem__olympiad__is_open","-problem__olympiad","problem__order")
        return queryset

admin.site.register(Solution,SolutionAdmin)


class ResultAdmin(admin.ModelAdmin):
    list_display = ("contestant", "olympiad", "problem", "score")
    list_select_related = ("contestant", "olympiad", "problem__olympiad__school_year")
    autocomplete_fields = ['contestant', 'coordinator', 'confirmed_by', 'olympiad', 'problem']

admin.site.register(Result, ResultAdmin)