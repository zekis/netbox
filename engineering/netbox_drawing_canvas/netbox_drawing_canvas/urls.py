from django.urls import path

from . import views

urlpatterns = [
    path('', views.DrawingListView.as_view(), name='drawing_list'),
    path('<int:pk>/', views.DrawingView.as_view(), name='drawing'),
    path('<int:pk>/scene/', views.scene, name='drawing_scene'),
    path('<int:pk>/equipment/', views.equipment, name='drawing_equipment'),
]
