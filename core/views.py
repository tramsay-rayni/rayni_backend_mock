# core/views.py
import uuid, json, time, random
import os
import urllib.request

from django.http import StreamingHttpResponse, HttpResponse
from django.shortcuts import get_object_or_404
from django.db.models import Q
from django.utils.timezone import now
from django.views.decorators.csrf import csrf_exempt

from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes, renderer_classes
from rest_framework.permissions import AllowAny
from rest_framework.viewsets import ModelViewSet
from rest_framework import status
from rest_framework.renderers import BaseRenderer

from .models import *
from .serializers import *

# ---- Renderer to allow text/event-stream (SSE) ----
class EventStreamRenderer(BaseRenderer):
    media_type = "text/event-stream"
    format = "event-stream"
    charset = "utf-8"
    def render(self, data, accepted_media_type=None, renderer_context=None):
        # Not actually used because we return StreamingHttpResponse,
        # but its presence allows DRF to negotiate the Accept header.
        return data

# --- ViewSets ---
class InstrumentViewSet(ModelViewSet):
    queryset = Instrument.objects.all().order_by("name")
    serializer_class = InstrumentSerializer
    permission_classes = [AllowAny]

class FolderViewSet(ModelViewSet):
    queryset = Folder.objects.all()
    serializer_class = FolderSerializer
    permission_classes = [AllowAny]
    def list(self, request, *a, **kw):
        qs = self.queryset
        instrument = request.GET.get("instrument")
        if instrument: qs = qs.filter(instrument_id=instrument)
        return Response(FolderSerializer(qs, many=True).data)

class SourceViewSet(ModelViewSet):
    queryset = Source.objects.all().order_by("-created_at")
    serializer_class = SourceSerializer
    permission_classes = [AllowAny]
    def list(self, request, *a, **kw):
        qs = self.queryset
        instrument = request.GET.get("instrument")
        q = request.GET.get("q"); typ = request.GET.get("type"); status_f = request.GET.get("status"); folder = request.GET.get("folder")
        if instrument: qs = qs.filter(instrument_id=instrument)
        if folder: qs = qs.filter(folder_id=folder)
        if q: qs = qs.filter(Q(title__icontains=q)|Q(version__icontains=q)|Q(model_tags__icontains=q))
        if typ: qs = qs.filter(type=typ)
        if status_f: qs = qs.filter(status=status_f)
        return Response(SourceSerializer(qs, many=True).data)

class SourceVersionViewSet(ModelViewSet):
    queryset = SourceVersion.objects.all().order_by("-created_at")
    serializer_class = SourceVersionSerializer
    permission_classes = [AllowAny]

# --- Auth / Me ---
# Demo users for testing (in production, use real authentication)
DEMO_USERS = {
    "admin@rayni.com": {
        "userId": "admin",
        "email": "admin@rayni.com",
        "name": "Admin User",
        "is_admin": True,
        "role": "instrument_manager",
    },
    "user@rayni.com": {
        "userId": "user1",
        "email": "user@rayni.com",
        "name": "Regular User",
        "is_admin": False,
        "role": "trained_user",
    },
}

@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
def auth_login(request):
    """
    Demo login endpoint - accepts email and returns user info.
    In production, validate credentials properly.
    """
    email = request.data.get("email", "").lower()

    if email not in DEMO_USERS:
        return Response({"error": "User not found"}, status=400)

    user_data = DEMO_USERS[email].copy()

    # Get allowed instruments based on user role
    if user_data["is_admin"]:
        # Admins have access to all instruments
        allowed = list(Instrument.objects.values_list("id", flat=True))
    else:
        # Regular users only have access to instruments they've been granted
        grants = AccessGrant.objects.filter(
            user_id=1,  # Demo: would use real user ID in production
            status="active"
        ).values_list("instrument_id", flat=True)
        allowed = list(grants)

    user_data["allowed"] = [str(x) for x in allowed]

    # Store in session
    request.session["user"] = user_data

    return Response(user_data)

@api_view(["POST"])
@permission_classes([AllowAny])
def auth_logout(request):
    """Logout and clear session"""
    request.session.flush()
    return Response({"message": "Logged out successfully"})

