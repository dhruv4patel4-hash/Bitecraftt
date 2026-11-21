"""BiteCraft - a small food ordering website built with Flask.

Run:
    pip install flask
    python app.py
Then open http://127.0.0.1:5000
"""
import json
import os
import secrets
import sqlite3
import time

from flask import (Flask, abort, flash, g, redirect, render_template,
                   request, session, url_for)
from jinja2 import DictLoader

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-change-me")
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bitecraft.db")

GST_RATE = 0.05
DELIVERY_FEE = 30
FREE_DELIVERY_OVER = 500
STEP_SECONDS = 45  # demo speed: seconds between order status changes
STATUSES = ["Received", "Preparing", "On the way", "Delivered"]

CATEGORIES = ["Curries", "Biryani", "Breads", "Street Food", "Burgers", "Pizza",
              "Bowls", "Sides", "Drinks", "Desserts"]
MENU = [
    (1, "Smash Classic", "Burgers", 249, "Two smashed patties, cheddar, pickles, house sauce.", "🍔", False),
    (2, "Paneer Tikka Burger", "Burgers", 219, "Charred paneer, mint mayo, onion rings in a brioche bun.", "🍔", True),
    (3, "Crispy Chicken Stack", "Burgers", 239, "Buttermilk fried chicken, slaw, hot honey.", "🍗", False),
    (4, "Margherita", "Pizza", 299, "San Marzano tomato, fresh mozzarella, basil.", "🍕", True),
    (5, "Pepperoni Blaze", "Pizza", 379, "Double pepperoni, chilli oil, mozzarella.", "🍕", False),
    (6, "Farmhouse Veg", "Pizza", 349, "Mushroom, capsicum, olives, sweet corn, onion.", "🍕", True),
    (7, "Teriyaki Chicken Bowl", "Bowls", 289, "Sticky chicken, rice, edamame, pickled carrot.", "🍱", False),
    (8, "Burrito Bowl", "Bowls", 269, "Rice, black beans, corn salsa, guacamole, jalapeños.", "🥗", True),
    (9, "Masala Fries", "Sides", 119, "Skin-on fries tossed in chaat masala.", "🍟", True),
    (10, "Garlic Bread", "Sides", 99, "Toasted with garlic butter and herbs.", "🥖", True),
    (11, "Chicken Wings (6)", "Sides", 189, "Smoky BBQ glaze, ranch dip.", "🍗", False),
    (12, "Fresh Lime Soda", "Drinks", 69, "Sweet, salted or mixed. Served over ice.", "🥤", True),
    (13, "Cold Coffee", "Drinks", 129, "Slow-brewed, milk, a touch of vanilla.", "🧋", True),
    (14, "Mango Lassi", "Drinks", 109, "Thick, chilled, with a pinch of cardamom.", "🥭", True),
    (15, "Molten Choco Cake", "Desserts", 149, "Warm centre, served with vanilla ice cream.", "🍫", True),
    (16, "Brownie Sundae", "Desserts", 169, "Fudge brownie, ice cream, hot chocolate sauce.", "🍨", True),
    # Indian
    (17, "Butter Chicken", "Curries", 329, "Tandoori chicken in a creamy tomato-butter gravy.", "🍛", False),
    (18, "Paneer Butter Masala", "Curries", 289, "Soft paneer cubes in a rich, mildly sweet tomato gravy.", "🍛", True),
    (19, "Dal Makhani", "Curries", 239, "Black lentils slow-cooked overnight with cream and butter.", "🍲", True),
    (20, "Chole Masala", "Curries", 199, "Punjabi-style spiced chickpeas with onion and amchur.", "🍲", True),
    (21, "Kadai Chicken", "Curries", 319, "Chicken tossed with peppers in a roasted kadai masala.", "🍛", False),
    (22, "Hyderabadi Chicken Biryani", "Biryani", 349, "Dum-cooked basmati, marinated chicken, saffron, raita.", "🍚", False),
    (23, "Veg Dum Biryani", "Biryani", 279, "Seasonal vegetables layered with fragrant basmati, raita.", "🍚", True),
    (24, "Jeera Rice", "Biryani", 119, "Basmati rice tempered with cumin and ghee.", "🍚", True),
    (25, "Butter Naan", "Breads", 49, "Tandoor-baked, brushed with butter.", "🫓", True),
    (26, "Garlic Naan", "Breads", 59, "Tandoor naan with garlic and coriander.", "🫓", True),
    (27, "Aloo Paratha (2)", "Breads", 109, "Stuffed whole-wheat parathas with curd and pickle.", "🫓", True),
    (28, "Pav Bhaji", "Street Food", 169, "Buttery mashed vegetable bhaji with toasted pav.", "🍛", True),
    (29, "Samosa Chaat", "Street Food", 109, "Crushed samosas with chole, yogurt and chutneys.", "🥟", True),
    (30, "Vada Pav (2)", "Street Food", 79, "Mumbai-style potato fritters in pav with garlic chutney.", "🍔", True),
    (31, "Pani Puri (8)", "Street Food", 89, "Crisp puris with spiced mint water and potato filling.", "🥙", True),
    (32, "Masala Chai", "Drinks", 49, "Ginger-cardamom tea simmered with milk.", "☕", True),
    (33, "Sweet Lassi", "Drinks", 99, "Thick chilled curd drink, topped with malai.", "🥛", True),
    (34, "Gulab Jamun (2)", "Desserts", 89, "Warm milk dumplings in cardamom sugar syrup.", "🍮", True),
    (35, "Rasmalai (2)", "Desserts", 129, "Soft paneer discs in chilled saffron milk.", "🍮", True),
    (36, "Jalebi with Rabri", "Desserts", 139, "Hot crisp jalebis with thickened sweet milk.", "🍥", True),
]
ITEMS = {m[0]: dict(id=m[0], name=m[1], cat=m[2], price=m[3], desc=m[4], emoji=m[5], veg=m[6])
         for m in MENU}


