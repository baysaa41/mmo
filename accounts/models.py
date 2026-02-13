from django.db import models
from django.contrib.auth.models import User, Group
from django.utils import timezone
import os
from django.utils.text import slugify
import uuid
import datetime


def user_directory_path(instance, filename):
    # Get file extension
    ext = filename.split('.')[-1]

    # Sanitize filename and create new filename with username
    filename = f'{slugify(instance.user.username)}_{slugify(filename)}.{ext}'

    # Return the path relative to MEDIA_ROOT
    return os.path.join('user_uploads', instance.user.username, filename)


class Author(models.Model):
    user = models.OneToOneField(User, related_name='is_author', on_delete=models.CASCADE, primary_key=True)

    def __str__(self):
        return "{}, {}".format(self.user.first_name,self.user.last_name)

class UploadedFile(models.Model):
    file = models.FileField(upload_to='attachments/')  # Files will be saved in MEDIA_ROOT/uploads/
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE)  # To link the file to a user (optional)

    def __str__(self):
        return self.file.name

class UserMeta(models.Model):
    user = models.OneToOneField(User, related_name='data', on_delete=models.CASCADE, primary_key=True)
    photo = models.ImageField(upload_to=user_directory_path, blank=True)
    reg_num = models.CharField(max_length=12)
    province = models.ForeignKey("Province", on_delete=models.SET_NULL, null=True, blank=True)
    user_school_name = models.CharField(max_length=100, null=True, blank=True)
    school = models.ForeignKey("schools.School", on_delete=models.SET_NULL, null=True, blank=True)
    grade = models.ForeignKey("Grade", on_delete=models.SET_NULL, null=True, blank=True)
    level = models.ForeignKey("Level", on_delete=models.SET_NULL, null=True, blank=True)

    class Gender(models.TextChoices):
        MALE = 'Эр', 'Эрэгтэй'
        FEMALE = 'Эм', 'Эмэгтэй'

    gender = models.CharField(
        max_length=2,
        choices=Gender.choices,
        default='',
    )
    address1 = models.CharField(max_length=240, null=True, blank=True)
    address2 = models.CharField(max_length=240, null=True, blank=True)
    mobile = models.IntegerField(null=True)
    is_valid = models.BooleanField(default=False)

    class Meta:
        indexes = [
            # models.Index(fields=['school']),
            models.Index(fields=['reg_num']),
            models.Index(fields=['mobile']),
            # Add more indexes as needed
        ]

    def __str__(self):
        return '{}'.format(self.user.username)

    def save(self, *args, **kwargs):
        # --- ШИНЭЭР НЭМЭГДСЭН ЛОГИК ---
        # Хэрэв обьект шинээр үүсээгүй (засагдаж байгаа) бол хуучин сургуулийг шалгах
        if self.pk:
            try:
                # Мэдээллийн сангаас хуучин хувилбарыг авах
                old_meta = UserMeta.objects.get(pk=self.pk)
                old_school = old_meta.school
                new_school = self.school

                # Хэрэв сургууль солигдсон бөгөөд хуучин сургууль нь групптэй бол
                if old_school != new_school and old_school and old_school.group:
                    # Хэрэглэгчийг хуучин сургуулийн группээс хасах
                    old_school.group.user_set.remove(self.user)
            except UserMeta.DoesNotExist:
                pass # Шинэ обьект бол алгасах

        super().save(*args, **kwargs) # Үндсэн хадгалах үйлдлийг дуудах

class TeacherStudent(models.Model):
    teacher = models.ForeignKey(User, related_name='students', on_delete=models.CASCADE)
    student = models.ForeignKey(User, related_name='teachers', on_delete=models.CASCADE)
    date_started = models.DateField(auto_now=True)
    date_finished = models.DateField(null=True, blank=True)

    def __str__(self):
        return '{} - {}'.format(self.teacher.first_name, self.student.first_name)


class Province(models.Model):
    name = models.CharField(max_length=120, null=True)
    zone = models.ForeignKey('Zone', on_delete=models.SET_NULL, null=True)
    contact_person = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    class Meta:
        permissions = [
            ("edit_province", "Аймаг дүүргийн мэдээлэл оруулах")
        ]

    def __str__(self):
        return '{}'.format(self.name)


class Zone(models.Model):
    name = models.CharField(max_length=120, null=True)
    description = models.TextField()
    contact_person = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='managed_zones')
    olympiads = models.ManyToManyField('olympiad.Olympiad', blank=True, related_name='zones')

    class Meta:
        permissions = [
            ("edit_province", "Аймаг дүүргийн мэдээлэл оруулах")
        ]

    def __str__(self):
        return '{}'.format(self.name)

class Grade(models.Model):
    name = models.CharField(max_length=60)

    def __str__(self):
        return '{}'.format(self.name)


class Level(models.Model):
    name = models.CharField(max_length=60)

    def __str__(self):
        return '{}'.format(self.name)

