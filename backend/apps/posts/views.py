from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from apps.api.v1.tasks.post_task import (
    trigger_approval_deadline_watcher,
    trigger_send_for_approval,
)
from .models import ScheduledPost

@csrf_exempt 
def schedule_post(request):
    content = "Text Linkedin Post with AI"

    post = ScheduledPost.objects.create(
        user_id=request.user.id,
        content=content,
        scheduled_for=timezone.now(),
        approval_deadline=timezone.now() + timezone.timedelta(minutes=1)
    )
    
    # Dispatch Celery tasks instead 
    trigger_send_for_approval(str(post.id))
    trigger_approval_deadline_watcher()

    return JsonResponse({"post_id": post.id})
