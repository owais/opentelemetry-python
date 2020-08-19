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


from tornado.testing import AsyncHTTPTestCase

from opentelemetry.test.test_base import TestBase
from opentelemetry import trace
from opentelemetry.instrumentation.tornado import TornadoInstrumentor
from opentelemetry.trace import SpanKind

from .app import make_app, DynamicHandler



class TornadoTest(AsyncHTTPTestCase, TestBase):

    def get_app(self):
        tracer = trace.get_tracer(__name__)
        app = make_app(tracer)
        return app


    def setUp(self):
        TornadoInstrumentor().instrument()
        super().setUp()

    def tearDown(self):
        TornadoInstrumentor().uninstrument()
        super().tearDown()


# TODO(owais): test uninstrument

class TestTornadoInstrumentation(TornadoTest):

    def test_http_calls(self):
        methods = ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]
        for method in methods:
            self._test_http_method_call(method)

    def _test_http_method_call(self, method):
        body = "" if method in ["POST", "PUT", "PATCH"] else None
        response = self.fetch("/", method=method, body=body)
        self.assertEqual(response.code, 201)
        spans = self.memory_exporter.get_finished_spans()
        self.assertEqual(len(spans), 3)

        manual, server, client = self.sorted_spans(spans)

        self.assertEqual(manual.name, "manual")
        self.assertEqual(manual.parent, server.context)
        self.assertEqual(manual.context.trace_id, client.context.trace_id)

        self.assertEqual(server.name, "MainHandler." + method.lower())
        self.assertTrue(server.parent.is_remote)
        self.assertNotEqual(server.parent, client.context)
        self.assertEqual(server.parent.span_id, client.context.span_id)
        self.assertEqual(server.context.trace_id, client.context.trace_id)
        self.assertEqual(server.kind, SpanKind.SERVER)
        self.assert_span_has_attributes(
            server,
            {
                "component": "tornado",
                "http.method": method,
                "http.scheme": "http",
                "http.host": "127.0.0.1:" + str(self.get_http_port()),
                "http.target": "/",
                "net.peer.ip": "127.0.0.1",
                "http.status_text": "Created",
                "http.status_code": 201,
            },
        )

        self.assertEqual(client.name, method)
        self.assertFalse(client.context.is_remote)
        self.assertIsNone(client.parent)
        self.assertEqual(client.kind, SpanKind.CLIENT)
        self.assert_span_has_attributes(
            client,
            {
                "component": "tornado",
                "http.url": self.get_url("/"),
                "http.method": method,
                "http.status_code": 201,
            },
        )

        self.memory_exporter.clear()

    def test_async_handler(self):
        self._test_async_handler("/async", "AsyncHandler")

    def test_coroutine_handler(self):
        self._test_async_handler("/cor", "CoroutineHandler")

    def _test_async_handler(self, url, handler_name):
        response = self.fetch(url)
        self.assertEqual(response.code, 201)
        spans = self.memory_exporter.get_finished_spans()
        self.assertEqual(len(spans), 5)

        sub2, sub1, sub_wrapper, server, client = self.sorted_spans(spans)

        self.assertEqual(sub2.name, "sub-task-2")
        self.assertEqual(sub2.parent, sub_wrapper.context)
        self.assertEqual(sub2.context.trace_id, client.context.trace_id)

        self.assertEqual(sub1.name, "sub-task-1")
        self.assertEqual(sub1.parent, sub_wrapper.context)
        self.assertEqual(sub1.context.trace_id, client.context.trace_id)

        self.assertEqual(sub_wrapper.name, "sub-task-wrapper")
        self.assertEqual(sub_wrapper.parent, server.context)
        self.assertEqual(sub_wrapper.context.trace_id, client.context.trace_id)

        self.assertEqual(server.name, handler_name + ".get")
        self.assertTrue(server.parent.is_remote)
        self.assertNotEqual(server.parent, client.context)
        self.assertEqual(server.parent.span_id, client.context.span_id)
        self.assertEqual(server.context.trace_id, client.context.trace_id)
        self.assertEqual(server.kind, SpanKind.SERVER)
        self.assert_span_has_attributes(
            server,
            {
                "component": "tornado",
                "http.method": "GET",
                "http.scheme": "http",
                "http.host": "127.0.0.1:" + str(self.get_http_port()),
                "http.target": url,
                "net.peer.ip": "127.0.0.1",
                "http.status_text": "Created",
                "http.status_code": 201,
            },
        )

        self.assertEqual(client.name, "GET")
        self.assertFalse(client.context.is_remote)
        self.assertIsNone(client.parent)
        self.assertEqual(client.kind, SpanKind.CLIENT)
        self.assert_span_has_attributes(
            client,
            {
                "component": "tornado",
                "http.url": self.get_url(url),
                "http.method": "GET",
                "http.status_code": 201,
            },
        )

    def test_500(self):
        response = self.fetch("/error")
        self.assertEqual(response.code, 500)

        spans = self.sorted_spans(self.memory_exporter.get_finished_spans())
        self.assertEqual(len(spans), 2)
        server, client = spans

        self.assertEqual(server.name, "BadHandler.get")
        self.assertEqual(server.kind, SpanKind.SERVER)
        self.assert_span_has_attributes(
            server,
            {
                "component": "tornado",
                "http.method": "GET",
                "http.scheme": "http",
                "http.host": "127.0.0.1:" + str(self.get_http_port()),
                "http.target": "/error",
                "net.peer.ip": "127.0.0.1",
                "http.status_code": 500,
            },
        )

        self.assertEqual(client.name, "GET")
        self.assertEqual(client.kind, SpanKind.CLIENT)
        self.assert_span_has_attributes(
            client,
            {
                "component": "tornado",
                "http.url": self.get_url("/error"),
                "http.method": "GET",
                "http.status_code": 500,
            },
        )

    def test_404(self):
        response = self.fetch("/missing-url")
        self.assertEqual(response.code, 404)

        spans = self.sorted_spans(self.memory_exporter.get_finished_spans())
        self.assertEqual(len(spans), 2)
        server, client = spans

        self.assertEqual(server.name, "ErrorHandler.get")
        self.assertEqual(server.kind, SpanKind.SERVER)
        self.assert_span_has_attributes(
            server,
            {
                "component": "tornado",
                "http.method": "GET",
                "http.scheme": "http",
                "http.host": "127.0.0.1:" + str(self.get_http_port()),
                "http.target": "/missing-url",
                "net.peer.ip": "127.0.0.1",
                "http.status_text": "Not Found",
                "http.status_code": 404,
            },
        )

        self.assertEqual(client.name, "GET")
        self.assertEqual(client.kind, SpanKind.CLIENT)
        self.assert_span_has_attributes(
            client,
            {
                "component": "tornado",
                "http.url": self.get_url("/missing-url"),
                "http.method": "GET",
                "http.status_code": 404,
            },
        )

    def test_dynamic_handler(self):
        response = self.fetch("/dyna")
        self.assertEqual(response.code, 404)
        self.memory_exporter.clear()

        self._app.add_handlers(r'.+', [
            (r'/dyna', DynamicHandler),
        ])

        response = self.fetch("/dyna")
        self.assertEqual(response.code, 202)

        spans = self.sorted_spans(self.memory_exporter.get_finished_spans())
        self.assertEqual(len(spans), 2)
        server, client = spans

        self.assertEqual(server.name, "DynamicHandler.get")
        self.assertTrue(server.parent.is_remote)
        self.assertNotEqual(server.parent, client.context)
        self.assertEqual(server.parent.span_id, client.context.span_id)
        self.assertEqual(server.context.trace_id, client.context.trace_id)
        self.assertEqual(server.kind, SpanKind.SERVER)
        self.assert_span_has_attributes(
            server,
            {
                "component": "tornado",
                "http.method": "GET",
                "http.scheme": "http",
                "http.host": "127.0.0.1:" + str(self.get_http_port()),
                "http.target": "/dyna",
                "net.peer.ip": "127.0.0.1",
                "http.status_text": "Accepted",
                "http.status_code": 202,
            },
        )

        self.assertEqual(client.name, "GET")
        self.assertFalse(client.context.is_remote)
        self.assertIsNone(client.parent)
        self.assertEqual(client.kind, SpanKind.CLIENT)
        self.assert_span_has_attributes(
            client,
            {
                "component": "tornado",
                "http.url": self.get_url("/dyna"),
                "http.method": "GET",
                "http.status_code": 202,
            },
        )



class TestTornadoUninstrument(TornadoTest):

    def test_uninstrument(self):
        response = self.fetch("/")
        self.assertEqual(response.code, 201)
        spans = self.memory_exporter.get_finished_spans()
        self.assertEqual(len(spans), 3)
        manual, server, client = self.sorted_spans(spans)
        self.assertEqual(manual.name, "manual")
        self.assertEqual(server.name, "MainHandler.get")
        self.assertEqual(client.name, "GET")
        self.memory_exporter.clear()

        TornadoInstrumentor().uninstrument()

        response = self.fetch("/")
        self.assertEqual(response.code, 201)
        spans = self.memory_exporter.get_finished_spans()
        self.assertEqual(len(spans), 1)
        manual = spans[0]
        self.assertEqual(manual.name, "manual")
