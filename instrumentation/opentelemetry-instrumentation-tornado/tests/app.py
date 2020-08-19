import tornado.web
from tornado import gen

tracer = None


class AsyncHandler(tornado.web.RequestHandler):
    async def get(self):
        with tracer.start_as_current_span("sub-task-wrapper"):
            await self.do_something1()
            await self.do_something2()
            self.set_status(201)
            self.write("{}")

    async def do_something1(self):
        with tracer.start_as_current_span("sub-task-1"):
            tornado.gen.sleep(0.1)

    async def do_something2(self):
        with tracer.start_as_current_span("sub-task-2"):
            tornado.gen.sleep(0.1)


class CoroutineHandler(tornado.web.RequestHandler):
    @gen.coroutine
    def get(self):
        with tracer.start_as_current_span("sub-task-wrapper"):
            yield self.do_something1()
            yield self.do_something2()
            self.set_status(201)
            self.write("{}")

    @gen.coroutine
    def do_something1(self):
        with tracer.start_as_current_span("sub-task-1"):
            tornado.gen.sleep(0.1)

    @gen.coroutine
    def do_something2(self):
        with tracer.start_as_current_span("sub-task-2"):
            tornado.gen.sleep(0.1)


class MainHandler(tornado.web.RequestHandler):
    def _handler(self):
        with tracer.start_as_current_span("manual"):
            self.write("Hello, world")
            self.set_status(201)

    def get(self):
        return self._handler()

    def post(self):
        ret = self._handler()

        return ret

    def patch(self):
        return self._handler()

    def delete(self):
        return self._handler()

    def put(self):
        return self._handler()

    def head(self):
        return self._handler()

    def options(self):
        return self._handler()


class BadHandler(tornado.web.RequestHandler):
    def get(self):
        raise NameError("some random name error")


class DynamicHandler(tornado.web.RequestHandler):
    def get(self):
        self.set_status(202)


def make_app(_tracer):
    global tracer
    tracer = _tracer
    app = tornado.web.Application(
        [
            (r"/", MainHandler),
            (r"/error", BadHandler),
            (r"/cor", CoroutineHandler),
            (r"/async", AsyncHandler),
        ]
    )
    app.tracer = tracer
    return app
