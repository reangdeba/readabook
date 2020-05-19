# this is the main script that does the magic of serving the app

# necessary imports
import os
# from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash
from helpers import apology, login_required, admin_required
from flask_misaka import Misaka
import wikipedia
from datetime import datetime
from flask_mail import Mail, Message
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker


# Configure application
app = Flask(__name__)

# Check for environment variables
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")
if not os.getenv("MAIL_USERNAME"):
    raise RuntimeError("MAIL_USERNAME is not set")

# Ensure templates are auto-reloaded
# app.config["TEMPLATES_AUTO_RELOAD"] = True

# # Ensure responses aren't cached
# @app.after_request
# def after_request(response):
#     response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
#     response.headers["Expires"] = 0
#     response.headers["Pragma"] = "no-cache"
#     return response


# Configure session to use filesystem (instead of signed cookies)
# app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
sess = Session(app)

# this converts markdown code into nice looking html pages
md = Misaka()
md.init_app(app)


engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))

app.config.update(
	DEBUG=True,
	#EMAIL SETTINGS
	MAIL_SERVER='smtp.gmail.com',
	MAIL_PORT=465,
	MAIL_USE_SSL=True,
	MAIL_USERNAME = os.environ.get('MAIL_USERNAME'),
	MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
	)
mail = Mail(app)