# ---------------------------------------------------------------- database
def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    conn = g.pop("db", None)
    if conn:
        conn.close()


ORDER_COLS = ["code", "name", "phone", "address", "note", "items",
              "subtotal", "tax", "delivery", "total", "created"]


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        existing = [r[1] for r in conn.execute("PRAGMA table_info(orders)")]
        if existing and existing != ORDER_COLS:
            # Old/different schema from an earlier version: keep it as a backup.
            conn.execute(f"ALTER TABLE orders RENAME TO orders_old_{int(time.time())}")
        conn.execute(
            """CREATE TABLE IF NOT EXISTS orders (
                 code TEXT PRIMARY KEY, name TEXT, phone TEXT, address TEXT,
                 note TEXT, items TEXT, subtotal INTEGER, tax INTEGER,
                 delivery INTEGER, total INTEGER, created REAL)""")


# ------------------------------------------------------------------ cart
def cart_summary():
    lines, subtotal = [], 0
    for key, qty in session.get("cart", {}).items():
        item = ITEMS.get(int(key))
        if item and qty > 0:
            line_total = item["price"] * qty
            subtotal += line_total
            lines.append(dict(item=item, qty=qty, total=line_total))
    tax = round(subtotal * GST_RATE)
    delivery = 0 if (subtotal == 0 or subtotal >= FREE_DELIVERY_OVER) else DELIVERY_FEE
    return dict(lines=lines, subtotal=subtotal, tax=tax, delivery=delivery,
                total=subtotal + tax + delivery,
                count=sum(l["qty"] for l in lines))


@app.context_processor
def inject_cart():
    return dict(cart_count=cart_summary()["count"], FREE_DELIVERY_OVER=FREE_DELIVERY_OVER)


# ---------------------------------------------------------------- routes
@app.route("/")
def menu():
    cat = request.args.get("cat", "")
    q = request.args.get("q", "").strip().lower()
    veg = request.args.get("veg") == "1"
    items = [i for i in ITEMS.values()
             if (not cat or i["cat"] == cat)
             and (not veg or i["veg"])
             and (not q or q in i["name"].lower() or q in i["desc"].lower())]
    return render_template("menu.html", items=items, cats=CATEGORIES,
                           cat=cat, q=q, veg=veg, cart=cart_summary())


@app.post("/cart/add/<int:item_id>")
def cart_add(item_id):
    if item_id not in ITEMS:
        abort(404)
    cart = session.setdefault("cart", {})
    cart[str(item_id)] = min(cart.get(str(item_id), 0) + 1, 20)
    session.modified = True
    flash(f"{ITEMS[item_id]['name']} added to your order.")
    return redirect(request.referrer or url_for("menu"))


