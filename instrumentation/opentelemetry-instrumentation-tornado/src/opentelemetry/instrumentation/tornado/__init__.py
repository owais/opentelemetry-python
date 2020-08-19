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

import inspect
import typing
from collections import namedtuple
from functools import partial
from logging import getLogger

import tornado.web
from tornado.routing import Rule
from wrapt import wrap_function_wrapper as _wrap
import wrapt

from opentelemetry import configuration, context, propagators, trace
from opentelemetry.instrumentation.instrumentor import BaseInstrumentor
from opentelemetry.instrumentation.tornado.version import __version__
from opentelemetry.instrumentation.utils import (
    http_status_to_canonical_code,
    unwrap,
)
from opentelemetry.trace.status import Status
from opentelemetry.util import ExcludeList, time_ns

from . import client

_logger = getLogger(__name__)

_TraceContext = namedtuple("TraceContext", ["activation", "span", "token"])


_OTEL_PATCHED_KEY = '_ptel_is_patched'
_HANDLER_CONTEXT_KEY = "_otel_trace_context_key"

# TODO: support traced attributes


def get_excluded_urls():
    urls = configuration.Configuration().TORNADO_EXCLUDED_URLS or []
    if urls:
        urls = str.split(urls, ",")
    return ExcludeList(urls)


_excluded_urls = get_excluded_urls()


class TornadoInstrumentor(BaseInstrumentor):
    patched_handlers = []
    original_handler_new = None

    def _instrument(self, **kwargs):
        tracer = trace.get_tracer(__name__, __version__)

        def new_request(cls, *args, **kwargs):
            patch_handler_class(tracer, cls)
            self.patched_handlers.append(cls)
            return cls.__otel_orig_new__(cls)

        if hasattr(tornado.web.RequestHandler, '__otel_orig_new__'):
            return

        tornado.web.RequestHandler.__otel_orig_new__ = tornado.web.RequestHandler.__new__
        tornado.web.RequestHandler.__new__ = staticmethod(new_request)
        _wrap("tornado.httpclient", "AsyncHTTPClient.fetch", partial(client.fetch_async, tracer))

        #_wrap("tornado.httpclient", "AsyncHTTPClient.fetch", partial(client.fetch_async, tracer))
        #_wrap("tornado.web", "Application.__init__", partial(app_init, tracer, self._on_patch))
        #_wrap("tornado.web", "Application.add_handlers", partial(app_add_handlers, tracer))
        #patch_handler_class(tracer, tornado.web.ErrorHandler)

    def _uninstrument(self, **kwargs):
        unwrap(tornado.httpclient.AsyncHTTPClient, "fetch")

        def new_request(cls, *args, **kwargs):
            return cls.__otel_orig_new__(cls)

        tornado.web.RequestHandler.__new__ = staticmethod(new_request)

        for handler_class in self.patched_handlers:
            unpatch_handler_class(handler_class)
        self.patched_handlers = []
        # TODO(owais): iterate over all patched handlers and unpatch them




class TornadoRoutingInstrumentor(BaseInstrumentor):
    is_instrumented = False
    patched_apps = []

    def _instrument(self, **kwargs):
        if self.is_instrumented:
            return

        self.is_instrumented = True
        tracer = trace.get_tracer(__name__, __version__)

        _wrap("tornado.httpclient", "AsyncHTTPClient.fetch", partial(client.fetch_async, tracer))
        _wrap("tornado.web", "Application.__init__", partial(app_init, tracer, self._on_patch))
        _wrap("tornado.web", "Application.add_handlers", partial(app_add_handlers, tracer))
        patch_handler_class(tracer, tornado.web.ErrorHandler)

    def _on_patch(self, app):
        self.patched_apps.append(app)

    def _uninstrument(self, **kwargs):
        if not self.is_instrumented:
            return

        unwrap(tornado.web.Application, "__init__")
        unpatch_handler_class(tornado.web.ErrorHandler)
        for app in self.patched_apps:
            unpatch_app(app)
        self.patched_apps = []
        # TODO(owais): find patched application routers and unpatch all their 
        # registered routes


def app_add_handlers(tracer, func, app, args, kwargs):
    handlers = args[1]
    apply_func_on_handlers(partial(patch_handler_class, tracer), handlers)
    return func(*args, **kwargs)


def app_init(tracer, on_patch, func, app, args, kwargs):
    func(*args, **kwargs)
    on_patch(app)
    apply_func_on_handlers(partial(patch_handler_class, tracer), app.wildcard_router.rules)
    apply_func_on_handlers(partial(patch_handler_class, tracer), app.default_router.rules)


def unpatch_app(app):
    apply_func_on_handlers(unpatch_handler_class, app.default_router.rules)
    apply_func_on_handlers(unpatch_handler_class, app.wildcard_router.rules)


def patch_handler_class(tracer, handler_class):
    if getattr(handler_class, '_otel_patched', False):
        return
    print('>> patching:: ', handler_class)
    setattr(handler_class, '_otel_patched', True)
    mod = handler_class.__module__
    name = handler_class.__name__
    _wrap(mod, '{0}.{1}'.format(name, 'prepare'), partial(prepare, tracer))
    _wrap(mod, '{0}.{1}'.format(name, 'on_finish'), partial(on_finish, tracer))
    _wrap(mod, '{0}.{1}'.format(name, 'log_exception'), partial(log_exception, tracer))


def unpatch_handler_class(handler_class):
    if not getattr(handler_class, '_otel_patched', False):
        return
    print('<< unpatching:: ', handler_class)
    mod = handler_class.__module__
    name = handler_class.__name__

    unwrap(handler_class, 'prepare')
    unwrap(handler_class, 'on_finish')
    unwrap(handler_class, 'log_exception')

    delattr(handler_class, '_otel_patched')


def apply_func_on_handlers(func, rules):
    # TODO(owais): test and support complex and nested routes
    # print(rules)
    if isinstance(rules, (tuple, list)):
        for rule in rules:
            apply_func_on_handlers(func, rule)
        return
    rule = rules
    if isinstance(rule, Rule):
        apply_func_on_handlers(func, rule.target)
        return
        #if isinstance(rule.target, (list, tuple)):
        #    patch_handlers(tracer, rules)
        #    return

    if isinstance(rule, tornado.web._ApplicationRouter):
        apply_func_on_handlers(func, rule.rules)
        return

    if inspect.isclass(rule) and issubclass(rule, tornado.web.RequestHandler):
        func(rule)


def unpatch_handlers(rules):
    if isinstance(rules, (tuple, list)):
        for rule in rules:
            unpatch_handlers(rules)
            continue
    rule = rules
    if isinstance(rule, Rule):
        if isinstance(rule.target, (list, tuple)):
            #patch_handlers(tracer, rules)
            return
    

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
        if isinstance(error, tornado.web.HTTPError):
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
