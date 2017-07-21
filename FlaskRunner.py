import pykka
import views


class FlaskRunner(pykka.ThreadingActor):
    def __init__(self, manager):
        super(FlaskRunner, self).__init__()
        self.manager = manager

    def on_start(self):
        views.run(self.manager)