@api_view(["GET"])
@permission_classes([AllowAny])
def auth_me(request):
    """Get current user info from session"""
    user = request.session.get("user")

    if not user:
        # Not logged in - return default demo user (for backward compatibility)
        inst = list(Instrument.objects.values_list("id", flat=True)[:1])
        return Response({
            "userId": "guest",
            "email": "guest@rayni.com",
            "name": "Guest User",
            "allowed": [str(x) for x in inst],
            "is_admin": False,
            "isGuest": True
        })

    # Refresh allowed instruments in case access was granted/revoked
    if user["is_admin"]:
        allowed = list(Instrument.objects.values_list("id", flat=True))
    else:
        grants = AccessGrant.objects.filter(
            user_id=1,
            status="active"
        ).values_list("instrument_id", flat=True)
        allowed = list(grants)

    user["allowed"] = [str(x) for x in allowed]
    request.session["user"] = user  # Update session

    return Response(user)

# --- Access control ---
@api_view(["POST"])
@permission_classes([AllowAny])
def request_access(request, instrument_id):
    instrument = get_object_or_404(Instrument, id=instrument_id)
    ar = AccessRequest.objects.create(user=None, instrument=instrument, reason=request.data.get("reason",""))
    return Response({"id": str(ar.id), "status":"pending"}, status=status.HTTP_202_ACCEPTED)

@api_view(["GET"])
@permission_classes([AllowAny])
def access_requests(request, instrument_id):
    data = AccessRequestSerializer(AccessRequest.objects.filter(instrument_id=instrument_id, status="pending"), many=True).data
    return Response({"items": data})

@api_view(["POST"])
@permission_classes([AllowAny])
def access_request_action(request, instrument_id, req_id, action):
    ar = get_object_or_404(AccessRequest, id=req_id, instrument_id=instrument_id)
    if action == "approve":
        ar.status = "approved"; ar.reviewed_at = now(); ar.save()
        AccessGrant.objects.get_or_create(user_id=1, instrument_id=instrument_id, defaults={"role":"trained_user"})
    elif action == "deny":
        ar.status = "denied"; ar.reviewed_at = now(); ar.save()
    else:
        return Response({"detail":"invalid action"}, status=400)
    return Response({"status": ar.status})

@api_view(["GET"])
@permission_classes([AllowAny])
def access_grants(request, instrument_id):
    items = AccessGrantSerializer(AccessGrant.objects.filter(instrument_id=instrument_id), many=True).data
    return Response({"items": items})

@api_view(["POST"])
@permission_classes([AllowAny])
def access_grant_create(request, instrument_id):
    email = request.data.get("email"); role = request.data.get("role","trained_user")
    grant = AccessGrant.objects.create(user_id=1, instrument_id=instrument_id, role=role)
    return Response(AccessGrantSerializer(grant).data, status=201)

@api_view(["PATCH"])
@permission_classes([AllowAny])
def access_grant_update(request, instrument_id, grant_id):
    g = get_object_or_404(AccessGrant, id=grant_id, instrument_id=instrument_id)
    role = request.data.get("role"); status_v = request.data.get("status")
    if role: g.role = role
    if status_v: g.status = status_v
    g.save()
    return Response(AccessGrantSerializer(g).data)

# --- Users ---
@api_view(["GET"])
@permission_classes([AllowAny])
def users_list(request):
    return Response({"items":[{"id":1,"email":"admin@example.com","is_admin":True},{"id":2,"email":"scientist@example.com","is_admin":False}]})

@api_view(["POST"])
@permission_classes([AllowAny])
def users_invite(request):
    return Response({"status":"invited","email":request.data.get("email")}, status=201)

