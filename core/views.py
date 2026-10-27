from django.shortcuts import render


def csrf_failure(request, reason=""):
    """
    Wired up via CSRF_FAILURE_VIEW in settings.

    Django's stock CSRF page explains cross-site attack vectors to someone
    who just wants to log in. Almost every real hit is a stale token: a tab
    left open across a restart, a rebuild, or a login in another tab. Say
    that instead, and give them the reload button.
    """
    return render(request, "csrf.html", {"reason": reason}, status=403)