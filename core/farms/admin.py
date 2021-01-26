from django.contrib import admin

from .models import (
    ControllerAuthToken,
    ControllerComponent,
    ControllerComponentType,
    ControllerMessage,
    ControllerTask,
    DataPoint,
    DataPointType,
    PeripheralComponent,
    PeripheralDataPointType,
    Site,
    SiteEntity,
)

# Register your models here.


@admin.register(Site)
class SiteAdmin(admin.ModelAdmin):
    pass


@admin.register(SiteEntity)
class SiteEntityAdmin(admin.ModelAdmin):
    pass


@admin.register(ControllerComponentType)
class ControllerComponentTypeAdmin(admin.ModelAdmin):
    pass


@admin.register(ControllerComponent)
class ControllerComponentAdmin(admin.ModelAdmin):
    pass


@admin.register(PeripheralComponent)
class PeripheralComponentAdmin(admin.ModelAdmin):
    pass


@admin.register(PeripheralDataPointType)
class PeripheralDataPointTypeAdmin(admin.ModelAdmin):
    pass


@admin.register(ControllerTask)
class ControllerTaskAdmin(admin.ModelAdmin):
    pass


@admin.register(DataPointType)
class DataPointTypeAdmin(admin.ModelAdmin):
    pass


@admin.register(DataPoint)
class DataPointAdmin(admin.ModelAdmin):
    pass


@admin.register(ControllerAuthToken)
class ControllerAuthTokenAdmin(admin.ModelAdmin):
    def get_form(self, request, obj=None, change=False, **kwargs):
        form = super(ControllerAuthTokenAdmin, self).get_form(request, obj, **kwargs)
        form.base_fields["key"].initial = ControllerAuthToken.generate_key()
        return form


@admin.register(ControllerMessage)
class ControllerMessageAdmin(admin.ModelAdmin):
    pass
