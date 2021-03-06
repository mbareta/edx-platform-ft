from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.contrib import messages
from django.core import serializers
from django.shortcuts import render, redirect
from django.db.models import Q, F
from django.http import Http404
from lms.envs.common import STATE_CHOICES
from django_countries import countries
from edxmako.shortcuts import render_to_response, render_to_string
from lms.djangoapps.ccx.models import CustomCourseForEdX
from .models import AffiliateEntity, AffiliateMembership, AffiliateInvite
from django.contrib.auth.models import User
from student.models import CourseEnrollment
from lms.djangoapps.instructor.views.tools import get_student_from_identifier
from .decorators import only_program_director, only_staff
from .tasks import export_csv_user_report, export_csv_affiliate_course_report, export_csv_affiliate_report, export_csv_course_report
from instructor_task.models import ReportStore
import django.contrib.auth as auth



@only_staff
def admin(request):
    affiliates = AffiliateEntity.objects.all().order_by('name')
    ccxs = CustomCourseForEdX.objects.all()
    ccxs = sorted(ccxs, key = lambda ccx: ccx.affiliate.name)
    fasttrac_course_key = settings.FASTTRAC_COURSE_KEY

    total_learners = CourseEnrollment.objects.filter(is_active=True).count()
    total_fasttrac_learners = CourseEnrollment.objects.filter(is_active=True, course_id__startswith=fasttrac_course_key).count()
    total_affiliate_learners = CourseEnrollment.objects.filter(is_active=True).exclude(course_id__startswith=fasttrac_course_key).count()

    return render_to_response('affiliates/admin.html', {
        'affiliates': affiliates,
        'ccxs': ccxs,
        'partial_course_key': fasttrac_course_key.split(':')[1],
        'total_learners': total_learners,
        'total_fasttrac_learners': total_fasttrac_learners,
        'total_affiliate_learners': total_affiliate_learners
    })


@only_staff
def csv_admin(request):
    report_store = ReportStore.from_config('GRADES_DOWNLOAD')

    return render_to_response('affiliates/csv_admin.html', {
        'csv_files': report_store.links_for('affiliates')
    })


@only_staff
def csv_export(request):
    report_type = request.GET.get('report_type')

    if report_type == 'export_csv_affiliate_report':
        export_csv_affiliate_report.delay()
        messages.add_message(request, messages.INFO, 'Generating affiliate report CSV... Refresh to see the download link below.')

    elif report_type == 'export_csv_affiliate_course_report':
        export_csv_affiliate_course_report.delay()
        messages.add_message(request, messages.INFO, 'Generating affiliate course report CSV... Refresh to see the download link below.')

    elif report_type == 'export_csv_user_report':
        export_csv_user_report.delay()
        messages.add_message(request, messages.INFO, 'Generating user report CSV... Refresh to see the download link below.')

    elif report_type == 'export_csv_time_report':
        export_csv_course_report.delay(time_report=True)
        messages.add_message(request, messages.INFO, 'Generating course time report CSV... Refresh to see the download link below.')

    elif report_type == 'export_csv_completion_report':
        export_csv_course_report.delay(time_report=False)
        messages.add_message(request, messages.INFO, 'Generating course completion report CSV... Refresh to see the download link below.')

    return redirect('affiliates:csv_admin')


def index(request):
    affiliate_id = request.GET.get('affiliate_id', '')
    affiliate_city = request.GET.get('affiliate_city', '')
    affiliate_state = request.GET.get('affiliate_state', '')
    location_latitude = request.GET.get('latitude', '')
    location_longitude = request.GET.get('longitude', '')
    search_radius = request.GET.get('affiliate_search_radius', '')
    user_messages = []

    if not affiliate_id:
        filters = {'active': True}
        if location_latitude and location_longitude and search_radius:
            from courseware.views.views import get_coordinate_boundaries
            latitude_boundaries, longitude_boundaries = get_coordinate_boundaries(
                float(location_latitude), float(location_longitude), float(search_radius))

            filters['location_latitude__range'] = latitude_boundaries
            filters['location_longitude__range'] = longitude_boundaries
        else:
            if affiliate_city:
                filters['city__icontains'] = affiliate_city
            if affiliate_state:
                filters['state'] = affiliate_state

        affiliates = AffiliateEntity.objects.filter(**filters).order_by('name')
        if location_latitude and location_longitude:
            affiliates = affiliates.exclude(Q(location_longitude=None) | Q(location_latitude=None))
            affiliates = sorted(affiliates, key=lambda affiliate: affiliate.distance_from(
            {'latitude': location_latitude, 'longitude': location_longitude}))


            if len(affiliates) > 0:
                user_messages.append('Affiliates are sorted by the distance!')
    else:
        affiliates = AffiliateEntity.objects.filter(pk=affiliate_id, active=True)

    all_affiliates = AffiliateEntity.objects.filter(active=True).order_by('name')
    affiliates_as_json = serializers.serialize('json', all_affiliates, fields=('name', 'id'))

    return render_to_response('affiliates/index.html', {
        'affiliates': affiliates,
        'affiliates_as_json': affiliates_as_json,
        'affiliate_city': affiliate_city,
        'affiliate_state': affiliate_state,
        'state_choices': STATE_CHOICES,
        'user_messages': user_messages
    })


def show(request, slug):
    affiliate = AffiliateEntity.objects.get(slug=slug)

    return render_to_response('affiliates/show.html', {
        'affiliate': affiliate,
        'is_program_director': is_program_director(request.user, affiliate)
    })


