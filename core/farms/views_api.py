from rest_framework import generics
from rest_framework.exceptions import APIException
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView
from ipware import get_client_ip
from ipware.utils import is_valid_ipv6
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.core.exceptions import ObjectDoesNotExist

from .models import Site, Coordinator, Controller, MqttMessage
from .serializers import (
    CoordinatorPingSerializer,
    CoordinatorSerializer,
    ControllerSerializer,
    ControllerPingGetSerializer,
    ControllerPingPostSerializer,
    SiteSerializer,
    MqttMessageSerializer,
)


class ExternalIPAddressNotRoutable(APIException):
    """Error that the IP address is not routable"""

    status_code = 400
    default_code = "external_ip_address_not_routable"

    def __init__(self, ip_address):
        detail = "External IP address is not routable: {}".format(ip_address)
        super().__init__(detail=detail)


class ExternalIPAddressV6(APIException):
    """Error that external ipv6 addresses are not supported"""

    status_code = 400
    default_code = "external_ip_address_v6"

    def __init__(self, ip_address):
        detail = "External IPv6 address is not supported: {}".format(ip_address)
        super().__init__(detail=detail)


class UnauthenticatedPing(APIException):
    """Error when pinging a restricted endpoint"""

    status_code = 403
    default_code = "unauthenticated_ping"

    def __init__(self, url):
        detail = "Unauthenticated ping of registered device. Use {}".format(url)
        super().__init__(detail=detail)


def get_external_ip_address(request):
    """Find the external IP address from the request"""
    # TODO: Handle IPv6 properly: http://www.steves-internet-guide.com/ipv6-guide/
    client_ip, is_routable = get_client_ip(request)
    if not is_routable and not settings.DEBUG:
        raise ExternalIPAddressNotRoutable(client_ip)
    if is_valid_ipv6(client_ip):
        raise ExternalIPAddressV6(client_ip)
    return client_ip


class APICoordinatorPingView(APIView):
    permission_classes = (AllowAny,)

    def post(self, request):
        # Find the external IP address from the request
        # TODO: Handle IPv6 properly: http://www.steves-internet-guide.com/ipv6-guide/
        client_ip, is_routable = get_client_ip(request)
        if not is_routable and not settings.DEBUG:
            error_msg = "External IP address is not routable: %s" % client_ip
            return JsonResponse(data={"error": error_msg}, status=400)

        data = request.data.copy()
        data["external_ip_address"] = client_ip

        # Serialize the request
        serializer = CoordinatorPingSerializer(data=data)
        if not serializer.is_valid():
            return JsonResponse(serializer.errors, status=400)

        # If the coordinator has been registered, only allow authenticated view
        try:
            coordinator = Coordinator.objects.get(pk=serializer.validated_data["id"])
            if coordinator.site:
                url = CoordinatorSerializer(
                    coordinator, context={"request": request}
                ).data["url"]
                raise UnauthenticatedPing(url)
        except ObjectDoesNotExist:
            pass

        serializer.save()
        return JsonResponse(serializer.data, status=201)


class APISiteListCreateView(generics.ListCreateAPIView):
    """List of your sites. Returns 404 on unauthorized access."""

    permission_classes = (IsAuthenticated,)
    serializer_class = SiteSerializer

    def get_queryset(self):
        return Site.objects.filter(owner=self.request.user)


class APISiteDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Details of one site"""

    permission_classes = (IsAuthenticated,)
    serializer_class = SiteSerializer
    http_method_names = ["get", "head", "put", "options", "delete"]

    def get_queryset(self):
        return Site.objects.filter(owner=self.request.user)


class APICoordinatorListCreateView(generics.ListCreateAPIView):
    """List of your coordinators"""

    permission_classes = (IsAuthenticated,)
    serializer_class = CoordinatorSerializer

    def get_queryset(self):
        return Coordinator.objects.filter(site__owner=self.request.user)


class APICoordinatorDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Details of one coordinator"""

    permission_classes = (IsAuthenticated,)
    serializer_class = CoordinatorSerializer
    http_method_names = ["get", "head", "put", "options", "delete"]

    def get_queryset(self):
        return Coordinator.objects.filter(site__owner=self.request.user)


class APIMqttMessageListView(generics.ListCreateAPIView):
    """List of a coordinator's MQTT messages"""

    permission_classes = (IsAuthenticated,)
    serializer_class = MqttMessageSerializer

    def get_queryset(self):
        coordinator = self.kwargs["pk"]
        return MqttMessage.objects.filter(coordinator=coordinator).order_by(
            "-created_at"
        )


class APIMqttMessageDetailView(generics.RetrieveAPIView):
    """Details of one MQTT message"""

    permission_classes = (IsAuthenticated,)
    serializer_class = MqttMessageSerializer
    queryset = MqttMessage.objects.all()

    def get_object(self):
        queryset = self.get_queryset()
        filters = {
            "coordinator": self.kwargs["pk"],
            "created_at": self.kwargs["created_at"],
        }
        obj = get_object_or_404(queryset, **filters)
        return obj


class APIControllerPingView(APIView):
    permission_classes = (AllowAny,)

    def get(self, request):
        # Extract the IP address and get the first matching coordinator
        external_ip_address = get_external_ip_address(request)

        # Return the local IP address of the coordinator or
        coordinator = Coordinator.objects.filter(
            external_ip_address=external_ip_address
        ).first()
        if coordinator:
            response = ControllerPingGetSerializer(
                {"coordinator_local_ip_address": coordinator.local_ip_address}
            )
        else:
            response = ControllerPingGetSerializer()

        return JsonResponse(response.data)

    def post(self, request):
        request_data = request.data.copy()
        request_data["external_ip_address"] = get_external_ip_address(request)

        # Serialize the request
        serializer = ControllerPingPostSerializer(data=request_data)
        if not serializer.is_valid():
            return JsonResponse(serializer.errors, status=400)

        # If the controller has been registered, only allow authenticated view
        try:
            controller = Controller.objects.get(pk=serializer.validated_data["id"])
            if controller.coordinator:
                url = ControllerSerializer(
                    controller, context={"request": request}
                ).data["url"]
                raise UnauthenticatedPing(url)
        except ObjectDoesNotExist:
            pass

        serializer.save()
        return JsonResponse(serializer.data, status=201)


class APIControllerDetailView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        return JsonResponse(
            ControllerSerializer(Controller.objects.get(pk=request.user))
        )
