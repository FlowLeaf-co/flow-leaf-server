from oauth2_provider.views.generic import ScopedProtectedResourceView

def index(request):
    return render(request, 'homepage.html')

class UserInfo(ScopedProtectedResourceView):
    required_scopes = ['userinfo-v1']

    def get(self, request, *args, **kwargs):
      return JsonResponse({'name':'Grafana Auth', 'email':'grafana@test.com'})