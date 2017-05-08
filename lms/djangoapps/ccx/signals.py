"""
Asynchronous tasks for the CCX app.
"""

from django.dispatch import receiver
import logging

from xmodule.modulestore.django import SignalHandler
from lms import CELERY_APP

log = logging.getLogger("edx.ccx")

#TODO: remove this
#
# @receiver(SignalHandler.index_ccx)
# def ccx_index_handler(sender, course_key, **kwargs):
#     log.info('**************** IN CCX/ SIGNALS ********************************************************************************** in ccx index handler')
#     send_ccx_indexed.delay(unicode(course_key))
#
#
# @CELERY_APP.task
# def send_ccx_indexed(course_key):
#     log.info('*********************IN CCX/ SIGNALS ***************************************************************************** send ccx indexed')
#     responses = SignalHandler.index_ccx.send("index_ccx", course_key=course_key)
#     log.info('************************************************************************************************** after ccx indexed')
#
#     for rec, response in responses:
#             log.info('********************************************************************** Signal fired when ccx is indexed. Receiver: %s. Response: %s', rec, response)


