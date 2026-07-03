# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is the **MMO (Math Minds Olympiad)** Django application - a comprehensive platform for managing mathematics olympiads in Mongolia. The system handles user registration, school management, olympiad administration, problem sets, scoring, and certificate generation.

**Key Language Note**: This codebase uses Mongolian (Cyrillic) for UI text, comments, and variable names.

## Development Commands

### Environment Setup
```bash
# Activate virtual environment
source /home/deploy/django/venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Running the Application
```bash
# Run development server
cd /home/deploy/django/mmo
python manage.py runserver

# Run with Gunicorn (production-like)
gunicorn mmo.wsgi:application
```

### Database Operations
```bash
# Create migrations
python manage.py makemigrations

# Apply migrations
python manage.py migrate

# Database: PostgreSQL on localhost, database name 'mmo' (see DATABASES['default'] in settings.py)
# Note: settings.py also defines an unused 'mysql' entry in DATABASES left over from a prior backend;
# Django only ever connects to 'default' (postgresql_psycopg2).
```

### Celery Task Queue
```bash
# Start Celery worker
celery -A mmo worker -l info

# Start Celery Beat scheduler (for periodic tasks)
celery -A mmo beat -l info

# Both together (development)
celery -A mmo worker -B -l info
```

Celery is configured to use Redis (localhost:6379/0) as broker and result backend.

### Testing
```bash
# Run all tests
python manage.py test

# Run specific app tests
python manage.py test accounts
python manage.py test olympiad
python manage.py test schools
```

### Static Files
```bash
# Collect static files
python manage.py collectstatic

# Clear cache
python manage.py clearcache
```

### Custom Management Commands

#### School Management
```bash
# Export schools to Excel
python manage.py export_schools_excel

# Show school staff
python manage.py show_school_staff

# Fix duplicate schools
python manage.py fixduplicateschools

# Sync user schools with groups
python manage.py sync_user_schools

# Check moderator-school relationships
python manage.py check_moderator_school
```

#### User Management
```bash
# Auto-merge duplicate users
python manage.py automerge_users

# Find duplicate users
python manage.py find_duplicate_users

# Find duplicate school users
python manage.py find_duplicate_school_users

# Delete inactive users
python manage.py delete_inactive_users

# Advance grades (end of school year)
python manage.py advance_grades

# Import user groups
python manage.py import_user_groups

# Update student schools from groups
python manage.py update_students_school_from_group
```

#### Olympiad Quota Management
```bash
# Generate quota template
python create_additional_quota_template.py

# Process additional quota (dry run first)
python manage.py first_to_second_by_ranking --config-file additional_quota.xlsx --dry-run

