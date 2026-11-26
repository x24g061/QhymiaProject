DEBUG_MODE_SESSION_KEY = "debug_mode"
DEBUG_DROP_RATE_SESSION_KEY = "debug_drop_rate"

DEFAULT_DEBUG_DROP_RATE = 100


def is_debug_mode(request):
    return bool(
        request.session.get(
            DEBUG_MODE_SESSION_KEY,
            False,
        )
    )


def enable_debug_mode(request):

    request.session[
        DEBUG_MODE_SESSION_KEY
    ] = True

    request.session.setdefault(
        DEBUG_DROP_RATE_SESSION_KEY,
        DEFAULT_DEBUG_DROP_RATE,
    )


def disable_debug_mode(request):

    request.session.pop(
        DEBUG_MODE_SESSION_KEY,
        None,
    )

    request.session.pop(
        DEBUG_DROP_RATE_SESSION_KEY,
        None,
    )


def get_debug_drop_rate(request):

    if not is_debug_mode(request):
        return None

    return request.session.get(
        DEBUG_DROP_RATE_SESSION_KEY,
        DEFAULT_DEBUG_DROP_RATE,
    )


def set_debug_drop_rate(
    request,
    value,
):

    value = int(value)

    value = max(
        0,
        min(100, value),
    )

    request.session[
        DEBUG_DROP_RATE_SESSION_KEY
    ] = value

    return value