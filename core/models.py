import uuid
from django.conf import settings
from django.db import models
from django.contrib.postgres.fields import ArrayField

ROLE_CHOICES=(("instrument_manager","instrument_manager"),("trained_user","trained_user"))
VIS_CHOICES=(("public","public"),("restricted","restricted"))
SRC_TYPE=(("pdf","pdf"),("video","video"),("image","image"),("note","note"),("url","url"))
SRC_STATUS=(("uploaded","uploaded"),("processing","processing"),("parsed","parsed"),("embedded","embedded"),("approved","approved"),("rejected","rejected"),("archived","archived"))
CATEGORY_CHOICES=(("manual","Manual"),("protocol","Protocol"),("sop","SOP"),("troubleshooting","Troubleshooting"),("training","Training"),("maintenance","Maintenance"))

class Instrument(models.Model):
    id=models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name=models.CharField(max_length=200)
    vendor=models.CharField(max_length=100)
    models_arr=ArrayField(models.CharField(max_length=64), default=list, blank=True)
    visibility=models.CharField(max_length=12, choices=VIS_CHOICES, default="restricted")
    description=models.TextField(blank=True, null=True)
    updated_at=models.DateTimeField(auto_now=True)

class Folder(models.Model):
    id=models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    instrument=models.ForeignKey(Instrument, on_delete=models.CASCADE, related_name="folders")
    name=models.CharField(max_length=200)
    parent=models.ForeignKey("self", null=True, blank=True, on_delete=models.CASCADE, related_name="children")

class Source(models.Model):
    id=models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    instrument=models.ForeignKey(Instrument, on_delete=models.CASCADE, related_name="sources")
    folder=models.ForeignKey(Folder, on_delete=models.SET_NULL, null=True, blank=True)
    type=models.CharField(max_length=12, choices=SRC_TYPE)
    title=models.CharField(max_length=255)
    category=models.CharField(max_length=32, choices=CATEGORY_CHOICES, blank=True, null=True)
    description=models.TextField(blank=True, null=True)
    version=models.CharField(max_length=50, blank=True, null=True)
    model_tags=ArrayField(models.CharField(max_length=64), default=list, blank=True)
    storage_uri=models.TextField()
    status=models.CharField(max_length=12, choices=SRC_STATUS, default="uploaded")
    checksum=models.CharField(max_length=200, blank=True, null=True)
    archived=models.BooleanField(default=False)
    archived_at=models.DateTimeField(null=True, blank=True)
    created_at=models.DateTimeField(auto_now_add=True)

class SourceVersion(models.Model):
    id=models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source=models.ForeignKey(Source, on_delete=models.CASCADE, related_name="versions")
    version=models.CharField(max_length=50)
    storage_uri=models.TextField()
    checksum=models.CharField(max_length=200, blank=True, null=True)
    created_at=models.DateTimeField(auto_now_add=True)

class PDFFragment(models.Model):
    id=models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source=models.ForeignKey(Source, on_delete=models.CASCADE, related_name="pdf_fragments")
    page=models.IntegerField()
    bbox_x=models.IntegerField()
    bbox_y=models.IntegerField()
    bbox_w=models.IntegerField()
    bbox_h=models.IntegerField()
    text_hash=models.CharField(max_length=128)

class VideoFragment(models.Model):
    id=models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source=models.ForeignKey(Source, on_delete=models.CASCADE, related_name="video_fragments")
    t_start=models.FloatField()
    t_end=models.FloatField()
    transcript_text=models.TextField(blank=True, null=True)

class ImageFragment(models.Model):
    id=models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source=models.ForeignKey(Source, on_delete=models.CASCADE, related_name="image_fragments")
    region_x=models.IntegerField(blank=True, null=True)
    region_y=models.IntegerField(blank=True, null=True)
    region_w=models.IntegerField(blank=True, null=True)
    region_h=models.IntegerField(blank=True, null=True)
    alt_text=models.TextField(blank=True, null=True)

class AccessGrant(models.Model):
    id=models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user=models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    instrument=models.ForeignKey(Instrument, on_delete=models.CASCADE)
    role=models.CharField(max_length=32, choices=ROLE_CHOICES)
    status=models.CharField(max_length=12, default="active")
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=["user","instrument"], name="uq_user_instrument")]

class AccessRequest(models.Model):
    id=models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user=models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    instrument=models.ForeignKey(Instrument, on_delete=models.CASCADE)
    reason=models.TextField(blank=True, null=True)
    status=models.CharField(max_length=12, default="pending")
    reviewer=models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="reviews", blank=True)
    reviewed_at=models.DateTimeField(blank=True, null=True)
    created_at=models.DateTimeField(auto_now_add=True)

class ChatSession(models.Model):
    id=models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    instrument=models.ForeignKey(Instrument, on_delete=models.CASCADE)
    owner_email=models.EmailField(blank=True, null=True)
    title=models.CharField(max_length=255, blank=True, null=True)
    share_token=models.CharField(max_length=40, blank=True, null=True, unique=True)
    created_at=models.DateTimeField(auto_now_add=True)

class ChatTurn(models.Model):
    id=models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session=models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name="turns")
    role=models.CharField(max_length=16) # user|assistant
    text=models.TextField(blank=True, null=True)
    rating=models.CharField(max_length=8, blank=True, null=True) # like|dislike
    feedback_tag=models.CharField(max_length=32, blank=True, null=True) # hallucination|offtopic|etc
    created_at=models.DateTimeField(auto_now_add=True)

class Attachment(models.Model):
    id=models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    turn=models.ForeignKey(ChatTurn, on_delete=models.CASCADE, related_name="attachments")
    storage_uri=models.TextField()
    ingest=models.BooleanField(default=False) # True = send to Knowledge Store

class Citation(models.Model):
    id=models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    turn=models.ForeignKey(ChatTurn, on_delete=models.CASCADE, related_name="citations")
    source=models.ForeignKey(Source, on_delete=models.CASCADE)
    fragment_id=models.UUIDField()

class Feedback(models.Model):
    id=models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email=models.EmailField(blank=True, null=True)
    category=models.CharField(max_length=64)  # bug, idea, support
    body=models.TextField()
    route=models.CharField(max_length=255, blank=True, null=True)
    instrument_id=models.UUIDField(blank=True, null=True)
    last_turn_id=models.UUIDField(blank=True, null=True)
    user_agent=models.TextField(blank=True, null=True)
    status=models.CharField(max_length=16, default="open")
    admin_response=models.TextField(blank=True, null=True)
    responded_at=models.DateTimeField(blank=True, null=True)

class Connector(models.Model):
    id=models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    provider=models.CharField(max_length=32) # google_drive|sharepoint
    created_at=models.DateTimeField(auto_now_add=True)
    config_json=models.JSONField(default=dict)