@app.post("/cart/update/<int:item_id>")
def cart_update(item_id):
    cart = session.setdefault("cart", {})
    delta = request.form.get("delta", type=int, default=0)
    new_qty = min(cart.get(str(item_id), 0) + delta, 20)
    if new_qty <= 0:
        cart.pop(str(item_id), None)
    else:
        cart[str(item_id)] = new_qty
    session.modified = True
    return redirect(url_for("cart_view"))


@app.route("/cart")
def cart_view():
    return render_template("cart.html", cart=cart_summary())


@app.route("/checkout", methods=["GET", "POST"])
def checkout():
    cart = cart_summary()
    if not cart["lines"]:
        flash("Your cart is empty. Add something tasty first.")
        return redirect(url_for("menu"))
    form = dict(name="", phone="", address="", note="")
    errors = {}
    if request.method == "POST":
        form = {k: request.form.get(k, "").strip() for k in form}
        digits = "".join(c for c in form["phone"] if c.isdigit())
        if len(form["name"]) < 2:
            errors["name"] = "Enter your name."
        if len(digits) < 10:
            errors["phone"] = "Enter a phone number with at least 10 digits."
        if len(form["address"]) < 10:
            errors["address"] = "Enter a full delivery address (house, street, area)."
        if not errors:
            code = "BC-" + secrets.token_hex(3).upper()
            snapshot = [dict(name=l["item"]["name"], qty=l["qty"], total=l["total"])
                        for l in cart["lines"]]
            db().execute(
                "INSERT INTO orders (" + ", ".join(ORDER_COLS) + ") VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (code, form["name"], form["phone"], form["address"], form["note"],
                 json.dumps(snapshot), cart["subtotal"], cart["tax"],
                 cart["delivery"], cart["total"], time.time()))
            db().commit()
            session.pop("cart", None)
            return redirect(url_for("order_status", code=code))
    return render_template("checkout.html", cart=cart, form=form, errors=errors)


