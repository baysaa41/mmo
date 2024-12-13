from django.contrib import admin

# Register your models here.

from .models import Olympiad, SchoolYear, Topic, Problem, AnswerChoice, Award, Result, Solution, Team, Upload, Article, Tag

admin.site.register(SchoolYear)
admin.site.register(Topic)
admin.site.register(AnswerChoice)
admin.site.register(Award)
admin.site.register(Result)
admin.site.register(Team)
admin.site.register(Upload)
admin.site.register(Tag)

class ArticleAdmin(admin.ModelAdmin):
    list_display = ("title","year")
    list_filter = ("year",)
    raw_id_fields = ("author",)
    exclude = ("oldid", "intro", "imagesource", "embedcode", "pictures", "files", "tags", "sawcount", "createuserid", "author")
    search_fields = ["title", "descr"]

    def get_queryset(self, request):
        return Article.objects.all().order_by("year_id","-id")

admin.site.register(Article,ArticleAdmin)

class OlympiadAdmin(admin.ModelAdmin):
    list_display = ("name", "school_year", "level", "description")
    list_filter = ("level","school_year")
    search_fields = ["name", "description"]

    def get_queryset(self, request):
        return Olympiad.objects.all().order_by("school_year","-level","-is_open")

admin.site.register(Olympiad,OlympiadAdmin)


class ProblemAdmin(admin.ModelAdmin):
    list_display = ("olympiad", "order", "statement")
    list_filter = ("olympiad__school_year",)
    search_fields = ["olympiad", "statement"]

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        queryset = queryset.order_by("olympiad__school_year","-olympiad__is_open","-olympiad","order")
        return queryset

admin.site.register(Problem,ProblemAdmin)

class SolutionAdmin(admin.ModelAdmin):
    list_display = ("problem","content")
    list_filter = ("problem__olympiad__school_year",)
    search_fields = ["problem__olympiad", "content"]

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        queryset = queryset.order_by("problem__olympiad__school_year","-problem__olympiad__is_open","-problem__olympiad","problem__order")
        return queryset

admin.site.register(Solution,SolutionAdmin)