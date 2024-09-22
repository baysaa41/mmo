from django.db import models
from django.contrib.auth.models import User, Group
from accounts.models import Province


class School(models.Model):
    user = models.ForeignKey(User, related_name='moderating', on_delete=models.CASCADE)
    group = models.ForeignKey(Group, related_name='moderator', on_delete=models.CASCADE)
    province = models.ForeignKey(Province, related_name='moderators', on_delete=models.CASCADE)
    name = models.CharField(max_length=200, default='ЕБС')

    class Meta:
        unique_together = ('user', 'group')  # Prevent duplicate moderator assignments

    def __str__(self):
        return "{}, {}".format(self.group.name, self.user.first_name)

