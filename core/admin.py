from django.contrib import admin
from .models import *
admin.site.register([Instrument, Folder, Source, SourceVersion, PDFFragment, VideoFragment, ImageFragment, AccessGrant, AccessRequest, ChatSession, ChatTurn, Attachment, Citation, Feedback, Connector])
