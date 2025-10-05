from rest_framework import serializers
from .models import (
    Instrument, Folder, Source, SourceVersion, PDFFragment, VideoFragment, ImageFragment,
    AccessGrant, AccessRequest, ChatSession, ChatTurn, Attachment, Citation, Feedback, Connector
)

class InstrumentSerializer(serializers.ModelSerializer):
    class Meta: model=Instrument; fields="__all__"

class FolderSerializer(serializers.ModelSerializer):
    class Meta: model=Folder; fields="__all__"

class SourceSerializer(serializers.ModelSerializer):
    class Meta: model=Source; fields="__all__"

class SourceVersionSerializer(serializers.ModelSerializer):
    class Meta: model=SourceVersion; fields="__all__"

class ChatTurnSerializer(serializers.ModelSerializer):
    class Meta: model=ChatTurn; fields="__all__"

class ChatSessionSerializer(serializers.ModelSerializer):
    turns=ChatTurnSerializer(many=True, read_only=True)
    class Meta: model=ChatSession; fields=("id","instrument","owner_email","title","share_token","created_at","turns")

class FeedbackSerializer(serializers.ModelSerializer):
    class Meta: model=Feedback; fields="__all__"

class AccessRequestSerializer(serializers.ModelSerializer):
    class Meta: model=AccessRequest; fields="__all__"

class AccessGrantSerializer(serializers.ModelSerializer):
    class Meta: model=AccessGrant; fields="__all__"

class ConnectorSerializer(serializers.ModelSerializer):
    class Meta: model=Connector; fields="__all__"
