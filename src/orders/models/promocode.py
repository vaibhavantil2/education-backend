from typing import Optional

from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db.models import Case, CheckConstraint, Count, Q, When
from django.utils.translation import gettext_lazy as _

from app.models import DefaultQuerySet, TimestampedModel, models
from products.models import Course


class PromoCodeQuerySet(DefaultQuerySet):
    def active(self):
        return self.filter(active=True)

    def with_order_count(self):
        return self.annotate(order_count=Count(Case(
            When(order__paid__isnull=False, then=1),
            output_field=models.IntegerField(),
        )))

    def get_or_nothing(self, name: Optional[str]):
        if name is not None:
            try:
                return self.active().get(name__iexact=name.strip())
            except PromoCode.DoesNotExist:
                return None


class PromoCode(TimestampedModel):
    objects = PromoCodeQuerySet.as_manager()

    name = models.CharField(_('Promo Code'), max_length=32, unique=True, db_index=True)
    discount_percent = models.IntegerField(_('Discount percent'), null=True, blank=True)
    discount_value = models.IntegerField(_('Discount amount'), null=True, blank=True, help_text=_('Takes precedence over percent'))
    active = models.BooleanField(_('Active'), default=True)
    comment = models.TextField(_('Comment'), blank=True, null=True)

    courses = models.ManyToManyField('products.Course', help_text=_('Can not be used for courses not checked here'), blank=True)

    class Meta:
        verbose_name = _('Promo Code')
        verbose_name_plural = _('Promo Codes')
        constraints = [
            CheckConstraint(check=Q(discount_percent__isnull=False) | Q(discount_value__isnull=False), name='percent or value must be set'),
        ]

    def clean(self):
        if self.discount_percent is None and self.discount_value is None:
            raise ValidationError(_('Percent or value must be set'))

    def compatible_with(self, course: Course) -> bool:
        return self.courses.count() == 0 or course in self.courses.all()

    def apply(self, course: Course) -> Decimal:
        if not self.compatible_with(course):
            return course.price

        if self.discount_value is not None and self.discount_value and self.discount_value < course.price:
            return Decimal(course.price - self.discount_value)

        if self.discount_percent is not None:
            return Decimal(course.price * (100 - self.discount_percent) / 100)

        return course.price
