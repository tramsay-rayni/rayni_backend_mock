from django.contrib import admin
from django.urls import path, include, re_path
from rest_framework.routers import DefaultRouter
from core.views import (
    InstrumentViewSet, FolderViewSet, SourceViewSet, SourceVersionViewSet,
    request_access, auth_me,
    chat_ask, chat_stream, chat_regen, chat_turn_feedback,
    citations_for_turn,
    faq, feedback_list, feedback_submit, feedback_respond,
    uploads_initiate, uploads_complete,
    users_list, users_invite, access_requests, access_request_action, access_grants, access_grant_create, access_grant_update,
    connectors_list, connectors_create, connectors_sync,
    viewer_pdf_meta, viewer_video_meta, viewer_image_meta,
)
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

router=DefaultRouter()
router.register(r"instruments", InstrumentViewSet, basename="instrument")
router.register(r"folders", FolderViewSet, basename="folder")
router.register(r"sources", SourceViewSet, basename="source")
router.register(r"source-versions", SourceVersionViewSet, basename="sourceversion")

urlpatterns=[
 path("admin/", admin.site.urls),
 # SSE stream endpoint - must be BEFORE api/ to avoid DRF content negotiation
 path("stream/chat", chat_stream),
 path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
 path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
 path("api/", include(router.urls)),
 # auth / me
 path("api/auth/me", auth_me),
 # access
 path("api/instruments/<uuid:instrument_id>/request-access", request_access),
 path("api/instruments/<uuid:instrument_id>/access/requests", access_requests),
 path("api/instruments/<uuid:instrument_id>/access/requests/<uuid:req_id>/<str:action>", access_request_action),  # approve|deny
 path("api/instruments/<uuid:instrument_id>/access/grants", access_grants),
 path("api/instruments/<uuid:instrument_id>/access/grants/create", access_grant_create),
 path("api/instruments/<uuid:instrument_id>/access/grants/<uuid:grant_id>", access_grant_update),
 # chat
 path("api/chat/ask", chat_ask),
 path("api/chat/turns/<uuid:turn_id>/regenerate", chat_regen),
 path("api/chat/turns/<uuid:turn_id>/feedback", chat_turn_feedback),
 path("api/chat/turns/<uuid:turn_id>/citations", citations_for_turn),
 # support
 path("api/support/faq", faq),
 path("api/support/feedback", feedback_submit),
 path("api/support/feedback/list", feedback_list),
 path("api/support/feedback/<uuid:fb_id>/respond", feedback_respond),
 # uploads
 path("api/uploads/initiate", uploads_initiate),
 path("api/uploads/<uuid:upload_id>/complete", uploads_complete),
 # users
 path("api/users", users_list),
 path("api/users/invite", users_invite),
 # connectors (scaffold)
 path("api/connectors", connectors_list),
 path("api/connectors/create", connectors_create),
 path("api/connectors/<uuid:conn_id>/sync", connectors_sync),
 # viewer meta
 path("api/viewer/pdf/<uuid:source_id>", viewer_pdf_meta),
 path("api/viewer/video/<uuid:source_id>", viewer_video_meta),
 path("api/viewer/image/<uuid:source_id>", viewer_image_meta),
]