# --- OpenAI simple completion (non-stream) with RAG ---
def _openai_complete(prompt: str, instrument_id: str = None) -> tuple:
    """
    Minimal HTTP call to OpenAI Chat Completions with RAG support.
    Reads OPENAI_API_KEY (required), OPENAI_BASE_URL and OPENAI_MODEL (optional) from env/settings.

    Returns:
        Tuple of (answer_text, citations_list)
    """
    from django.conf import settings as dj_settings
    from .rag_utils import search_sources, build_context_prompt, parse_citations_from_response

    api_key = os.environ.get("OPENAI_API_KEY") or getattr(dj_settings, "OPENAI_API_KEY", None)
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY missing")

    base_url = (os.environ.get("OPENAI_BASE_URL")
                or getattr(dj_settings, "OPENAI_BASE_URL", None)
                or "https://api.openai.com/v1").rstrip("/")
    model = (os.environ.get("OPENAI_MODEL")
             or getattr(dj_settings, "OPENAI_MODEL", None)
             or "gpt-4o-mini")

    # Search sources and get instrument context if instrument_id provided
    sources = []
    instrument_context = None
    if instrument_id:
        sources = search_sources(instrument_id, prompt, limit=5)
        # Get instrument info
        try:
            instrument = Instrument.objects.get(id=instrument_id)
            instrument_context = {
                'name': instrument.name,
                'vendor': instrument.vendor,
                'models_arr': instrument.models_arr,
                'description': instrument.description
            }
        except Instrument.DoesNotExist:
            pass
        prompt = build_context_prompt(prompt, sources, instrument_context)

    url = f"{base_url}/chat/completions"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    if "choices" not in data or not data["choices"]:
        raise RuntimeError(f"Bad OpenAI response: {data}")

    answer_text = data["choices"][0]["message"]["content"]

    # Parse citations from response
    answer_text, citations = parse_citations_from_response(answer_text, sources)

    return answer_text, citations

# --- Chat (non-stream) ---
@api_view(["POST"])
@permission_classes([AllowAny])
def chat_ask(request):
    instrument_id = request.data.get("instrument_id") or request.data.get("instrument")
    question = (request.data.get("question") or "").strip()
    if not instrument_id:
        return Response({"detail": "instrument_id is required"}, status=400)

    sess = ChatSession.objects.create(instrument_id=instrument_id)
    user_turn = ChatTurn.objects.create(session=sess, role="user", text=question)

    ans_text = None
    citations_data = []
    try:
        ans_text, citations_data = _openai_complete(question or "Say hello.", instrument_id=instrument_id)
    except Exception as e:
        ans_text = f"[LLM error: {e}]"

    if not ans_text:
        ans_text = "This is a placeholder answer. Set OPENAI_API_KEY to enable real LLM responses."

    ans_turn = ChatTurn.objects.create(session=sess, role="assistant", text=ans_text)

    # Create real citations from RAG results
    cites = []
    for cite_data in citations_data:
        source = Source.objects.filter(id=cite_data['source_id']).first()
        if source:
            # Create a fragment ID (for now, just use UUID; later can point to actual fragments)
            frag_id = uuid.uuid4()
            Citation.objects.create(turn=ans_turn, source=source, fragment_id=frag_id)
            cites.append({
                "source_id": str(source.id),
                "source_title": cite_data.get('source_title', source.title),
                "source_type": cite_data.get('source_type', source.type),
                "fragment_id": str(frag_id),
                "score": cite_data.get('score', 0.9)
            })

    return Response({"turn_id": str(ans_turn.id), "answer": ans_turn.text, "citations": cites})

