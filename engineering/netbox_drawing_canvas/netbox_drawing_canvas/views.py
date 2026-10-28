import json

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.decorators.http import require_http_methods

from utilities.views import register_model_view

from .forms import DrawingForm
from .models import Drawing
from .services import RevisionConflict, drawings_for, equipment_for, save_scene


@login_required
@require_http_methods(['GET', 'POST'])
def drawing_list(request):
    form = DrawingForm(request.POST or None, user=request.user)
    if request.method == 'POST':
        if not request.user.has_perm('netbox_drawing_canvas.add_drawing'):
            raise PermissionDenied
        if form.is_valid():
            with transaction.atomic():
                drawing = form.save()
                # NetBox evaluates constraints against the saved row, inside this rollback boundary.
                if not request.user.has_perm('netbox_drawing_canvas.add_drawing', drawing):
                    raise PermissionDenied
            return redirect(drawing)
    return render(request, 'netbox_drawing_canvas/list.html', {
        'drawings': drawings_for(request.user), 'form': form,
        'can_add': request.user.has_perm('netbox_drawing_canvas.add_drawing'),
    })


@login_required
@require_http_methods(['GET'])
def drawing(request, pk):
    obj = get_object_or_404(drawings_for(request.user), pk=pk)
    return render(request, 'netbox_drawing_canvas/canvas.html', {
        'drawing': obj, 'editable': drawings_for(request.user, 'change').filter(pk=pk).exists(),
    })


@login_required
@require_http_methods(['GET', 'POST'])
def scene(request, pk):
    obj = get_object_or_404(drawings_for(request.user), pk=pk)
    if request.method == 'POST':
        try:
            if len(request.body) > 256000:
                raise ValidationError('Scene request exceeds 256 KB.')
            data = json.loads(request.body)
            if not isinstance(data, dict) or set(data) != {'revision', 'scene', 'state'}:
                raise ValidationError('Expected revision, scene and state.')
            obj = save_scene(request.user, pk, data['revision'], data['scene'], data['state'])
        except (ValueError, UnicodeDecodeError):
            return JsonResponse({'error': 'Invalid JSON.'}, status=400)
        except ValidationError as exc:
            return JsonResponse({'error': '; '.join(exc.messages)}, status=400)
        except RevisionConflict:
            return JsonResponse({'error': 'Another editor saved this sheet. Reload before editing again.'}, status=409)
    # Never expose object IDs whose permissions or tenant assignments have changed since the last save.
    visible = {kind: set(equipment_for(request.user, obj, kind).values_list('pk', flat=True))
               for kind in ('device', 'rack')}
    items = obj.scene['appearances']
    if any(item['object_id'] not in visible[item['kind']] for item in items):
        return JsonResponse(
            {'error': 'This sheet references unavailable equipment. Ask an administrator to repair it.'}, status=403
        )
    return JsonResponse({'revision': obj.revision, 'scene': obj.scene, 'state': obj.state})


@login_required
@require_http_methods(['GET'])
def equipment(request, pk):
    obj = get_object_or_404(drawings_for(request.user), pk=pk)
    kind = request.GET.get('kind', 'device')
    if kind not in ('device', 'rack'):
        return JsonResponse({'error': 'Invalid equipment kind.'}, status=400)
    queryset = equipment_for(request.user, obj, kind)
    object_id = request.GET.get('object_id')
    if object_id:
        if not object_id.isdecimal() or len(object_id) > 18:
            return JsonResponse({'error': 'Invalid object ID.'}, status=400)
        item = get_object_or_404(queryset, pk=int(object_id))
        # Detail pages enforce their own field/component permissions; don't serialize unrestricted relations here.
        return JsonResponse({'id': item.pk, 'kind': kind, 'name': str(item), 'url': item.get_absolute_url()})
    query = request.GET.get('q', '')[:100]
    rows = queryset.filter(name__icontains=query).order_by('name', 'pk')[:100]
    return JsonResponse({'results': [{'id': item.pk, 'kind': kind, 'name': str(item)} for item in rows]})


@register_model_view(Drawing, 'list', detail=False)
class DrawingListView(View):
    def get(self, request):
        return drawing_list(request)

    def post(self, request):
        return drawing_list(request)


@register_model_view(Drawing)
class DrawingView(View):
    def get(self, request, pk):
        return drawing(request, pk)
