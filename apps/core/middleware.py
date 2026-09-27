from django.http import HttpResponse

LIVENESS_PATH = "/livez/"


class LivenessMiddleware:
    """Sonde de vie : répond « ok » sans base, sans session, sans contrôle d'hôte.

    Placée en tête de MIDDLEWARE. L'hébergeur l'appelle toutes les quelques
    secondes, souvent en HTTP interne avec un en-tête Host qui lui est propre :
    elle ne doit donc ni rediriger, ni valider ALLOWED_HOSTS, ni réveiller la
    base Neon (qui consommerait alors son quota de calcul en continu).
    /healthz/ reste la sonde complète, base comprise.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path == LIVENESS_PATH and request.method in ("GET", "HEAD"):
            return HttpResponse("ok", content_type="text/plain")
        return self.get_response(request)