@app.route("/order/<code>")
def order_status(code):
    row = db().execute("SELECT * FROM orders WHERE code = ?", (code,)).fetchone()
    if not row:
        abort(404)
    step = min(int((time.time() - row["created"]) // STEP_SECONDS), len(STATUSES) - 1)
    return render_template("order.html", o=row, items=json.loads(row["items"]),
                           statuses=STATUSES, step=step)


@app.errorhandler(404)
def not_found(_e):
    return render_template("404.html"), 404


# -------------------------------------------------------------- templates
BASE = """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{% block title %}BiteCraft{% endblock %}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,500;12..96,800&family=DM+Sans:wght@400;500;700&display=swap" rel="stylesheet">
<style>
:root{--bg:#eef3ea;--card:#fbfdf8;--ink:#12372a;--muted:#5b7267;--chili:#e4412b;--butter:#f6c945;--line:#cfdac8;
--head:'Bricolage Grotesque',Georgia,serif;--body:'DM Sans',system-ui,sans-serif}
*{box-sizing:border-box}html{scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--ink);font:400 16px/1.55 var(--body)}
a{color:inherit}.wrap{max-width:1080px;margin:0 auto;padding:0 20px}
:focus-visible{outline:3px solid var(--chili);outline-offset:2px}
header.top{background:var(--ink);color:#fff}
header.top .wrap{display:flex;align-items:center;justify-content:space-between;height:64px}
.logo{font:800 26px var(--head);text-decoration:none;letter-spacing:-.02em}
.logo b{color:var(--butter);font-weight:800}
.cartlink{background:var(--butter);color:var(--ink);text-decoration:none;font-weight:700;padding:8px 16px;border-radius:999px}
.cartlink span{background:var(--ink);color:var(--butter);border-radius:999px;padding:1px 9px;margin-left:6px;font-size:14px}
.hero{background:var(--ink);color:#fff;padding:36px 0 56px}
.hero h1{font:800 clamp(44px,9vw,104px)/.92 var(--head);letter-spacing:-.04em;margin:0 0 18px;max-width:11ch}
.hero p{color:#c4d6cb;max-width:46ch;margin:0 0 24px;font-size:18px}
.search{display:flex;gap:8px;max-width:520px}
.search input{flex:1}
input,textarea,select{font:inherit;color:var(--ink);background:#fff;border:2px solid var(--line);border-radius:10px;padding:11px 14px;width:100%}
input:focus,textarea:focus{border-color:var(--ink);outline:none}
.btn{font:700 16px var(--body);background:var(--chili);color:#fff;border:0;border-radius:10px;padding:11px 20px;cursor:pointer;text-decoration:none;display:inline-block}
.btn:hover{filter:brightness(.92)}.btn.alt{background:var(--ink)}.btn.ghost{background:transparent;color:var(--ink);border:2px solid var(--ink)}
.chips{display:flex;gap:8px;flex-wrap:wrap;margin:28px 0 8px}
.chip{padding:7px 16px;border-radius:999px;border:2px solid var(--ink);text-decoration:none;font-weight:500}
.chip.on{background:var(--ink);color:#fff}
.flash{background:var(--butter);padding:10px 0;font-weight:500}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:18px;margin:20px 0 60px}
.dish{background:var(--card);border:2px solid var(--line);border-radius:14px;padding:18px;display:flex;flex-direction:column}
.dish .em{font-size:54px;line-height:1}.dish h3{font:800 21px var(--head);margin:10px 0 4px;letter-spacing:-.01em}
.dish p{color:var(--muted);margin:0 0 14px;font-size:15px;flex:1}
.dish .row{display:flex;justify-content:space-between;align-items:center}
.price{font:800 22px var(--head)}
.dot{display:inline-block;width:12px;height:12px;border:2px solid #1f8a4c;border-radius:3px;position:relative;margin-right:6px;vertical-align:middle}
.dot::after{content:"";position:absolute;inset:2px;background:#1f8a4c;border-radius:50%}
.dot.nv{border-color:var(--chili)}.dot.nv::after{background:var(--chili)}
h1.page{font:800 clamp(34px,6vw,56px)/1 var(--head);letter-spacing:-.03em;margin:36px 0 20px}
.panel{background:var(--card);border:2px solid var(--line);border-radius:14px;padding:20px;margin-bottom:60px}
.line{display:flex;align-items:center;gap:14px;padding:14px 0;border-bottom:1px solid var(--line)}
.line .nm{flex:1;font-weight:700}.line small{display:block;color:var(--muted);font-weight:400}
.qty{display:flex;align-items:center;gap:8px}.qty button{width:32px;height:32px;border-radius:8px;border:2px solid var(--ink);background:#fff;font-size:18px;cursor:pointer}
.sum{display:flex;justify-content:space-between;padding:5px 0}.sum.t{font:800 24px var(--head);border-top:2px solid var(--ink);margin-top:8px;padding-top:12px}
.two{display:grid;grid-template-columns:1.4fr 1fr;gap:24px;align-items:start}
@media(max-width:760px){.two{grid-template-columns:1fr}}
label{font-weight:700;display:block;margin:14px 0 6px}.err{color:var(--chili);font-size:14px;margin-top:4px}
.track{list-style:none;padding:0;margin:20px 0;display:grid;grid-template-columns:repeat(4,1fr);gap:8px}
.track li{border-top:6px solid var(--line);padding-top:8px;color:var(--muted);font-weight:500}
.track li.done{border-color:var(--ink);color:var(--ink)}.track li.now{border-color:var(--chili);color:var(--chili);font-weight:700}
.code{font:800 18px var(--head);background:var(--butter);padding:3px 12px;border-radius:8px;display:inline-block}
.empty{padding:40px 0;text-align:center;color:var(--muted)}
footer{border-top:2px solid var(--line);padding:24px 0;color:var(--muted);font-size:14px}
@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}}
</style></head><body>
<header class="top"><div class="wrap">
<a class="logo" href="{{ url_for('menu') }}">Bite<b>Craft</b></a>
<a class="cartlink" href="{{ url_for('cart_view') }}">Cart<span>{{ cart_count }}</span></a>
</div></header>
{% with msgs = get_flashed_messages() %}{% if msgs %}<div class="flash" role="status"><div class="wrap">{{ msgs[0] }}</div></div>{% endif %}{% endwith %}
{% block body %}{% endblock %}
<footer><div class="wrap">BiteCraft. Demo project: no real orders or payments are processed.</div></footer>
</body></html>"""

MENU_PAGE = """{% extends 'base.html' %}
{% block body %}
<section class="hero"><div class="wrap">
<h1>Made when you order it.</h1>
<p>Burgers, pizzas and bowls cooked fresh and delivered in about 30 minutes. Free delivery over ₹{{ FREE_DELIVERY_OVER }}.</p>
<form class="search" method="get" role="search">
<input type="search" name="q" value="{{ q }}" placeholder="Search dishes, e.g. paneer" aria-label="Search dishes">
{% if cat %}<input type="hidden" name="cat" value="{{ cat }}">{% endif %}
{% if veg %}<input type="hidden" name="veg" value="1">{% endif %}
<button class="btn" type="submit">Search</button></form>
</div></section>
<main class="wrap">
<nav class="chips" aria-label="Categories">
<a class="chip {{ 'on' if not cat }}" href="{{ url_for('menu', q=q or None, veg='1' if veg else None) }}">All</a>
{% for c in cats %}<a class="chip {{ 'on' if c == cat }}" href="{{ url_for('menu', cat=c, q=q or None, veg='1' if veg else None) }}">{{ c }}</a>{% endfor %}
<a class="chip {{ 'on' if veg }}" href="{{ url_for('menu', cat=cat or None, q=q or None, veg=None if veg else '1') }}"><span class="dot"></span>Veg only</a>
</nav>
{% if items %}
<div class="grid">
{% for i in items %}
<article class="dish"><div class="em" aria-hidden="true">{{ i.emoji }}</div>
<h3><span class="dot {{ '' if i.veg else 'nv' }}" title="{{ 'Vegetarian' if i.veg else 'Non-vegetarian' }}"></span>{{ i.name }}</h3>
<p>{{ i.desc }}</p>
<div class="row"><span class="price">₹{{ i.price }}</span>
<form method="post" action="{{ url_for('cart_add', item_id=i.id) }}"><button class="btn" type="submit">Add to cart</button></form></div>
</article>{% endfor %}
</div>
{% else %}<div class="empty"><p>No dishes match that. Try another word or clear the filters.</p><a class="btn ghost" href="{{ url_for('menu') }}">Show full menu</a></div>{% endif %}
{% if cart.count %}<p style="margin-bottom:60px"><a class="btn alt" href="{{ url_for('cart_view') }}">View cart: {{ cart.count }} item{{ 's' if cart.count != 1 }}, ₹{{ cart.subtotal }}</a></p>{% endif %}
</main>{% endblock %}"""

SUMMARY = """<div class="sum"><span>Subtotal</span><span>₹{{ cart.subtotal }}</span></div>
<div class="sum"><span>GST (5%)</span><span>₹{{ cart.tax }}</span></div>
<div class="sum"><span>Delivery</span><span>{{ '₹' ~ cart.delivery if cart.delivery else 'Free' }}</span></div>
<div class="sum t"><span>Total</span><span>₹{{ cart.total }}</span></div>"""

CART_PAGE = """{% extends 'base.html' %}{% block title %}Your cart - BiteCraft{% endblock %}
{% block body %}<main class="wrap"><h1 class="page">Your cart</h1>
{% if cart.lines %}
<div class="two"><div class="panel">
{% for l in cart.lines %}
<div class="line"><div class="nm">{{ l.item.emoji }} {{ l.item.name }}<small>₹{{ l.item.price }} each</small></div>
<form class="qty" method="post" action="{{ url_for('cart_update', item_id=l.item.id) }}">
<button name="delta" value="-1" aria-label="Remove one {{ l.item.name }}">−</button><strong>{{ l.qty }}</strong>
<button name="delta" value="1" aria-label="Add one {{ l.item.name }}">+</button></form>
<strong style="min-width:64px;text-align:right">₹{{ l.total }}</strong></div>{% endfor %}
</div>
<div class="panel">""" + SUMMARY + """
{% if cart.subtotal < FREE_DELIVERY_OVER %}<p style="color:var(--muted);font-size:14px">Add ₹{{ FREE_DELIVERY_OVER - cart.subtotal }} more for free delivery.</p>{% endif %}
<a class="btn" style="width:100%;text-align:center" href="{{ url_for('checkout') }}">Go to checkout</a></div></div>
{% else %}<div class="empty"><p>Your cart is empty. Pick something from the menu.</p><a class="btn" href="{{ url_for('menu') }}">Browse menu</a></div>{% endif %}
</main>{% endblock %}"""

CHECKOUT_PAGE = """{% extends 'base.html' %}{% block title %}Checkout - BiteCraft{% endblock %}
{% block body %}<main class="wrap"><h1 class="page">Checkout</h1>
<div class="two"><form class="panel" method="post" novalidate>
<label for="name">Full name</label><input id="name" name="name" value="{{ form.name }}" autocomplete="name">
{% if errors.name %}<div class="err">{{ errors.name }}</div>{% endif %}
<label for="phone">Phone number</label><input id="phone" name="phone" value="{{ form.phone }}" inputmode="tel" autocomplete="tel">
{% if errors.phone %}<div class="err">{{ errors.phone }}</div>{% endif %}
<label for="address">Delivery address</label><textarea id="address" name="address" rows="3" autocomplete="street-address">{{ form.address }}</textarea>
{% if errors.address %}<div class="err">{{ errors.address }}</div>{% endif %}
<label for="note">Note for the kitchen (optional)</label><input id="note" name="note" value="{{ form.note }}">
<p style="color:var(--muted);font-size:14px">Payment: cash on delivery.</p>
<button class="btn" type="submit">Place order: ₹{{ cart.total }}</button></form>
<div class="panel"><strong>Your order</strong>
{% for l in cart.lines %}<div class="sum"><span>{{ l.qty }} × {{ l.item.name }}</span><span>₹{{ l.total }}</span></div>{% endfor %}
<hr style="border:0;border-top:1px solid var(--line)">""" + SUMMARY + """</div></div></main>{% endblock %}"""

ORDER_PAGE = """{% extends 'base.html' %}{% block title %}Order {{ o.code }} - BiteCraft{% endblock %}
{% block body %}{% if step < 3 %}<meta http-equiv="refresh" content="10">{% endif %}
<main class="wrap"><h1 class="page">{{ 'Delivered. Enjoy!' if step == 3 else 'We are on it, ' ~ o.name.split()[0] ~ '.' }}</h1>
<p>Order <span class="code">{{ o.code }}</span> &nbsp;Bookmark this page to check progress.</p>
<ol class="track">{% for s in statuses %}<li class="{{ 'now' if loop.index0 == step else ('done' if loop.index0 < step) }}">{{ s }}</li>{% endfor %}</ol>
<div class="two"><div class="panel"><strong>Items</strong>
{% for i in items %}<div class="sum"><span>{{ i.qty }} × {{ i.name }}</span><span>₹{{ i.total }}</span></div>{% endfor %}
<div class="sum"><span>GST</span><span>₹{{ o.tax }}</span></div>
<div class="sum"><span>Delivery</span><span>{{ '₹' ~ o.delivery if o.delivery else 'Free' }}</span></div>
<div class="sum t"><span>Total (cash)</span><span>₹{{ o.total }}</span></div></div>
<div class="panel"><strong>Delivering to</strong><p>{{ o.name }}<br>{{ o.phone }}<br>{{ o.address }}</p>
{% if o.note %}<p style="color:var(--muted)">Note: {{ o.note }}</p>{% endif %}
<a class="btn ghost" href="{{ url_for('menu') }}">Order more</a></div></div></main>{% endblock %}"""

NOT_FOUND = """{% extends 'base.html' %}{% block body %}<main class="wrap"><div class="empty">
<h1 class="page">Page not found</h1><p>That page does not exist or the order code is wrong.</p>
<a class="btn" href="{{ url_for('menu') }}">Back to the menu</a></div></main>{% endblock %}"""

app.jinja_loader = DictLoader({
    "base.html": BASE, "menu.html": MENU_PAGE, "cart.html": CART_PAGE,
    "checkout.html": CHECKOUT_PAGE, "order.html": ORDER_PAGE, "404.html": NOT_FOUND,
})

init_db()

if __name__ == "__main__":
    app.run(debug=True)