# start defining website routes
@app.route("/")
@login_required
def index():
    """Show user homapage"""
    rows = db.execute("SELECT * FROM books")
    return render_template("index.html", books=rows)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          {"username": request.form.get("username")})

        rows = rows.fetchall()
        # Ensure username exists and password is correct
        len_rows = len(rows)
        if len(rows) != 1 or not check_password_hash(rows[0]['hash'], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["username"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        elif not request.form.get("confirmation"):
            return apology("must provide confirmation password", 403)

        password = request.form.get("password")
        confirm = request.form.get("confirmation")

        if password != confirm:
            return apology("passwords do not match", 403)


        try:
            rows = db.execute("SELECT * FROM users WHERE username = :username",
                          {"username": request.form.get("username")})
        except:
            pass

        if len(rows.fetchone()) != 0:
            return apology("username already taken", 403)

        hash_ = generate_password_hash(request.form.get("password"))

        db.execute("INSERT INTO users (username, hash, email, fullname, phone, postaladd) VALUES (:username, :hash_, :email, :fullname, :phone, :postaladd)", {"username": request.form.get("username"), "hash_": hash_, "email": request.form.get("email"), "fullname": request.form.get("fullname"), "phone": request.form.get("phoneNumber"), "postaladd":request.form.get("postalAddress")})

        db.commit()
        flash("Registration successful!")

        return redirect("/login")

    else:
        return render_template('register.html')


@app.route("/books")
@login_required
def books():
    """List books"""
    rows = db.execute("SELECT * FROM books")

    return render_template("books.html", books=rows)

# list individual book details
# url is of the form /book/isbn13
@app.route("/book/<isbn>")
@login_required
def book(isbn):
    """Book details"""
    # query the db using isbn13
    row = db.execute("SELECT * FROM books WHERE isbn=:isbn", {"isbn": isbn})
    row = row.fetchall()
    author_name = row[0]["author"]

    # query the author db to get author bio scraped from wikipedia
    author_details = db.execute("SELECT * FROM authors WHERE name=:name", {"name": author_name})
    author_details = author_details.fetchall()
    return render_template("book_details.html", book=row[0], author_details=author_details[0]["bio"])


# allow users to borrow book
@app.route("/borrow/<isbn>", methods=["POST"])
@login_required
def borrow(isbn):
    """Allow request for available books"""
    if not request.form.get("pickupAdd"):
        return apology("Please choose pickup address")

    date = datetime.now().strftime('%d-%m-%Y %H:%M:%S')
    books = db.execute("SELECT * FROM books WHERE isbn=:isbn", isbn=isbn)
    title = books[0]["title"]

    rows = db.execute("SELECT * FROM users WHERE username=:username", username=session["user_id"])

    fullname = rows[0]["fullname"]
    phone = rows[0]["phone"]
    postalAdd = rows[0]["postaladd"]

    rows = db.execute("INSERT INTO requests (username, title, isbn, dateRequested, pickup, fullname, phone, postaladd) VALUES (:username, :booktitle, :isbn, :date, :pickup, :fullname, :phone, :postalAdd)",
                      username=session["user_id"], booktitle=title, isbn=isbn, date=date, pickup=request.form.get("pickupAdd"), fullname=fullname, phone=phone, postalAdd=postalAdd)




    book = db.execute("SELECT * FROM books WHERE isbn=:isbn", isbn=isbn)
    count = book[0]["count"]
    status = book[0]["status"]

    count = count - 1
    if count < 1:
        status = "unavailable"
    else:
        status = "available"

    rows = db.execute("UPDATE books SET status=:status, count=:count WHERE isbn=:isbn", status=status, count=count, isbn=isbn)


    email_recipient = os.environ.get('MAIL_RECIPIENT')

    msg = Message(subject="Hi! I am Debashish.", sender=os.environ.get('MAIL_USERNAME'), recipients=[f"{email_recipient}"])
    msg.body = "Hi! I am Debashish."
    msg.html = '<b>Readabook.in</b> test email!'
    mail.send(msg)

    flash("Book request successful!")

    return redirect(f"/book/{isbn}")

# admin login page
@app.route("/admin", methods=["GET", "POST"])
# @login_required
def admin():
    """Allow admin login"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM admins WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which admin has logged in
        session["admin_id"] = rows[0]["username"]

        # Redirect user to home page
        return redirect("/dashboard")
    else:
        return render_template("admin.html")


@app.route("/record")
@login_required
def record():
    """Display record of issued books"""

    books = db.execute("SELECT * FROM issued WHERE issuedTo = :username",
                      username=session["user_id"])
    # books = rows[0]
    return render_template("record.html", books=books)


# the admin dashboard
@app.route("/dashboard")
@admin_required
def dashboard():
    """Show admin homepage"""

    # entire catalog
    rows = db.execute("SELECT * FROM books")
    all_books = rows

    # issued books
    issued = db.execute("SELECT * FROM issued")
    books_issued = issued

    # book requests
    req = db.execute("SELECT * FROM requests")
    book_req = req

    return render_template("admin_index.html", all_books=all_books, books_issued=books_issued, book_requests=book_req)


@app.route("/adminview/<isbn>")
@admin_required
def adminview(isbn):
    """Book details"""
    # query the db using isbn13
    row = db.execute("SELECT * FROM books WHERE isbn=:isbn", isbn=isbn)
    author_name = row[0]["author"]

    # query the author db to get author bio scraped from wikipedia
    author_details = db.execute("SELECT * FROM authors WHERE name=:name", name=author_name)
    return render_template("book_details.html", book=row[0], author_details=author_details[0]["bio"])

@app.route("/issue/<isbn>/<username>/<action>", methods=["POST"])
@admin_required
def issue(isbn, username, action):
    if action == "yes":
        date = request.form.get("issue_date")

        book_title = db.execute("SELECT * FROM books WHERE isbn=:isbn", isbn=isbn)
        book_title = book_title[0]["title"]
        rows = db.execute("INSERT INTO issued (title, isbn, issuedTo, issuedBy, dateIssued, dateReturned) VALUES (:title, :isbn, :username, :admin, :issue_date, :return_date)",
                          title=book_title, isbn=isbn, username=username, admin=session["admin_id"], issue_date=date, return_date=None)
        del_ = db.execute("DELETE FROM requests WHERE username=:user_id AND isbn=:isbn_number", user_id=username, isbn_number=isbn)

        email_recipient = os.environ.get('MAIL_RECIPIENT')

        msg = Message(subject="Hi! I am Debashish.", sender=os.environ.get('MAIL_USERNAME'), recipients=[f"{email_recipient}"])
        msg.body = "Hi! I am Debashish."
        msg.html = '<b>Readabook.in</b> issue test email!'
        mail.send(msg)
    else:
        del_ = db.execute("DELETE FROM requests WHERE username=:user_id AND isbn=:isbn_number", user_id=username, isbn_number=isbn)
    return redirect("/dashboard")

## Do not modify the code below
# standard error handlers
def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