# --- OpenAI streaming helper with RAG ---
def _stream_tokens_openai(question, instrument_id=None):
    """
    Stream tokens from OpenAI with RAG support.

    Args:
        question: User's question
        instrument_id: UUID of instrument for RAG context

    Yields:
        Token strings OR dict with 'citations' key at the end
    """
    from django.conf import settings
    from .rag_utils import search_sources, build_context_prompt, parse_citations_from_response
    import os
    try:
        from openai import OpenAI
        import httpx

        api_key = os.environ.get("OPENAI_API_KEY") or getattr(settings, "OPENAI_API_KEY", None)
        base_url = (os.environ.get("OPENAI_BASE_URL") or
                    getattr(settings, "OPENAI_BASE_URL", None) or
                    "https://api.openai.com/v1")
        model = (os.environ.get("OPENAI_MODEL") or
                 getattr(settings, "OPENAI_MODEL", None) or
                 "gpt-4o-mini")

        if not api_key:
            yield "[OpenAI error: OPENAI_API_KEY not set]"
            return

        # Search sources and get instrument context if instrument_id provided
        sources = []
        instrument_context = None
        if instrument_id:
            sources = search_sources(instrument_id, question, limit=5)
            # Get instrument info
            try:
                instrument = Instrument.objects.get(id=instrument_id)
                instrument_context = {
                    'name': instrument.name,
                    'vendor': instrument.vendor,
                    'models_arr': instrument.models_arr,
                    'description': instrument.description
                }
            except Instrument.DoesNotExist:
                pass
            question = build_context_prompt(question, sources, instrument_context)

        # Create custom httpx client without proxy support to avoid initialization errors
        http_client = httpx.Client(timeout=60.0)

        client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            http_client=http_client
        )

        stream = client.chat.completions.create(
            model=model,
            messages=[{"role":"user","content":question}],
            stream=True
        )

        full_text = ""
        for chunk in stream:
            delta = chunk.choices[0].delta.content or ""
            if delta:
                full_text += delta
                yield delta

        http_client.close()

        # Parse citations after streaming complete
        _, citations = parse_citations_from_response(full_text, sources)
        yield {"citations": citations}

    except Exception as e:
        yield f"[OpenAI error: {e}]"

# --- Chat (SSE stream) WITHOUT DRF negotiation ---
from django.views.decorators.http import require_GET
from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
@require_GET
def chat_stream(request):
    question = request.GET.get("q", "")
    instrument_id = request.GET.get("instrument_id")

    # create session + user turn
    sess = ChatSession.objects.create(instrument_id=instrument_id)
    user_turn = ChatTurn.objects.create(session=sess, role="user", text=question)

    def gen():
        # tell client which turn this is
        yield "event: start\n"
        yield f"data: {json.dumps({'turn_id': str(user_turn.id)})}\n\n"

        text_accum = ""
        citations_data = []

        from django.conf import settings
        if getattr(settings, "OPENAI_API_KEY", None):
            for tok in _stream_tokens_openai(question, instrument_id=instrument_id):
                if not tok:
                    continue

                # Check if this is a citations dict (sent at the end)
                if isinstance(tok, dict) and 'citations' in tok:
                    citations_data = tok['citations']
                    continue

                # Regular token
                text_accum += tok
                yield "event: token\n"
                yield f"data: {json.dumps({'t': tok})}\n\n"
        else:
            # mock tokens if no key
            for tok in ["Working ", "through ", "your ", "question...", " Done."]:
                time.sleep(0.15)
                text_accum += tok
                yield "event: token\n"
                yield f"data: {json.dumps({'t': tok})}\n\n"

        # finalize and create assistant turn
        ans_turn = ChatTurn.objects.create(session=user_turn.session, role="assistant", text=text_accum)

        # Create real citations from RAG results
        cites = []
        for cite_data in citations_data:
            source = Source.objects.filter(id=cite_data['source_id']).first()
            if source:
                frag_id = uuid.uuid4()
                Citation.objects.create(turn=ans_turn, source=source, fragment_id=frag_id)
                cites.append({
                    "source_id": str(source.id),
                    "source_title": cite_data.get('source_title', source.title),
                    "source_type": cite_data.get('source_type', source.type),
                    "fragment_id": str(frag_id),
                    "score": cite_data.get('score', 0.9)
                })

        yield "event: done\n"
        yield f"data: {json.dumps({'turn_id': str(ans_turn.id), 'citations': cites})}\n\n"

    resp = StreamingHttpResponse(gen(), content_type="text/event-stream")
    # help the browser/proxies treat it as a live stream
    resp["Cache-Control"] = "no-cache"
    resp["X-Accel-Buffering"] = "no"
    # CORS is handled by corsheaders middleware (settings.py)
    # Do NOT set Access-Control-Allow-Origin here as it conflicts with credentials mode
    return resp
