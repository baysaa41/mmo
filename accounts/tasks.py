from celery import shared_task
from django.core.management import call_command
import io
import sys

@shared_task
def run_automerge_all_task():
    """--all горимд automerge коммандыг ажиллуулах Celery task."""
    call_command('automerge_users', all=True, no_input=True)

@shared_task
def run_advance_grades_task():
    """advance_grades коммандыг ажиллуулах Celery task."""
    call_command('advance_grades')