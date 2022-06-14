from flask import Flask
from .main.routes import main
from .extensions import mongo


def create_app( ):
    app = Flask(__name__)
    #app.config['MONGO_URI'] = 'mongodb+srv://dbadmin:HikRWVcUiy5Pmkh@dashboarddb.njqz7q2.mongodb.net/?retryWrites=true&w=majority'
    #mongo.init_app(app)
    app.secret_key = 'secret123'
    app.register_blueprint(main)

    return app


