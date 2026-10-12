from flask import Blueprint, send_from_directory
import os

im = Blueprint('image', __name__)

@im.route('/images/<path:filename>')
def image(filename):
    folder = os.path.join(os.getcwd(), 'mcres\\static\\images')
    return send_from_directory(folder, filename)
