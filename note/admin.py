from django.contrib import admin
from .models import NoteModel, NoteCommentModel

admin.site.register(NoteModel)
admin.site.register(NoteCommentModel)
