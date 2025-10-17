from django.urls import path
from .views import ChatbotAPIView 

urlpatterns = [
    path('ask/', ChatbotAPIView.as_view(), name='chatbot_ask'),
]