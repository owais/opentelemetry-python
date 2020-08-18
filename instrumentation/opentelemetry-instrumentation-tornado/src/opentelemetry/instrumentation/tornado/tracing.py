import functools
import inspect
import sys
import traceback
import typing

import wrapt

from opentelemetry import context, propagators, trace

# import opentracing
# from opentracing.ext import tags

# from .context_manager import tornado_context
# from ._constants import SCOPE_ATTR

_REQUEST_STARTTIME_KEY = "otel_starttime_key"
_REQUEST_SPAN_KEY = "otel_span_key"
_REQUEST_ACTIVATION_KEY = "otel_activation_key"
_REQUEST_TOKEN = "otel_token_key"


class TornadoTracing(object):
    """
    @param tracer the OpenTracing tracer to be used
    to trace requests using this TornadoTracing
    """

    def __init__(self, tracer=None, start_span_cb=None):
        if start_span_cb is not None and not callable(start_span_cb):
            raise ValueError("start_span_cb is not callable")

        self._tracer = tracer
        self._start_span_cb = start_span_cb
        self._trace_all = False
        self._trace_client = False

    @property
    def tracer(self):
        return self._tracer

    def get_span(self, request):
        """
        @param request
        Returns the span tracing this request
        """
        scope = getattr(request, SCOPE_ATTR, None)
        return None if scope is None else scope.span

    def _handle_wrapped_result(self, handler, result):
        # if it has `add_done_callback` it's a Future,
        # else, a normal method/function.
        if callable(getattr(result, "add_done_callback", None)):
            callback = functools.partial(
                self._finish_tracing_callback, handler=handler
            )
            result.add_done_callback(callback)
        else:
            self._finish_tracing(handler)

    def trace(self, *attributes):
        """
        Function decorator that traces functions
        NOTE: Must be placed before the Tornado decorators
        @param attributes any number of request attributes
        (strings) to be set as tags on the created span.
        This decorator support async functions in addition to regular ones.
        This is needed for tornado to work correctly with async handlers.
        We use a descriptor here as we need reference to the instance of the
        method being decorated which is not possible to do with a simple
        decorator.
        We don't use wrapt.decorator as it does not work uniformly with
        both async and regular functions, and we cannot selectively export
        an async or a regular decorator using wrapt as it's not possible
        to determine if the function being wrapped is async or not before
        the decorator is applied.
        """
        tracing = self

        class Descriptor(object):
            def __init__(self, wrapped):
                self.wrapped = wrapped

            async def __call__(self, handler, *args, **kwargs):
                if tracing._trace_all:
                    return self.wrapped(handler, *args, **kwargs)

                try:
                    tracing._apply_tracing(handler, list(attributes))

                    result = self.wrapped(handler, *args, **kwargs)
                    if result is not None and inspect.isawaitable(result):
                        result = await result
                    tracing._handle_wrapped_result(handler, result)

                except Exception as exc:
                    tracing._finish_tracing(
                        handler, error=exc, tb=sys.exc_info()[2]
                    )
                    raise

            def __get__(self, instance, owner):
                return functools.partial(self.__call__, instance)

        return Descriptor

    def __trace(self, *attributes):
        """
        Function decorator that traces functions
        NOTE: Must be placed before the Tornado decorators
        @param attributes any number of request attributes
        (strings) to be set as tags on the created span
        """

        @wrapt.decorator
        def wrapper(wrapped, instance, args, kwargs):
            if self._trace_all:
                return wrapped(*args, **kwargs)

            handler = instance

            with tornado_context():
                try:
                    self._apply_tracing(handler, list(attributes))

                    # Run the actual function.
                    result = wrapped(*args, **kwargs)
                    self._handle_wrapped_result(handler, result)
                except Exception as exc:
                    self._finish_tracing(
                        handler, error=exc, tb=sys.exc_info()[2]
                    )
                    raise

            return result

        return wrapper

    def _get_operation_name(self, handler):
        full_class_name = type(handler).__name__
        return full_class_name.rsplit(".")[-1]  # package-less name.

    def _finish_tracing_callback(self, future, handler):
        exc_info = future.exc_info()
        if exc_info:
            self._finish_tracing(handler, error=exc_info[1], tb=exc_info[2])
            return
        self._finish_tracing(handler)

    def _apply_tracing(self, handler, attributes):
        tracing = handler.settings.get("otel_tracing")
        if not tracing:
            return

        # operation_name = self._get_operation_name(handler)
        # headers = handler.request.headers
        request = handler.request

        token = context.attach(
            # TODO(owais): use proper propagator instead of wsgi
            propagators.extract(get_header_from_request_headers, headers)
        )

        tracer = tracing.tracer
        span = tracer.start_span(
            "span-op-name",
            kind=trace.SpanKind.SERVER,
            attributes=attributes,
            # start_time=
        )

        activation = tracer.use_span(span, end_on_exit=True)
        activation.__enter__()

        setattr(request, _REQUEST_ACTIVATION_KEY, activation)
        setattr(request, _REQUEST_TOKEN, token)
        setattr(request, _REQUEST_SPAN_KEY, span)

    def _finish_tracing(self, handler, error=None, tb=None):
        print(">>> finish tracing")
        request = handler.request

        activation = getattr(request, _REQUEST_ACTIVATION_KEY, None)
        if not activation:
            # TODO(owais): log error
            return

    def _apply_tracing_old(self, handler, attributes):
        """
        Helper function to avoid rewriting for middleware and decorator.
        Returns a new span from the request with logged attributes and
        correct operation name from the func.
        """
        operation_name = self._get_operation_name(handler)
        headers = handler.request.headers
        request = handler.request

        # start new span from trace info
        try:
            span_ctx = self._tracer.extract(
                opentracing.Format.HTTP_HEADERS, headers
            )
            scope = self._tracer.start_active_span(
                operation_name, child_of=span_ctx
            )
        except (
            opentracing.InvalidCarrierException,
            opentracing.SpanContextCorruptedException,
        ):
            scope = self._tracer.start_active_span(operation_name)

        # add span to current spans
        setattr(request, SCOPE_ATTR, scope)

        # log any traced attributes
        scope.span.set_tag(tags.COMPONENT, "tornado")
        scope.span.set_tag(tags.SPAN_KIND, tags.SPAN_KIND_RPC_SERVER)
        scope.span.set_tag(tags.HTTP_METHOD, request.method)
        scope.span.set_tag(tags.HTTP_URL, request.uri)

        for attr in attributes:
            if hasattr(request, attr):
                payload = str(getattr(request, attr))
                if payload:
                    scope.span.set_tag(attr, payload)

        # invoke the start span callback, if any
        self._call_start_span_cb(scope.span, request)

        return scope

    def _finish_tracing_old(self, handler, error=None, tb=None):
        scope = getattr(handler.request, SCOPE_ATTR, None)
        if scope is None:
            return

        delattr(handler.request, SCOPE_ATTR)

        if error is not None:
            scope.span.set_tag(tags.ERROR, True)
            scope.span.set_tag("sfx.error.message", str(error))
            scope.span.set_tag("sfx.error.object", str(error.__class__))
            scope.span.set_tag("sfx.error.kind", error.__class__.__name__)
            if tb:
                scope.span.set_tag(
                    "sfx.error.stack", "".join(traceback.format_tb(tb))
                )
        else:
            scope.span.set_tag(tags.HTTP_STATUS_CODE, handler.get_status())

        scope.close()

    def _call_start_span_cb(self, span, request):
        if self._start_span_cb is None:
            return

        try:
            self._start_span_cb(span, request)
        except Exception:
            # TODO - log the error to the Span?
            pass


