from django.conf import settings

from cart.cart import Cart
from items.models import Category
from lib.models import CompanyInfo


def get_category(request):
    return {"categories": Category.objects.all(), "request": request}


def get_company_info(request):
    return {
        "company": CompanyInfo.objects.get(name=settings.COMPANY_NAME),
        "request": request,
    }


def cart(request):
    return {"cart": Cart(request)}
