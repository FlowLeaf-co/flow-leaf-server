from django.conf import settings
from django.http import JsonResponse
from django.core.exceptions import ObjectDoesNotExist
from ipware import get_client_ip
from rest_framework.parsers import JSONParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import render
from django.views.generic.base import View

from .models import Farm, Coordinator, HydroponicSystem, Controller
from .serializers import (
    FarmSerializer,
    AddressSerializer,
    CoordinatorSerializer,
    CoordinatorPingSerializer,
    HydroponicSystemSerializer,
    ControllerSerializer,
)


class FarmDetailView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        pass


class CoordinatorSetupView(View):
    def get(self, request, *args, **kwargs):
        context = {}

        client_ip, is_routable = get_client_ip(request)
        if not is_routable and not settings.DEBUG:
            context["error"] = (
                "Sorry, your external IP address can not be used for a lookup: %s"
                % client_ip
            )
            return render(request, "farms/setup.html", context=context)

        coordinators = Coordinator.objects.filter(external_ip_address=client_ip)
        context["unregistered_coordinators"] = sorted(
            filter(lambda coordinator: not coordinator.farm, coordinators),
            key=lambda coordinator: coordinator.modified_at,
        )
        context["registered_coordinators"] = sorted(
            filter(lambda coordinator: coordinator.farm, coordinators),
            key=lambda coordinator: coordinator.modified_at,
        )
        return render(request, "farms/setup.html", context=context)


class CoordinatorPingView(APIView):
    permission_classes = (AllowAny,)

    def post(self, request):
        # Find the external IP address from the request
        # TODO: Handle IPv6 properly: http://www.steves-internet-guide.com/ipv6-guide/
        client_ip, is_routable = get_client_ip(request)
        if not is_routable and not settings.DEBUG:
            error_msg = "External IP address is not routable: %s" % client_ip
            return JsonResponse(data={"error": error_msg}, status=400)
        else:
            data = request.data.copy()
            data["external_ip_address"] = client_ip

        # Serialize the request
        serializer = CoordinatorPingSerializer(data=data)
        if not serializer.is_valid():
            return JsonResponse(serializer.errors, status=400)

        # If the coordinator has been registered, only allow authenticated view
        try:
            coordinator = Coordinator.objects.get(pk=serializer.validated_data["id"])
            if coordinator.farm:
                coordinator_url = CoordinatorSerializer(
                    coordinator, context={"request": request}
                ).data["url"]
                error_msg = (
                    "Coordinator has been registered. Use the detail URL: %s"
                    % coordinator_url
                )
                return JsonResponse(data={"error": error_msg}, status=403)
        except ObjectDoesNotExist:
            pass

        serializer.save()
        return JsonResponse(serializer.data, status=201)


class CoordinatorDetailView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        pass

