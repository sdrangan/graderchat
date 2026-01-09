from flask import Flask
from graderchat.routes.api import APIController
from graderchat.services.grader import Grader

def create_app(questions_root="questions", scratch_dir="scratch"):
    app = Flask(__name__)

    grader = Grader(questions_root=questions_root, scratch_dir=scratch_dir)
    controller = APIController(grader)
    controller.register(app)

    return app