# Process additional quota (apply)
python manage.py first_to_second_by_ranking --config-file additional_quota.xlsx
```

See `QUICK_START.md` and `ADDITIONAL_QUOTA_GUIDE.md` for detailed quota management workflows.

## Architecture

### Django Apps Structure

**`accounts/`** - User management and authentication
- Models: `User` (Django built-in), `UserMeta`, `Author`, `Province`, `Zone`, `Grade`, `Level`, `TeacherStudent`
- Handles user profiles, registration numbers, school associations, grades, and provinces
- Custom user registration flow with email activation
- School association logic: when a user's school changes, they're automatically removed from the old school's group

**`olympiad/`** - Core olympiad functionality
- Models: `Olympiad`, `SchoolYear`, `Problem`, `Topic`, `AnswerChoice`, `Solution`, `Result`, `ScoreSheet`, `Award`, `Team`/`TeamMember`, `Threshold`
- Manages olympiad lifecycle: creation, problem sets, submissions, scoring, results
- Round system: School → Province/District → Capital/Region → National → International, chained via `Olympiad.next_round`
- Two olympiad types: Traditional (hand-graded) and Test (auto-graded)
- Certificate generation using LaTeX templates (via `django-tex`)
- Cheating analysis utilities (`cheating_analysis.py`, `cheating_analysis_pro.py`)
- View logic is split by audience rather than one `views.py`: `views_public.py` (public results/stats), `views_contest.py` / `views_contest_cbv.py` (taking the exam), `views_api.py` (session-authenticated `SaveAnswerAPIView`/`BulkSaveAnswersAPIView` for saving answers during a contest), `views_admin.py` (grading/admin), `result_views.py`, `api_views.py` (external machine-to-machine API, see below)
- Round-advancement business logic lives in management commands (`first_to_second_by_ranking`, `second_to_third_fourth_by_ranking`, `third_to_fourth_by_ranking`), not in views/models

**`schools/`** - School management
- Models: `School` with relationships to `User` (moderator), `User` (manager), `Group`, `Province`
- Each school can have: moderator, manager, associated Django group, and official participation levels
- Email service for bulk communications (`email_service.py`)
- Celery tasks for async operations

**`emails/`** - Email campaign management
- Scheduled and bulk email sending via Amazon SES (configured in `settings.py`)
- Campaign management with pause/resume functionality
- Celery Beat integration for automated campaign execution

**`posts/`** - Homepage content and news
- Serves as the homepage (`/` points to posts app)

**`file_management/`** - File upload and management utilities

**`provinces/`** - Province-level views/URLs (`/provinces/`); the `Province`/`Zone` models themselves live in `accounts/models.py`, not here.

### Key Architectural Patterns

**Multi-App Django Structure**: Each domain (users, schools, olympiads) is a separate Django app with its own models, views, URLs, and templates.

**Group-Based Permissions**: Schools are associated with Django `Group` objects. Users inherit permissions through group membership. When a user changes schools, they're automatically moved between groups.

**Two separate external-access mechanisms — don't confuse them**:
- `/api/olympiads/...` (`olympiad/api_views.py`) is a plain machine-to-machine API guarded by a shared-secret header (`X-API-Key`, checked against `settings.MMO_API_KEY`), not by OAuth2.
- `/o/...` (`django-oauth-toolkit`) issues real OAuth2 tokens, used by the CORS-allowed external client at mathminds.club (see `CORS_ALLOWED_ORIGINS` in `settings.py`). `olympiad/views_api.py`'s `SaveAnswerAPIView`/`BulkSaveAnswersAPIView` are session/login-authenticated (`LoginRequiredMixin`), not OAuth2-protected either.

**Celery for Async Tasks**: Email campaigns, quota calculations, and bulk operations run asynchronously. Tasks defined in each app's `tasks.py` (`accounts`, `schools`, `emails`).

**LaTeX Certificate Generation**: Certificates generated from `.tex` templates in `templates/olympiad/`. Uses ImageMagick for PNG conversion. Requires system LaTeX installation.

**Maintenance Mode**: `MAINTENANCE_MODE` setting restricts access to staff and school moderators during system maintenance (see `mmo/middleware.py`).

### Important Model Relationships

- `User` ← (OneToOne) → `UserMeta` (extended profile: school, grade, province, reg_num)
- `School` ← (FK) → `User` (moderator), `User` (manager), `Group`, `Province`
- `Olympiad` ← (FK) → `SchoolYear`, `Level`, `Province` (host), `Group` (eligible participants)
- `Olympiad` → `next_round` (self-referential FK for multi-round progression)
- `ScoreSheet` ← (FK) → `User`, `Olympiad` (stores answers and scores)
- `Problem` ← (FK) → `Olympiad`, `Topic`, `Author`

### Templates and Frontend

Templates use Django template language with `crispy_forms` (Bootstrap 4, per `CRISPY_TEMPLATE_PACK`) and `widget_tweaks`. CKEditor/TinyMCE for rich text editing, `django-select2` for search widgets.

### External Services

- **Amazon SES**: Email sending via `django-anymail` (configured with AWS credentials in settings)
- **AWS S3**: `DEFAULT_FILE_STORAGE` is `storages.backends.s3boto3.S3Boto3Storage` — media uploads go to S3 (`AWS_STORAGE_BUCKET_NAME`), not the local `MEDIA_ROOT`/`media/` folder, even though those settings are also defined
- **Redis**: Celery broker and result backend (localhost:6379)
- **PostgreSQL**: Primary database (localhost:5432)
- **WhiteNoise**: Serves static files in production (`STATICFILES_STORAGE`), fronted by `corsheaders`/`SecurityMiddleware`

## Configuration Notes

**Development vs Production**:
- `settings.py` currently has `DEBUG = False` and a real `ALLOWED_HOSTS` list checked in — this is the file used for the live site, not a dev template. Flip `DEBUG` locally as needed; don't assume the checked-in value is dev-safe.
- Development settings hardcoded in `settings.py` (should use env vars in production)
- Static files served by Django in DEBUG mode, otherwise use separate static file server

**Security Warning**: The codebase contains hardcoded credentials in `settings.py`:
- `SECRET_KEY`
- `MMO_API_KEY`
- AWS credentials
- Database password

These should be moved to environment variables for production deployment.

**Time Zone**: All timestamps use `Asia/Ulaanbaatar` timezone (UTC+8).

**Language/Locale**: `mn-mn` (Mongolian)

## Testing Approach

Tests are minimal (stub `tests.py` files in each app). When adding tests:
- Use Django's `TestCase` for database-dependent tests
- Use `Client` for view/integration tests
- Mock external services (SES, S3) in tests
- Test quota calculation logic thoroughly (complex business rules)

Note: the repo root also has several `test_*.py` and `check_*.py` files (e.g. `test_quota.log`-adjacent scripts). These are ad hoc one-off debugging scripts run directly with `python`, not part of the Django test suite — `python manage.py test` does not discover or run them.

## Common Workflows

**Adding a New Olympiad**:
1. Create `SchoolYear` if needed
2. Create `Olympiad` with correct round, level, type
3. Add `Problem` instances linked to the olympiad
4. Set `start_time`, `end_time`, and `is_open=True`
5. Optionally link `next_round` for progression

**Processing Olympiad Results**:
1. Set `is_grading=True` during scoring period
2. Use `ScoreSheet` model to store/update scores
3. Generate certificates via LaTeX templates
4. Use quota management commands for advancement to next rounds

**Managing School Users**:
1. School moderators/managers can see their school's students
2. Use management commands to sync groups when schools change
3. Automatic group membership updates when `UserMeta.school` changes

## File Locations

- Main settings: `/home/deploy/django/mmo/mmo/settings.py`
- URL routing: `/home/deploy/django/mmo/mmo/urls.py`
- Celery config: `/home/deploy/django/mmo/mmo/celery.py`
- LaTeX templates: `/home/deploy/django/mmo/templates/olympiad/*.tex`
- Management commands: `<app>/management/commands/*.py`
- Logs: `/home/deploy/django/mmo/logs/`
