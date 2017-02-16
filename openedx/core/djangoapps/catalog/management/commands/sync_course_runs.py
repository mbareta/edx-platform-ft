"""
Sync course runs from catalog service.
"""
import logging

from django.core.management.base import BaseCommand
from opaque_keys.edx.keys import CourseKey

from catalog.utils import get_catalog_course_runs
from content.course_overviews.models import CourseOverview

logger = logging.getLogger(__name__)


def update_course_overviews(course_runs):
    """
    Refresh marketing urls for the given catalog course runs.

    Arguments:
        course_runs: A list containing catalog course runs.
    """
    for course_run in course_runs:
        marketing_url = course_run['marketing_url']
        course_key = CourseKey.from_string(course_run['key'])
        try:
            course_overview = CourseOverview.objects.get(id=course_key)
        except CourseOverview.DoesNotExist:
            # In that case just continue to next iteration.
            continue

        # Check whether course overview's marketing url is outdated - this would save a db hit.
        if course_overview.marketing_url != marketing_url:
            course_overview.marketing_url = marketing_url
            course_overview.save()


class Command(BaseCommand):
    """
    Purpose is to sync course runs data from catalog service make it accessible in edx-platform.
    It just happens to only be syncing marketing URLs from catalog course runs for now.
    """
    help = 'Refresh marketing urls from catalog service.'

    def handle(self, *args, **options):
        update_course_overviews(course_runs=get_catalog_course_runs())
