# Copyright The OpenTelemetry Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
This library uses OpenTelemetry to track web requests in Tornado applications.

Usage
-----

.. code-block:: python

    TODO(owais): add example

API
---
"""

import typing
from collections import namedtuple
from functools import partial, wraps
from logging import getLogger

import tornado
from tornado.web import HTTPError
from wrapt import ObjectProxy
from wrapt import wrap_function_wrapper as _wrap

from opentelemetry import configuration, context, propagators, trace
from opentelemetry.configuration import Configuration
from opentelemetry.instrumentation.instrumentor import BaseInstrumentor
from opentelemetry.instrumentation.tornado.version import __version__
from opentelemetry.instrumentation.utils import (
    http_status_to_canonical_code,
    unwrap,
)
from opentelemetry.trace import SpanKind, get_tracer
from opentelemetry.trace.status import Status, StatusCanonicalCode
from opentelemetry.util import ExcludeList, time_ns

from . import client

_logger = getLogger(__name__)

_TraceContext = namedtuple("TraceContext", ["activation", "span", "token"])


_HANDLER_CONTEXT_KEY = "_otel_trace_context_key"

# TODO: support traced attributes


def get_excluded_urls():
    urls = configuration.Configuration().TORNADO_EXCLUDED_URLS or []
    if urls:
        urls = str.split(urls, ",")
    return ExcludeList(urls)


_excluded_urls = get_excluded_urls()


class TornadoInstrumentor(BaseInstrumentor):
    is_instrumented = False

    def _instrument(self, **kwargs):
        if self.is_instrumented:
            return

        tracer = get_tracer(__name__, __version__)

        # TODO(owais): handler that overrides `preapre` or `on_finish` should work.
        _wrap(
            "tornado.httpclient",
            "AsyncHTTPClient.fetch",
            partial(client.fetch_async, tracer),
        )
        _wrap(
            "tornado.web", "RequestHandler.prepare", partial(prepare, tracer)
        )
        _wrap(
            "tornado.web",
            "RequestHandler.log_exception",
            partial(log_exception, tracer),
        )
        _wrap(
            "tornado.web",
            "RequestHandler.on_finish",
            partial(on_finish, tracer),
        )

    def _uninstrument(self, **kwargs):
        if not self.is_instrumented:
            return

        unwrap("tornado.web", "RequestHandler.prepare")
        unwrap("tornado.web", "RequestHandler.log_exception")
        unwrap("tornado.web", "RequestHandler.on_finish")
        unwrap("tornado.httpclient", "AsyncHTTPClient.fetch")


def prepare(tracer, func, handler, args, kwargs):
    start_time = time_ns()
    request = handler.request
    if _excluded_urls.url_disabled(request.uri):
        return func(*args, **kwargs)
    start_span(tracer, handler, start_time)
    return func(*args, **kwargs)


def finish_span(tracer, handler, error=None):
    status_code = handler.get_status()
    reason = getattr(handler, "_reason")
    finish_args = (None, None, None)
    ctx = getattr(handler, _HANDLER_CONTEXT_KEY, None)

    if error:
        if isinstance(error, HTTPError):
            status_code = error.status_code
            if not ctx and status_code == 404:
                ctx = start_span(tracer, handler, time_ns())
        if status_code != 404:
            finish_args = (
                type(error),
                error,
                getattr(error, "__traceback__", None),
            )
            status_code = 500
            reason = None

    if not ctx:
        return

    if reason:
        ctx.span.set_attribute("http.status_text", reason)
    ctx.span.set_attribute("http.status_code", status_code)
    ctx.span.set_status(
        Status(
            canonical_code=http_status_to_canonical_code(status_code),
            description=reason,
        )
    )

    ctx.activation.__exit__(*finish_args)
    context.detach(ctx.token)
    delattr(handler, _HANDLER_CONTEXT_KEY)


def on_finish(tracer, func, handler, args, kwargs):
    finish_span(tracer, handler)
    return func(*args, **kwargs)


def log_exception(tracer, func, handler, args, kwargs):
    error = None
    if len(args) == 3:
        error = args[1]

    finish_span(tracer, handler, error)
    return func(*args, **kwargs)


def start_span(tracer, handler, start_time) -> _TraceContext:
    token = context.attach(
        propagators.extract(
            get_header_from_request_headers, handler.request.headers,
        )
    )
    span = tracer.start_span(
        get_operation_name(handler, handler.request),
        kind=trace.SpanKind.SERVER,
        attributes=get_attributes_from_request(handler.request),
        start_time=start_time,
    )

    activation = tracer.use_span(span, end_on_exit=True)
    activation.__enter__()
    ctx = _TraceContext(activation, span, token)
    setattr(handler, _HANDLER_CONTEXT_KEY, ctx)
    return ctx


def get_header_from_request_headers(
    headers: dict, header_name: str
) -> typing.List[str]:
    header = headers.get(header_name)
    return [header] if header else []


def get_attributes_from_request(request):
    attrs = {
        "component": "tornado",
        "http.method": request.method,
        "http.scheme": request.protocol,
        "http.host": request.host,
        "http.target": request.path,
    }

    if request.host:
        attrs["http.host"] = request.host

    if request.remote_ip:
        attrs["net.peer.ip"] = request.remote_ip

    return attrs


def get_operation_name(handler, request):
    full_class_name = type(handler).__name__
    class_name = full_class_name.rsplit(".")[-1]
    return "{0}.{1}".format(class_name, request.method.lower())
