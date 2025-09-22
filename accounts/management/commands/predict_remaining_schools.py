from django.core.management.base import BaseCommand
from accounts.models import UserMeta
from accounts.school_utils import guess_school   # шинэчлэгдсэн guess_school-г импортолно
from django.db.models import Q


class Command(BaseCommand):
    help = ("Сурагчийн оруулсан province_id ба school нэрийн дагуу "
            "guess_school() функцыг ашиглаж UserMeta.address1-д сургуулийн ID, "
            "address2-д сургуулийн нэрийг автоматаар бичнэ.")

    def handle(self, *args, **options):
        updated_count = 0
        skipped_count = 0

        # school талбар хоосон биш, address1 хоосон сурагчдыг сонгоно


        qs=UserMeta.objects.filter(
            user_school_name__isnull=False,
            school__isnull=True,
        ).filter(
            Q(address1__isnull=True) | Q(address1='')
        )

        for um in qs.iterator():
            school = guess_school(um)
            if school:
                um.address1 = '-' + str(school.province.id) + ', ' + str(school.id)
                um.address2 = '-' + school.name
                um.save(update_fields=['address1', 'address2'])
                updated_count += 1
            else:
                um.address1 = '-skipped'
                um.save(update_fields=['address1'])
                skipped_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Нийт {updated_count} сурагчийн address1/2 талбарыг шинэчилж, "
                f"{skipped_count} сурагчийг таамаглаж чадсангүй."
            )
        )

