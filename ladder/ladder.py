from flask import Flask, render_template
import psycopg2
import psycopg2.extras

app = Flask(__name__)


@app.route('/')
def ladder():
    f = open("db.txt", "r")
    print(f.read())
    db_conn = f.read()
    conn = psycopg2.connect("dbname=lab-bot user=ilavinogradov")
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("SELECT * FROM user_state ORDER BY user_score DESC")
    ladder = cur.fetchall()
    cur.close()
    return render_template('ladder.html', ladder=ladder)