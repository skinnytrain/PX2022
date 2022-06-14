import datetime
from datetime import timedelta
import dateutil.utils
import dateutil.parser

from flask import Blueprint, render_template, url_for, json, request, session, redirect, logging, flash
from pymongo import MongoClient
from wtforms import Form, StringField, TextAreaField, PasswordField, validators, RadioField
from passlib.hash import sha256_crypt
from functools import wraps

cluster = "mongodb://localhost:27017"
client = MongoClient(cluster)
print(client.list_database_names())
db = client.dashboard
print(db.list_collection_names())

main = Blueprint('main', __name__ )

#testquery = db.dashdata.find({"humidity": 43})
#print(testquery)

# currentdate = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
# print(currentdate)
#
# testdate = (datetime.datetime.now() + timedelta(hours=-10.25)).strftime("%Y-%m-%dT%H:%M:%SZ") #offset to gmt then -15mins
# print(testdate)
#
# testquery = db.dashdata.find({"received_at": {"$gt": testdate}}).limit(1)
# print(db.dashdata.count_documents({"received_at": {"$gt": testdate}})) #count
# print(testquery) #cursor location, testquery is a list

def is_logged_in(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if 'logged_in' in session:
            return f(*args, **kwargs)
        else:
            flash('unauthorised, please log in', 'danger')
            return redirect(url_for('main.login'))
    return wrap

@main.route('/', methods=['GET', 'POST'])
@is_logged_in
def index():
    userAuthority = session['authority']
    # get time = 15mins before now (modified by gmt -10) and query for single record, pass to index
    modTime = -10.25
    shownTime = -15
    querytime = (datetime.datetime.now() + timedelta(hours=modTime)).strftime("%Y-%m-%dT%H:%M:%SZ")

    while db.dashdata.count_documents({"received_at": {"$gt": querytime}}) < 1:
        print("nodata")
        print(modTime)
        print(shownTime)
        modTime = modTime - 0.25
        shownTime = shownTime - 15
        querytime = (datetime.datetime.now() + timedelta(hours=modTime)).strftime("%Y-%m-%dT%H:%M:%SZ")

    testquery = db.dashdata.find({"received_at": {"$gt": querytime}})
    for query in testquery:
        print(query)
        nowdata = query
    print(nowdata)
    displaytime = (dateutil.parser.parse(nowdata["received_at"]) + timedelta(hours=10)).strftime("%H:%M:%S")

    # set up arrays
    labels = []
    co2_values = []
    hum_values = []
    light_values = []
    motion_values = []
    temp_values = []

    if request.method == 'POST':
        if len(request.form['fromDate']) == 0 or len(request.form['toDate']) == 0:
            error = 'date value not selected or invalid'
            return render_template('index.html',
                                   nowdata=nowdata, displaytime=displaytime, error=error)

        # get form's from date adjusted for GMT
        fromDate = (dateutil.parser.parse(request.form['fromDate'])+ timedelta(hours=-10)).strftime("%Y-%m-%dT%H:%M:%SZ")
        print(fromDate)

        # get form's to date adjusted for GMT
        toDate = (dateutil.parser.parse(request.form['toDate'])+ timedelta(hours=-10)).strftime("%Y-%m-%dT%H:%M:%SZ")
        print(toDate)

        datequery = db.dashdata.find({"received_at": {"$gt": fromDate, "$lt": toDate}})
        print(db.dashdata.count_documents({"received_at": {"$gt": fromDate, "$lt": toDate}}))

        labels.clear()
        co2_values.clear()
        hum_values.clear()
        light_values.clear()
        motion_values.clear()
        temp_values.clear()

        for data in datequery:
            labels.append((dateutil.parser.parse(data["received_at"]) + timedelta(hours=10)).strftime("%Y:%m:%d , %H:%M:%S"))

            if "co2" in data.keys():
                co2_values.append(data["co2"])
            else:
                co2_values.append(co2_values[-1])

            if "humidity" in data.keys():
                hum_values.append(data["humidity"])
            else:
                hum_values.append(hum_values[-1])

            if "light" in data.keys():
                light_values.append(data["light"])
            else:
                light_values.append(light_values[-1])

            if "temperature" in data.keys():
                temp_values.append(data["temperature"])
            else:
                temp_values.append(temp_values[-1])

            motion_values.append(data["motion"])

    return render_template('index.html', userAuthority=userAuthority,
                           labels=labels, co2_values=co2_values, hum_values=hum_values,
                           light_values=light_values, temp_values=temp_values, motion_values=motion_values,
                           nowdata=nowdata, displaytime=displaytime)


@main.route('/uplink', methods=['POST'])
def api_gh_message():
    if request.headers['Content-Type'] == 'application/json':
        my_info = json.dumps(request.json)
        #my_info = request.json
        data = json.loads(my_info)

        if "decoded_payload" in data["uplink_message"] and data["end_device_ids"]["device_id"] == "eui-a81758fffe067069":
            print(data["uplink_message"]["decoded_payload"])
            print(data["received_at"])
            print(data["end_device_ids"]["device_id"])

            testDic = data["uplink_message"]["decoded_payload"]
            dateobj = dateutil.parser.parse(data["received_at"])

            testDic.update({"received_at": data["received_at"], "year": dateobj.year, "month": dateobj.month, "day": dateobj.day})

            print(testDic)

            db.dashdata.insert_one(testDic)

        return my_info

@main.route('/dashboard')
@is_logged_in
def dashboard():
    return render_template("dashboard.html")

@main.route('/labdata')
@is_logged_in
def labdata():
    return render_template("labdata.html")

class RegisterForm(Form):
    name = StringField('Name', [validators.length(min=1, max=50)])
    username = StringField('Username', [validators.length(min=4, max=25)])
    email = StringField('Email', [validators.length(min=6, max=80)])
    password = PasswordField('Password',[
        validators.DataRequired(),
        validators.EqualTo('confirm', message='incorrect/invalid password')
    ])
    accesslevel = RadioField('Access Level', choices=[('Admin','Admin'),('Executive','Executive'),('Operation','Operation')], default='Admin')
    confirm = PasswordField('Confirm Password')

@main.route('/register', methods=['Get', 'POST'])
def registration():
    form = RegisterForm(request.form)
    if request.method == 'POST' and form.validate():
        name = form.name.data
        username = form.username.data
        email = form.email.data
        password = sha256_crypt.encrypt(str(form.password.data))
        accesslevel = form.accesslevel.data

        userDic = {'name': name, 'username': username, 'email': email, 'password': password, 'accesslevel': accesslevel}

        db.users.insert_one(userDic)

        flash('You are now registered to use the MakerSpace dashboard', 'success')

        return redirect(url_for('main.login'))

    return render_template("register.html", form=form)

@main.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password_info = request.form['password']
        print(username + ' ' + password_info)
        log_user = db.users.find({'username': username}).limit(1)

        # if user is found, validate password
        if db.users.count_documents({'username': username}) > 0:
            for user in log_user:
                pw = user['password']
                # verify password
                if sha256_crypt.verify(password_info, pw):
                    session['logged_in'] = True
                    session['username'] = username
                    session['authority'] = user['accesslevel']
                    flash('you are now logged in', 'success')
                    return redirect(url_for('main.index'))
                else:
                    error = 'invalid login'
                    return render_template("login.html", error=error)

        else:
            error = 'username not found'
            return render_template("login.html", error=error)

        return redirect(url_for('main.index'))
    return render_template("login.html")


@main.route('/logout')
def logout():
    session.clear()
    flash('you are now logged out', 'success')
    return redirect(url_for('main.login'))