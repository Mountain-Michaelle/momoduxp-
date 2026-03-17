import asyncio
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from .models import ScheduledPost
from .tasks.post_tasks import send_for_approval, approval_deadline_watcher

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
    send_for_approval.delay(str(post.id))
    approval_deadline_watcher.delay()

    return JsonResponse({"post_id": post.id})