@api_view(["POST"])
@permission_classes([AllowAny])
def chat_attach(request):
    """
    Handle chat with file attachments.
    Extracts text from files and includes in context.
    """
    # Parse form data
    instrument_id = request.POST.get("instrument_id") or request.data.get("instrument_id")
    question = (request.POST.get("question") or request.data.get("question") or "").strip()
    files = request.FILES.getlist("files")

    if not instrument_id:
        return Response({"detail": "instrument_id is required"}, status=400)

    try:
        sess = ChatSession.objects.create(instrument_id=instrument_id)
        user_turn = ChatTurn.objects.create(session=sess, role="user", text=question)

        # Extract text from attached files
        attachment_texts = []
        for file in files:
            try:
                file_bytes = file.read()
                if file.name.lower().endswith('.pdf'):
                    from .rag_utils import extract_text_from_pdf
                    text = extract_text_from_pdf(file_bytes)
                    if text:
                        attachment_texts.append(f"[Attachment: {file.name}]\n{text[:2000]}")  # Limit per file
                    else:
                        attachment_texts.append(f"[Attachment: {file.name}] (No text extracted)")
                else:
                    # Try to decode as text
                    try:
                        text = file_bytes.decode('utf-8')
                        attachment_texts.append(f"[Attachment: {file.name}]\n{text[:2000]}")
                    except:
                        attachment_texts.append(f"[Attachment: {file.name}] (Binary file - cannot extract text)")
            except Exception as e:
                print(f"Error processing file {file.name}: {e}")
                attachment_texts.append(f"[Attachment: {file.name}] (Error: {str(e)})")

        # Build enhanced prompt with attachments
        enhanced_question = question
        if attachment_texts:
            enhanced_question = f"{question}\n\nUser has attached the following documents for context:\n" + "\n\n".join(attachment_texts)

        ans_text = None
        citations_data = []
        try:
            ans_text, citations_data = _openai_complete(enhanced_question, instrument_id=instrument_id)
        except Exception as e:
            print(f"OpenAI error: {e}")
            ans_text = f"[LLM error: {e}]"

        if not ans_text:
            ans_text = "This is a placeholder answer. Set OPENAI_API_KEY to enable real LLM responses."

        ans_turn = ChatTurn.objects.create(session=sess, role="assistant", text=ans_text)

        # Create citations
        cites = []
        for cite_data in citations_data:
            source = Source.objects.filter(id=cite_data['source_id']).first()
            if source:
                frag_id = uuid.uuid4()
                Citation.objects.create(turn=ans_turn, source=source, fragment_id=frag_id)
                cites.append({
                    "source_id": str(source.id),
                    "source_title": cite_data.get('source_title', source.title),
                    "source_type": cite_data.get('source_type', source.type),
                    "fragment_id": str(frag_id),
                    "score": cite_data.get('score', 0.9)
                })

        return Response({"turn_id": str(ans_turn.id), "answer": ans_turn.text, "citations": cites})

    except Exception as e:
        print(f"chat_attach error: {e}")
        import traceback
        traceback.print_exc()
        return Response({"detail": f"Error processing request: {str(e)}"}, status=500)

@api_view(["POST"])
@permission_classes([AllowAny])
def chat_regen(request, turn_id):
    t = get_object_or_404(ChatTurn, id=turn_id)
    t.text = t.text + " (regenerated)"
    t.save()
    return Response({"turn_id": str(t.id), "answer": t.text})

@api_view(["POST"])
@permission_classes([AllowAny])
def chat_turn_feedback(request, turn_id):
    t = get_object_or_404(ChatTurn, id=turn_id)
    t.rating = request.data.get("rating"); t.feedback_tag = request.data.get("tag"); t.save()
    return Response({"status":"ok"})

@api_view(["GET"])
@permission_classes([AllowAny])
def citations_for_turn(request, turn_id):
    cites = Citation.objects.filter(turn_id=turn_id)
    out = [{"source_id":str(c.source_id), "fragment_id":str(c.fragment_id), "score":0.8} for c in cites]
    return Response({"items": out})

# --- Support & Feedback ---
@api_view(["GET"])
@permission_classes([AllowAny])
def faq(request):
    data = [
        {"id":"upload","q":"How do I upload documents?","a":"Go to Knowledge Store → Upload. Supported: PDF, video, images, notes."},
        {"id":"access","q":"How do I request access?","a":"Open the instrument and click Request Access; you’ll get an email when approved."},
        {"id":"citations","q":"How do I verify an answer?","a":"Click a citation chip to open the Proof Viewer at the exact fragment."},
        {"id":"contact","q":"How do I contact support?","a":"Open the help widget, or email support@rayni.ai."},
    ]
    return Response({"items": data})

