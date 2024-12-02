from django.contrib import admin

from .models import UserModel, UserTokenModel, RoleModel

admin.site.register(UserModel)
admin.site.register(UserTokenModel)
admin.site.register(RoleModel)
