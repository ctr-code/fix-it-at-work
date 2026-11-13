from django.urls import path

from . import views

urlpatterns = [
    path('', views.home, name='index'),
    path('report/', views.report, name='report'),
    path('my-reports/', views.my_reports, name='my_reports'),
    path('track/', views.track, name='track'),
    path('track/<str:ref>/', views.track_case, name='track_case'),
    path('triage/', views.triage_queue, name='triage_queue'),
    path('triage/<str:ref>/', views.triage_case, name='triage_case'),
    path('cases/<str:ref>/', views.case_detail, name='case_detail'),
    path('cases/<str:ref>/change/', views.reassign_case, name='reassign_case'),
    path('cases/<str:ref>/letter/', views.outcome_letter, name='outcome_letter'),
    path('cases/<str:ref>/request-info/', views.request_info, name='request_info'),
    path('officer/', views.officer_cases, name='officer_cases'),
    path('alerts/', views.alerts_inbox, name='alerts'),
    path('officer/<str:ref>/', views.officer_case, name='officer_case'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('people/', views.people, name='people'),
]