'''
class AsyncTornadoTracing(BaseTornadoTracing):

    def trace(self, *attributes):
        """
        Function decorator that traces functions
        NOTE: Must be placed before the Tornado decorators
        @param attributes any number of request attributes
        (strings) to be set as tags on the created span.
        This decorator support async functions in addition to regular ones.
        This is needed for tornado to work correctly with async handlers.
        We use a descriptor here as we need reference to the instance of the
        method being decorated which is not possible to do with a simple
        decorator.
        We don't use wrapt.decorator as it does not work uniformly with
        both async and regular functions, and we cannot selectively export
        an async or a regular decorator using wrapt as it's not possible
        to determine if the function being wrapped is async or not before
        the decorator is applied.
        """
        tracing = self

        class Descriptor(object):
            def __init__(self, wrapped):
                self.wrapped = wrapped

            async def __call__(self, handler, *args, **kwargs):
                if tracing._trace_all:
                    return self.wrapped(handler, *args, **kwargs)

                try:
                    tracing._apply_tracing(handler, list(attributes))

                    result = self.wrapped(handler, *args, **kwargs)
                    if result is not None and inspect.isawaitable(result):
                        result = await result
                    tracing._handle_wrapped_result(handler, result)

                except Exception as exc:
                    tracing._finish_tracing(
                        handler, error=exc, tb=sys.exc_info()[2]
                    )
                    raise

            def __get__(self, instance, owner):
                return functools.partial(self.__call__, instance)

        return Descriptor
'''


def get_header_from_request_headers(
    headers: dict, header_name: str
) -> typing.List[str]:
    return [
        value.decode("utf8")
        for (key, value) in headers
        if key.decode("utf8") == header_name
    ]
