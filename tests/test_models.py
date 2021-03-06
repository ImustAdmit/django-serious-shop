from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.urls import resolve, reverse

import pytest
from addresses.models import Address
from items.models import Category, Item, ItemImage
from lib.utils import get_sentinel_user_anonymous, image_directory_path
from orders.models import Order

from .factories import (
    AddressFactory,
    CategoryFactory,
    ItemAccessoryFactory,
    ItemWearFactory,
    OrderFactory,
    OrderItemFactory,
    UserFactory,
    WearSizeFactory,
)


@pytest.mark.django_db
def test_category_model():
    base_cat = CategoryFactory()
    category1 = CategoryFactory(name="wear", parent=base_cat)
    item1 = ItemAccessoryFactory(category=category1)
    assert Category.objects.count() == 2
    assert category1.items.count() == 1
    assert list(category1.items.all()) == [item1]

    item2 = ItemAccessoryFactory(category=category1)
    assert category1.items.count() == 2
    assert list(category1.items.all()) == [item1, item2]
    assert base_cat.items.count() == 0


@pytest.mark.django_db
def test_item_model():
    category_wear = CategoryFactory(need_sizes=True)
    category_item = CategoryFactory(need_sizes=False)
    item2 = ItemAccessoryFactory(
        title="same_title", price=10.00, discount_price=5.00, category=category_item
    )
    item3 = ItemAccessoryFactory(
        title="same_title", price=10.00, discount_price=None, category=category_item
    )
    wear1 = ItemWearFactory(title="same_title", category=category_wear, color="Blue")
    wear2 = ItemWearFactory(title="same_title", category=category_wear, color="Blue")
    assert item2.slug == "same_title"
    assert item3.slug == "same_title-1"
    assert wear1.slug == "same_title"
    assert wear2.slug == "same_title-1"
    assert item2.actual_price == 5.00
    assert item3.actual_price == 10.00

    wear1.quantity = 10
    with pytest.raises(ValidationError):
        assert wear1.full_clean()

    # testing custom manager
    item2.active = False
    item2.save()
    assert Item.objects.active().count() == 3
    assert list(Item.objects.active()) == [item3, wear1, wear2]
    assert Item.objects.search(wear1.color).count() == 2
    assert list(Item.objects.search(wear1.color)) == [wear1, wear2]
    assert Item.objects.in_category(category_wear).count() == 2
    assert Item.objects.in_category(category_item).count() == 1
    assert list(Item.objects.in_category(category_wear)) == [wear1, wear2]


@pytest.mark.django_db
def test_wearsize_model():
    category_wear = CategoryFactory(need_sizes=True)
    wear1 = ItemWearFactory(category=category_wear)
    item1 = ItemAccessoryFactory()
    wearsize1 = WearSizeFactory(size="M", quantity=10)
    wearsize1.item = item1
    with pytest.raises(ValidationError):
        assert wearsize1.full_clean()

    wear1.sizes.add(wearsize1)
    assert wear1.sizes.all().count() == 2

    with pytest.raises(Exception):
        assert wearsize1.save()


@pytest.mark.django_db
def test_address_model():
    user = UserFactory()
    billing_address = AddressFactory(
        address_type="billing", is_default=False, user=user
    )
    shipping_address = AddressFactory(
        address_type="shipping", is_default=False, user=get_sentinel_user_anonymous()
    )
    assert billing_address.is_default == True
    assert shipping_address.is_default == False

    billing_address2 = AddressFactory(
        address_type="billing", is_default=True, user=user
    )
    assert billing_address2.is_default == True
    assert (
        not Address.objects.filter(user=user, address_type="billing", is_default=True)
        .exclude(id=billing_address2.id)
        .exists()
    )

    # testing custom manager
    shipping_address.user = user
    shipping_address.save()
    assert Address.objects.default_shipping(user)[0] == shipping_address
    assert Address.objects.default_billing(user)[0] == billing_address2

    billing_address.user = user
    billing_address.save()
    assert Address.objects.default_billing(user)[0] == billing_address


@pytest.mark.django_db
def test_orderitem_model():
    wear = ItemWearFactory(quantity=10)
    acc = ItemAccessoryFactory(quantity=10)
    order_item = OrderItemFactory(item=wear, price=10, quantity=5)
    order_item2 = OrderItemFactory(item=acc, price=10, quantity=20)
    assert order_item.get_cost() == 50
    assert order_item2.get_cost() == 200
    assert Item.objects.get(id=wear.id).quantity == 5
    assert Item.objects.get(id=acc.id).quantity == -10


@pytest.mark.django_db
def test_order_model():
    item1 = ItemWearFactory(price=25.00, discount_price=10.00)
    item2 = ItemAccessoryFactory(quantity=10, price=50.00, discount_price=25.00)
    item1.sizes.add(WearSizeFactory(size="M", quantity=10))
    order_item1 = OrderItemFactory(
        item=item1, size=item1.sizes.first().size, quantity=5, price=item1.actual_price
    )
    order_item2 = OrderItemFactory(item=item2, price=item2.actual_price, quantity=1)
    user = UserFactory(email="userlol@wp.pl")
    order = OrderFactory(user=user)
    address = AddressFactory(address_type="shipping", email="lol@wp.pl")
    order2 = OrderFactory(user=get_sentinel_user_anonymous(), shipping_address=address)
    order.items.add(order_item1, order_item2)
    assert order.get_total == Decimal(75)
    assert order.items_quantity == 6
    assert order.get_email == "userlol@wp.pl"
    assert order2.get_email == "lol@wp.pl"
    assert order.paid() == False

    # testing custom manager
    order2 = OrderFactory(user=user)
    Order.objects.filter(user=user).update(status="paid")
    assert list(Order.objects.search_by_user(user)) == [order2, order]
    assert Order.objects.latest("id").paid() == True