@api_view(["GET"])
@permission_classes([AllowAny])
def feedback_list(request):
    items = FeedbackSerializer(Feedback.objects.all().order_by("-created_at"), many=True).data
    return Response({"items": items})

@api_view(["POST"])
@permission_classes([AllowAny])
def feedback_submit(request):
    fb = Feedback.objects.create(
        email=request.data.get("email"),
        category=request.data.get("category","support"),
        body=request.data.get("body",""),
        route=request.data.get("route"),
        instrument_id=request.data.get("instrument_id"),
        last_turn_id=request.data.get("last_turn_id"),
        user_agent=request.META.get("HTTP_USER_AGENT"),
    )
    return Response(FeedbackSerializer(fb).data, status=201)

@api_view(["POST"])
@permission_classes([AllowAny])
def feedback_respond(request, fb_id):
    fb = get_object_or_404(Feedback, id=fb_id)
    fb.admin_response = request.data.get("response","")
    fb.status = "closed"; fb.responded_at = now(); fb.save()
    return Response(FeedbackSerializer(fb).data)

# --- Uploads ---
@api_view(["POST"])
@permission_classes([AllowAny])
def uploads_initiate(request):
    upload_id = uuid.uuid4()
    return Response({"upload_id": str(upload_id), "signed_url": f"http://localhost:9000/bucket/{upload_id}", "headers": {"x-amz-acl":"private"}}, status=201)

@api_view(["PATCH"])
@permission_classes([AllowAny])
def uploads_complete(request, upload_id):
    instrument_id = request.data.get("instrument_id")
    folder_id = request.data.get("folder_id")
    s = Source.objects.create(
        instrument_id=instrument_id,
        folder_id=folder_id,
        type=request.data.get("type", "pdf"),
        title=request.data.get("title", "Uploaded File"),
        category=request.data.get("category"),
        description=request.data.get("description"),
        version=request.data.get("version"),
        model_tags=request.data.get("model_tags", []),
        storage_uri=f"minio://{upload_id}",
        status="uploaded"
    )
    return Response({"source_id": str(s.id), "status": s.status})

# --- Connectors scaffold ---
@api_view(["GET"])
@permission_classes([AllowAny])
def connectors_list(request):
    return Response({"items": ConnectorSerializer(Connector.objects.all(), many=True).data})

@api_view(["POST"])
@permission_classes([AllowAny])
def connectors_create(request):
    c = Connector.objects.create(provider=request.data.get("provider","google_drive"), config_json=request.data.get("config",{}))
    return Response(ConnectorSerializer(c).data, status=201)

@api_view(["POST"])
@permission_classes([AllowAny])
def connectors_sync(request, conn_id):
    return Response({"status":"scheduled"}, status=202)

# --- Archive endpoint (admin-only) ---
@api_view(["PATCH"])
@permission_classes([AllowAny])
def archive_source(request, source_id):
    source = get_object_or_404(Source, id=source_id)
    source.archived = True
    source.archived_at = now()
    source.status = "archived"
    source.save()
    return Response(SourceSerializer(source).data)

# --- Viewer meta endpoints (used by frontend to draw highlights) ---
@api_view(["GET"])
@permission_classes([AllowAny])
def viewer_pdf_meta(request, source_id):
    return Response({"type":"pdf","page":1,"bbox":{"x":120,"y":200,"w":260,"h":40},"filename":"manual.pdf","version":"v3.1","checksum":"abc123"})

@api_view(["GET"])
@permission_classes([AllowAny])
def viewer_video_meta(request, source_id):
    return Response({"type":"video","t_start":12.4,"t_end":22.0,"transcript":[{"t":10,"text":"Intro"}, {"t":12.4,"text":"Load flow cell (highlight)"},{"t":23,"text":"Next step"}]})

@api_view(["GET"])
@permission_classes([AllowAny])
def viewer_image_meta(request, source_id):
    return Response({"type":"image","region":{"x":40,"y":60,"w":180,"h":120},"alt_text":"Latch mechanism area"})
