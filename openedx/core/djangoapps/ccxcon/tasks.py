"""
This file contains celery tasks for ccxcon
"""

from celery.task import task  # pylint: disable=no-name-in-module, import-error
from celery.utils.log import get_task_logger  # pylint: disable=no-name-in-module, import-error
from requests.exceptions import (
    ConnectionError,
    HTTPError,
    RequestException,
    TooManyRedirects
)

from opaque_keys.edx.keys import CourseKey

from openedx.core.djangoapps.ccxcon import api
from celery.contrib import rdb

log = get_task_logger(__name__)


@task()
def update_ccxcon(course_id, cur_retry=0):
    """
    Pass through function to update course information on CCXCon.
    Takes care of retries in case of some specific exceptions.

    Args:
        course_id (str): string representing a course key
        cur_retry (int): integer representing the current task retry
    """
    course_key = CourseKey.from_string(course_id)
    try:
        api.course_info_to_ccxcon(course_key)
        log.info('Course update to CCXCon returned no errors. Course key: %s', course_id)
    except (ConnectionError, HTTPError, RequestException, TooManyRedirects, api.CCXConnServerError) as exp:
        log.error('Course update to CCXCon failed for course_id %s with error: %s', course_id, exp)
        # in case the maximum amount of retries has not been reached,
        # insert another task delayed exponentially up to 5 retries
        if cur_retry < 5:
            update_ccxcon.apply_async(
                kwargs={'course_id': course_id, 'cur_retry': cur_retry + 1},
                countdown=10 ** cur_retry  # number of seconds the task should be delayed
            )
            log.info('Requeued celery task for course key %s ; retry # %s', course_id, cur_retry + 1)


@task()
def index_ccx(course_key, **kwargs):  # pylint: disable=unused-argument
    """
    Receives the index_ccx signal sent by LMS when user changes CCX schedule and triggers handler
    for indexing ccx.

    Arguments:
        course_key: Contains the content usage key of the item deleted
        kwargs: "Signals receiver must accept **kwargs"

    Returns:
        None
    """
    # LOGGER.debug('********************************************************************** in signal handler')
    course_key = CourseKey.from_string(course_key)
    rdb.set_trace()
    from cms.djangoapps.contentstore.courseware_index import CoursewareSearchIndexer
    rdb.set_trace()
    from contentstore.courseware_index import SearchIndexingError
    rdb.set_trace()
    from xmodule.modulestore.django import modulestore

    rdb.set_trace()
    with modulestore().bulk_operations(course_key):
        try:
            rdb.set_trace()
            CoursewareSearchIndexer.do_course_reindex(modulestore(), course_key)
            rdb.set_trace()
        except SearchIndexingError as search_err:
            print search_err  # temp
