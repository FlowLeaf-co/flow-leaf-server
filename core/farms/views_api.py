from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from ipware import get_client_ip
from ipware.utils import is_valid_ipv6
from rest_framework import generics
from rest_framework.exceptions import APIException
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView

from .models import (
    Controller,
    ControllerTask,
    ControllerMessage,
    Coordinator,
    MqttMessage,
    PeripheralComponent,
    Site,
    SiteEntity,
)
from .permissions import ControllerAPIPermission
from .serializers import (
    ControllerMessageSerializer,
    ControllerPingGetSerializer,
    ControllerPingPostSerializer,
    ControllerSerializer,
    CoordinatorPingSerializer,
    CoordinatorSerializer,
    MqttMessageSerializer,
    SiteSerializer,
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
    permission_classes = (
        IsAuthenticated,
        ControllerAPIPermission,
    )

    def get(self, request, pk):
        controller = Controller.objects.get(id=pk)
        self.check_object_permissions(request, controller)
        return JsonResponse(
            ControllerSerializer(controller, context={"request": request}).data
        )


class APIControllerCommandView(APIView):
    permission_classes = (
        IsAuthenticated,
        ControllerAPIPermission,
    )

    def post(self, request, pk):
        """Send a command to a controller"""
        
        # Check if the controller from the URL exists
        entity_query = SiteEntity.objects.select_related("controller_component")
        entity = get_object_or_404(entity_query, pk=pk)

        # Check if the user has permission to interact with the controller
        self.check_object_permissions(request, entity)

        # Check that the controller has once connected
        if not entity.controller_component.channel_name:
            return JsonResponse({"message": ["Controller channel not set"]}, status=400)

        # Parse the data into a ControllerMessage
        serializer = ControllerMessageSerializer(
            data={
                "message": {
                    **request.data,
                },
                "request_id": request.id,
                "controller": entity.controller_component.id,
            }
        )
        if not serializer.is_valid():
            return JsonResponse(serializer.errors, status=400)
        message = serializer.save()

        # Extract peripheral and task commands from the message
        try:
            peripherals = PeripheralComponent.objects.from_commands(
                message.to_peripheral_commands(), message.controller
            )
            controller_tasks = ControllerTask.objects.from_commands(
                message.to_task_commands(), message.controller
            )
        except ValueError as err:
            return JsonResponse({"message": [str(err)]}, status=400)

        # Forward the verified commands to the controller
        channel_layer = get_channel_layer()
        peripheral_commands = PeripheralComponent.to_commands(peripherals)
        task_commands = ControllerTask.to_commands(controller_tasks)
        if peripheral_commands:
            async_to_sync(channel_layer.send)(
                entity.controller_component.channel_name,
                {
                    "type": "send.peripheral.commands",
                    "commands": peripheral_commands,
                    "request_id": message.request_id,
                },
            )
        if task_commands:
            async_to_sync(channel_layer.send)(
                entity.controller_component.channel_name,
                {
                    "type": "send.controller.task.commands",
                    "commands": task_commands,
                    "request_id": message.request_id,
                },
            )

        return JsonResponse(
            ControllerMessage.to_command_message(
                peripheral_commands=peripheral_commands,
                task_commands=task_commands,
                request_id=message.request_id,
            )
        )