class UserMails(models.Model):
    subject = models.CharField(max_length=256)
    text = models.TextField()
    text_html = models.TextField(default='')
    from_email = models.EmailField()
    to_email = models.EmailField()
    replyto_email = models.EmailField(default="baysa.edu@gmail.com")
    bcc = models.TextField(blank=True,null=True)
    is_sent = models.BooleanField(default=False)
    is_opened = models.BooleanField(default=False)  # New field to track if opened
    tracking_token = models.UUIDField(default=uuid.uuid4, unique=True)  # Unique tracking token

    def __str__(self):
        return f"Email to {self.to_email}"


class UserMergeRequest(models.Model):
    """
    Хэрэглэгчдийг нэгтгэх хүсэлт
    """
    # Request metadata
    requesting_user = models.ForeignKey(
        User,
        related_name='merge_requests_created',
        on_delete=models.CASCADE,
        verbose_name="Хүсэлт үүсгэсэн хэрэглэгч"
    )

    # Users to merge - stored as JSON array of user IDs
    user_ids = models.JSONField(
        verbose_name="Нэгтгэх хэрэглэгчдийн ID",
        help_text="JSON array: [101, 205, 308]"
    )

    # Primary user selection (will be kept after merge)
    primary_user = models.ForeignKey(
        User,
        related_name='merge_requests_as_primary',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Үндсэн хэрэглэгч"
    )

    # Request reason/notes
    reason = models.TextField(
        blank=True,
        verbose_name="Шалтгаан/Тайлбар",
        help_text="Яагаад эдгээр хэрэглэгчдийг нэгтгэх шаардлагатай вэ?"
    )

    # Status tracking
    class Status(models.TextChoices):
        PENDING = 'pending', 'Хүлээгдэж буй'
        APPROVED = 'approved', 'Зөвшөөрсөн'
        REJECTED = 'rejected', 'Татгалзсан'
        COMPLETED = 'completed', 'Дууссан'
        FAILED = 'failed', 'Амжилтгүй'

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name="Төлөв"
    )

    # Conflict detection
    has_conflicts = models.BooleanField(
        default=False,
        verbose_name="Зөрчил байгаа эсэх"
    )

    conflicts_data = models.JSONField(
        null=True,
        blank=True,
        verbose_name="Зөрчлийн дэлгэрэнгүй",
        help_text="Дүнгийн давхцал, өгөгдлийн зөрчил зэрэг"
    )

    # Review information
    reviewed_by = models.ForeignKey(
        User,
        related_name='merge_requests_reviewed',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Хянасан хэрэглэгч"
    )

    reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Хянасан огноо"
    )

    review_notes = models.TextField(
        blank=True,
        verbose_name="Хянасан тэмдэглэл"
    )

    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Үүсгэсэн огноо"
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Шинэчилсэн огноо"
    )

    # Merge result information
    merge_error = models.TextField(
        blank=True,
        verbose_name="Нэгтгэх алдаа"
    )

    # User confirmation tracking
    confirmations = models.JSONField(
        default=dict,
        verbose_name="Хэрэглэгчдийн баталгаажуулалт",
        help_text="Format: {user_id: {status: 'pending/confirmed/rejected', token: 'uuid', confirmed_at: timestamp}}"
    )

    requires_user_confirmation = models.BooleanField(
        default=True,
        verbose_name="Хэрэглэгчдээс баталгаажуулалт шаардах эсэх"
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Хэрэглэгч нэгтгэх хүсэлт"
        verbose_name_plural = "Хэрэглэгч нэгтгэх хүсэлтүүд"
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['requesting_user', 'status']),
        ]

    def __str__(self):
        return f"Нэгтгэх хүсэлт #{self.id} - {self.get_status_display()}"

    def get_users(self):
        """Нэгтгэх хэрэглэгчдийг буцаана"""
        return User.objects.filter(id__in=self.user_ids)

    def detect_conflicts(self):
        """
        Дүнгийн зөрчил илрүүлэх (automerge_users.py-с авсан логик)
        """
        users = self.get_users()
        if len(users) < 2:
            return []

        # Use first user as primary if not set
        primary_user = self.primary_user or users.first()
        duplicate_users = [u for u in users if u.id != primary_user.id]

        from olympiad.models import Result

        real_conflicts = []

        for dup_user in duplicate_users:
            results_to_check = Result.objects.filter(
                contestant=dup_user
            ).select_related('olympiad', 'problem')

            for dup_result in results_to_check:
                primary_result = Result.objects.filter(
                    contestant=primary_user,
                    olympiad=dup_result.olympiad,
                    problem=dup_result.problem
                ).first()

                if primary_result:
                    # Хариулт ЭСВЭЛ оноо өөр байвал л давхцал гэж үзнэ
                    if (primary_result.answer != dup_result.answer or
                        primary_result.score != dup_result.score):
                        real_conflicts.append({
                            'dup_user_id': dup_user.id,
                            'dup_user_name': f"{dup_user.last_name} {dup_user.first_name}",
                            'olympiad_id': dup_result.olympiad.id,
                            'olympiad_name': dup_result.olympiad.name,
                            'problem_order': dup_result.problem.order,
                            'primary_score': primary_result.score,
                            'dup_score': dup_result.score,
                            'primary_answer': primary_result.answer,
                            'dup_answer': dup_result.answer,
                        })

        self.has_conflicts = len(real_conflicts) > 0
        self.conflicts_data = real_conflicts if real_conflicts else None
        return real_conflicts

    def initialize_confirmations(self):
        """
        Хэрэглэгч бүрт баталгаажуулах token үүсгэх
        """
        import uuid
        from django.utils import timezone

        confirmations = {}
        for user_id in self.user_ids:
            confirmations[str(user_id)] = {
                'status': 'pending',
                'token': str(uuid.uuid4()),
                'confirmed_at': None,
                'rejected_at': None,
            }
        self.confirmations = confirmations
        return confirmations

    def get_confirmation_status(self, user_id):
        """
        Тухайн хэрэглэгчийн баталгаажуулалтын статусыг буцаана
        """
        return self.confirmations.get(str(user_id), {}).get('status', 'unknown')

    def confirm_by_user(self, user_id, token):
        """
        Хэрэглэгч баталгаажуулах
        Returns: (success: bool, message: str)
        """
        from django.utils import timezone

        user_id_str = str(user_id)

        if user_id_str not in self.confirmations:
            return False, "Хэрэглэгч олдсонгүй"

        user_conf = self.confirmations[user_id_str]

        if user_conf['token'] != token:
            return False, "Буруу баталгаажуулах код"

        if user_conf['status'] == 'confirmed':
            return False, "Аль хэдийн баталгаажуулсан байна"

        if user_conf['status'] == 'rejected':
            return False, "Та энэ хүсэлтийг татгалзсан байна"

        # Confirm
        user_conf['status'] = 'confirmed'
        user_conf['confirmed_at'] = timezone.now().isoformat()
        self.confirmations[user_id_str] = user_conf
        self.save()

        # Check if all confirmed
        if self.is_all_confirmed():
            self.auto_approve_and_merge()

        return True, "Амжилттай баталгаажууллаа"

    def reject_by_user(self, user_id, token):
        """
        Хэрэглэгч татгалзах
        Returns: (success: bool, message: str)
        """
        from django.utils import timezone

        user_id_str = str(user_id)

        if user_id_str not in self.confirmations:
            return False, "Хэрэглэгч олдсонгүй"

        user_conf = self.confirmations[user_id_str]

        if user_conf['token'] != token:
            return False, "Буруу баталгаажуулах код"

        if user_conf['status'] == 'rejected':
            return False, "Аль хэдийн татгалзсан байна"

        # Reject
        user_conf['status'] = 'rejected'
        user_conf['rejected_at'] = timezone.now().isoformat()
        self.confirmations[user_id_str] = user_conf

        # Cancel the merge request
        self.status = self.Status.REJECTED
        self.review_notes = f"Хэрэглэгч ID {user_id} татгалзсан тул автоматаар цуцлагдсан"
        self.save()

        return True, "Хүсэлтийг татгалзсан. Нэгтгэлт цуцлагдсан."

    def is_all_confirmed(self):
        """
        Бүх хэрэглэгч баталгаажуулсан эсэхийг шалгах
        """
        for user_id_str, conf in self.confirmations.items():
            if conf['status'] != 'confirmed':
                return False
        return True

    def get_confirmation_stats(self):
        """
        Баталгаажуулалтын статистик буцаах
        Returns: {'confirmed': 2, 'pending': 1, 'rejected': 0, 'total': 3}
        """
        stats = {'confirmed': 0, 'pending': 0, 'rejected': 0, 'total': len(self.confirmations)}
        for user_id_str, conf in self.confirmations.items():
            status = conf['status']
            if status in stats:
                stats[status] += 1
        return stats

    def auto_approve_and_merge(self):
        """
        Бүх хэрэглэгч баталгаажуулсан үед автоматаар нэгтгэх
        """
        if not self.is_all_confirmed():
            return False, "Бүх хэрэглэгч баталгаажуулаагүй байна"

        if self.has_conflicts:
            self.status = self.Status.REJECTED
            self.review_notes = "Автомат татгалзсан: дүнгийн зөрчил байна"
            self.save()
            return False, "Дүнгийн зөрчил байгаа тул нэгтгэх боломжгүй"

        # Call the merge logic from admin.py
        from .views.admin import _perform_merge
        from django.db import transaction

        try:
            with transaction.atomic():
                success = _perform_merge(self)
                if success:
                    self.status = self.Status.COMPLETED
                    self.review_notes = "Автомат нэгтгэсэн: бүх хэрэглэгч баталгаажуулсан"
                    self.save()
                    return True, "Амжилттай нэгтгэлээ"
                else:
                    self.status = self.Status.FAILED
                    self.save()
                    return False, "Нэгтгэх үед алдаа гарлаа"
        except Exception as e:
            self.status = self.Status.FAILED
            self.merge_error = str(e)
            self.save()
            return False, f"Алдаа: {str(e)}"