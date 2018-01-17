from sql import SQL
from datetime import datetime
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    stocks = get_stocks(session["user_id"])
    cash = get_cash(session["user_id"])

    # Total value of stocks
    value = 0

    for stock in stocks:
        try:
            stock["price"] = lookup(stock["symbol"])["price"]
            stock["stocks_value"] = usd(stock["price"]*stock["total_shares"])
            value += stock["price"] * stock["total_shares"]
            stock["price"] = usd(stock["price"])

        except:
            return render_template("index.html", stocks=stocks, cash=usd(cash))

    return render_template("index.html", stocks=stocks, cash=usd(cash), total=usd(value+cash))

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        symbol = request.form.get("symbol")
        stock = lookup(symbol)

        try:
            shares = float(request.form.get("shares"))
        except:
            return apology("The number of share must be numeric")

        # A symbol has been submitted
        if not symbol:
            return apology("You need to provide a symbol")

        # Symbol exists
        elif not stock:
            return apology("Symbol doesn't exist")

        # Number of shares is positive
        elif shares < 0.01:
            return apology("The number of shares must be positive")

        # Amount of cash user has
        cash = get_cash(session["user_id"])

        # Get stock price and total cost
        stock = lookup(symbol)
        total_cost = shares * stock["price"]

        # User can afford the stock
        if cash > total_cost:
            cash -= total_cost
            result = do_transaction(stock["name"], symbol, shares, stock["price"], session["user_id"], cash)

        else:
            return apology("You don't have enough money for this buy")

        return redirect("/")

    # user got to the route via GET
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    stocks = get_stocks(session["user_id"], date=True)
    for stock in stocks:
        stock["value"] = usd(abs(stock["price"]*stock["shares"]))

    return render_template("history.html", stocks=stocks)


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
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

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


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    # User reached route via POST
    if request.method == "POST":
        symbol = request.form.get("symbol")
        stock = lookup(symbol)

        if not symbol:
            return apology("A stock symbol in needed")

        elif not stock:
            return apology("Symbol doesn't exist")

        else:

            return render_template("quoted.html", name=stock["name"], symbol=stock["symbol"], price=usd(stock["price"]))

    # user got to the route via GET
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # Forget any user_id
    session.clear()

    # User reached route via POST
    if request.method == "POST":

        # A username has been submitted
        if not request.form.get("username"):
            return apology("Must choose a username", 400)

        # Ensure new password has been submitted
        elif not request.form.get("password"):
            return apology("Must choose a password", 400)

        # Ensure confirmation of password has been submitted
        elif not request.form.get("confirmation"):
            return apology("Please confirm your password", 400)

        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("Your passwords don't match", 400)

        # Get a hash for the password
        hash_pass = generate_password_hash(request.form.get("password"))

        # Query database for username (returns the row id to result)
        result = db.execute("INSERT INTO users (username, hash) VALUES (:username, :hash)",
                            username = request.form.get("username"), hash = hash_pass)

        # Check if username already exists
        if not result:
            return apology("That username already exists, choose another one", 400)

        # log the user in once it is registered
        session["user_id"] = result

        # redirect user to homepage
        return redirect("/")

    # user got to the route via GET
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        symbol = request.form.get("symbol")
        shares = float(request.form.get("shares"))
        stocks_owned = get_stocks(session["user_id"])

        for stock in stocks_owned:
            if stock["symbol"] == symbol:
                shares_owned = stock["total_shares"]

        # A symbol has been submitted
        if not symbol:
            return apology("You need to provide a symbol")

        # Number of shares is positive
        elif shares < 0.01:
            return apology("The number of shares must be positive")

        if shares > shares_owned:
            return apology("You don't have that amount of shares")

        # Amount of cash user has
        cash = get_cash(session["user_id"])

        # Get stock price and total value
        stock = lookup(symbol)
        total_value = shares * stock["price"]

        cash += total_value
        result = do_transaction(stock["name"], symbol, -shares, stock["price"], session["user_id"], cash)

        return redirect("/")

    # user got to the route via GET
    else:
        stocks_owned = get_stocks(session["user_id"])
        return render_template("sell.html", stocks=stocks_owned)


def errorhandler(e):
    """Handle error"""
    return apology(e.name, e.code)


def get_stocks(user_id, date=False):
    """Gets the stocks owned by the user"""

    # Get transactions by user
    if date:
        return db.execute("SELECT name, price, shares, date FROM transactions WHERE user_id = :user_id",
                        user_id=user_id)
    else:
        return db.execute("SELECT name, symbol, SUM(shares) AS total_shares FROM transactions GROUP BY symbol HAVING user_id = :user_id",
                            user_id=user_id)


def get_cash(user_id):
    """Gets amount of cash user has"""

    return db.execute("SELECT cash FROM users WHERE id = :user_id", user_id=user_id)[0]["cash"]


def do_transaction(stock_name, symbol, shares, price, user_id, cash):
    "Buy or sell stock at current price and update cash available"
    result = db.execute(
                "INSERT INTO transactions (date, name, symbol, shares, price, user_id) VALUES (:date, :name, :symbol, :shares, :price, :user_id)",
                date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"), name=stock_name, symbol=symbol, shares=shares,
                price=price, user_id=user_id)

    # Transaction was unsuccesful
    if not result:
            return apology("Sorry, the sell wasn't executed. Try later")

    else:
        db.execute("UPDATE users SET cash = :cash WHERE id = :user_id", cash=cash, user_id=session["user_id"])

# listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
