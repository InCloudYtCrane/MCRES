from mcres import create_app
from waitress import serve
from utils import db

app = create_app()
db.create_db()

if __name__ == '__main__':
    serve(app, host='127.0.0.1', port=5000)