@only_program_director
def new(request):
    return render_to_response('affiliates/form.html', {
        'affiliate': AffiliateEntity(),
        'state_choices': STATE_CHOICES,
        'countries': countries,
        'role_choices': AffiliateMembership.role_choices
    })


@only_program_director
def create(request):
    affiliate = AffiliateEntity()
    post_data = request.POST.copy().dict()

    program_director_identifier = post_data.pop('member_identifier', None)

    # delete image from POST since we pull it from FILES
    post_data.pop('image', None)

    if request.FILES and request.FILES['image']:
        setattr(affiliate, 'image', request.FILES['image'])

    for key in post_data:
        if key == 'year_of_birth':
            setattr(affiliate, key, int(post_data[key]))
        else:
            setattr(affiliate, key, post_data[key])

    affiliate.save()

    # SurveyGizmo functionality to automatically add Program Director upon creation
    if program_director_identifier:
        member = get_student_from_identifier(program_director_identifier)
        AffiliateMembership.objects.create(affiliate=affiliate, member=member, role='staff')

    return redirect('affiliates:show', slug=affiliate.slug)

@only_staff
def edit(request, slug):
    affiliate = AffiliateEntity.objects.get(slug=slug)

    if request.method == 'POST':
        # delete image from POST since we pull it from FILES
        request.POST.pop('image', None)

        if request.FILES and request.FILES['image']:
            setattr(affiliate, 'image', request.FILES['image'])

        for key in request.POST:
            if key == 'year_of_birth':
                setattr(affiliate, key, int(request.POST[key]))
            else:
                setattr(affiliate, key, request.POST[key])

        affiliate.save()

        return redirect('affiliates:show', slug=affiliate.slug)

    role_choices = AffiliateMembership.role_choices

    if not request.user.is_staff:
        role_choices = (
            ('ccx_coach', 'Facilitator'),
            ('instructor', 'Course Manager'),
        )

    return render_to_response('affiliates/form.html', {
        'affiliate': affiliate,
        'state_choices': STATE_CHOICES,
        'countries': countries,
        'role_choices': role_choices,
        'is_program_director': is_program_director(request.user, affiliate)
    })

@only_program_director
def delete(request, slug):
    AffiliateEntity.objects.get(slug=slug).delete()

    return redirect('affiliates:index')


def payment(request):
    return render_to_response('affiliates/payment.html', {
        'preview': settings.PAYMENT_PREVIEW
    })


@only_staff
def add_member(request, slug):
    member_identifier = request.POST.get('member_identifier')
    role = request.POST.get('role')
    affiliate = AffiliateEntity.objects.get(slug=slug)

    if role == 'staff' and not request.user.is_staff:
        messages.add_message(request, messages.INFO, 'You are not allowed to do that.')
        return redirect('affiliates:edit', slug=slug)

    try:
        member = get_student_from_identifier(member_identifier)
    except ObjectDoesNotExist:
        # create a user invite if the user does not exist
        invite_new_user(affiliate, member_identifier, role, request.user)

        messages.add_message(request, messages.INFO, 'User "{}" does not exist. They will be invited.'.format(member_identifier))
        return redirect('affiliates:edit', slug=slug)

    params = {
        'affiliate': affiliate,
        'member': member,
        'role': role,
    }

    membership = AffiliateMembership.objects.create(**params)

    return redirect('affiliates:edit', slug=slug)


@only_staff
def remove_member(request, slug, member_id):
    role = request.GET.get('role')

    if role == 'staff' and not request.user.is_staff:
        messages.add_message(request, messages.INFO, 'You are not allowed to do that.')
        return redirect('affiliates:edit', slug=slug)

    params = {
        'affiliate': AffiliateEntity.objects.get(slug=slug),
        'member_id': member_id,
        'role': role
    }

    try:
        AffiliateMembership.objects.filter(**params).delete()
    except ValueError as e:
        messages.add_message(request, messages.INFO, e)

    return redirect('affiliates:edit', slug=slug)


@only_staff
def remove_invite(request, slug, invite_id):
    try:
        AffiliateInvite.objects.get(id=invite_id).delete()
    except ValueError as e:
        messages.add_message(request, messages.INFO, e)

    return redirect('affiliates:edit', slug=slug)


@only_staff
def toggle_active_status(request, slug):
    affiliate = AffiliateEntity.objects.select_for_update().get(slug=slug)
    affiliate.active = not affiliate.active
    affiliate.save()

    return redirect('affiliates:edit', slug=slug)


@only_staff
def login_as_user(request):
    email = request.POST.get('email')
    try:
        user = User.objects.get(email=email)
        if not hasattr(request.user, 'backend'):
            user.backend = _get_path_of_arbitrary_backend_for_user(user)

        auth.login(request, user)
        return redirect('/')
    except User.DoesNotExist:
        messages.error(request, 'User "{}" does not exist'.format(email))
        return redirect(request.META['HTTP_REFERER'])


def is_program_director(user, affiliate):
    if user.is_anonymous():
        return False
    else:
        return user.is_staff or AffiliateMembership.objects.filter(member=user, affiliate=affiliate, role='staff').exists()


def invite_new_user(affiliate, user_email, role, current_user):
    AffiliateInvite.objects.create(affiliate=affiliate, email=user_email, role=role, invited_by=current_user)


def _get_path_of_arbitrary_backend_for_user(user):
        """
        Return the path to the first found authentication backend that recognizes the given user.
        """
        for backend_path in settings.AUTHENTICATION_BACKENDS:
            backend = auth.load_backend(backend_path)
            if backend.get_user(user.id):
                return backend_path
