# (c) 2012-2018, Ansible by Red Hat
#
# This file is part of Ansible Galaxy
#
# Ansible Galaxy is free software: you can redistribute it and/or modify
# it under the terms of the Apache License as published by
# the Apache Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# Ansible Galaxy is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# Apache License for more details.
#
# You should have received a copy of the Apache License
# along with Galaxy.  If not, see <http://www.apache.org/licenses/>.

import logging

from rest_framework.response import Response
from django.http import Http404

from galaxy.main.models import Content

from .views import filter_role_queryset
from .base_views import ListAPIView, RetrieveAPIView
# from ..serializers import RoleListSerializer, RoleDetailSerializer
from galaxy.api import serializers

__all__ = [
    'RoleList',
    'RoleDetail'
]

logger = logging.getLogger(__name__)


# Keeping these views until Ansible < 2.5 deprecation

class RoleList(ListAPIView):
    model = Content
    serializer_class = serializers.RoleListSerializer
    throttle_scope = 'download_count'

    def list(self, request, *args, **kwargs):
        if request.query_params.get('owner__username'):
            params = {}
            for key, val in request.query_params.items():
                if key == 'owner__username':
                    params['namespace__name__iexact'] = val
                elif key == 'name':
                    params['name__iexact'] = val
                elif key not in ('page', 'page_size'):
                    params[key] = val
            qs = self.get_queryset()
            qs = qs.filter(**params)
            page = self.paginate_queryset(qs)

            if request.query_params.get('name'):
                content = qs.first()
                if content is not None:
                    content.repository.download_count += 1
                    content.repository.save()

                    name = '{}.{}'.format(
                        content.namespace.name,
                        content.repository.name
                    )

                    data = {
                        'measurement': 'content_download',
                        'fields': {
                            'content_name': name,
                            'content_id': content.repository.id,
                            'download_count': content.repository.download_count
                        }
                    }

                    serializers.influx_insert_internal(data)

            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)
            serializer = self.get_serializer(qs, many=True)
            return Response(serializer.data)
        return super().list(self, request, *args, **kwargs)

    def get_queryset(self):
        qs = super().get_queryset()
        qs = qs.prefetch_related(
            'platforms', 'tags', 'repository__versions', 'dependencies')
        return filter_role_queryset(qs)


class RoleDetail(RetrieveAPIView):
    model = Content
    serializer_class = serializers.RoleDetailSerializer

    def get_object(self, qs=None):
        obj = super().get_object()
        if not obj.is_valid or not obj.active:
            raise Http404()
        return obj
