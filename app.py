from flask import Flask, jsonify, request, render_template
from pnr import get_connection

app = Flask(__name__)


@app.get("/")
def home():
    return render_template("index.html")

@app.get("/manifest")
def manifest():
    return render_template("manifest.html")

@app.get("/passenger")
def search_passenger():
    return render_template("passenger.html")

@app.get("/seatmap")
def seatmap():
    return render_template("seatmap.html")

@app.get("/all-flights")
def all_flights_page():
    return render_template("flights.html")

@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "not found"}), 404


@app.get("/flights")
def list_flights():
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM flights ORDER BY flight_date, flight_no"
        ).fetchall()
        return jsonify([dict(r) for r in rows])
    finally:
        conn.close()


@app.get("/flights/<flight_no>/<flight_date>/<origin>/<destination>/passengers")
def flight_passengers(flight_no, flight_date, origin, destination):
    # flight_date must be YYYY-MM-DD; spaces in flight_no are URL-decoded automatically
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT * FROM passengers
               WHERE flight_no = ? AND flight_date = ? AND origin = ? AND destination = ?
               ORDER BY seat""",
            (flight_no, flight_date, origin, destination),
        ).fetchall()
        return jsonify([dict(r) for r in rows])
    finally:
        conn.close()

@app.get("/flights/<flight_no>/<flight_date>/<origin>/<destination>/seat_config")
def flight_seat_config(flight_no, flight_date, origin, destination):
    conn = get_connection()
    try:
        flight = conn.execute(
            """SELECT a.config_code
               FROM flights f JOIN aircraft a ON f.aircraft_id = a.aircraft_id
               WHERE f.flight_no=? AND f.flight_date=?
               AND f.origin=? AND f.destination=?""",
            (flight_no, flight_date, origin, destination),
        ).fetchone()
        if not flight or not flight["config_code"]:
            return jsonify({"error": "No seat config assigned to this flight"}), 404
        rows = conn.execute(
            """SELECT * FROM seat_configs
               WHERE config_code=?
               ORDER BY row_first""",
            (flight["config_code"],),
        ).fetchall()
        return jsonify([dict(r) for r in rows])
    finally:
        conn.close()

@app.get("/passengers/search")
def search_passengers():
    last_name = request.args.get("last_name", "").strip()
    cabin_class = request.args.get("cabin_class", "").strip()
    ssr_code = request.args.get("ssr_code", "").strip()
    seat_num = request.args.get("seat_num", "").strip()
    flight_num = request.args.get("flight_num", "").strip()
    departure_date = request.args.get("departure_date", "").strip()

    conn = get_connection()
    try:
        if last_name:
            # Escape LIKE wildcards in user input so they are treated as literals
            safe = last_name.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            rows = conn.execute(
                """SELECT * FROM passengers
                   WHERE last_name LIKE ? ESCAPE '\\'
                   ORDER BY last_name, first_name""",
                (f"%{safe}%",),
            ).fetchall()
        elif cabin_class:
            rows = conn.execute(
                """SELECT * FROM passengers
                   WHERE UPPER(cabin_class) = UPPER(?)
                   ORDER BY seat""",
                (cabin_class,),
            ).fetchall()
        elif ssr_code:
            rows = conn.execute(
                """SELECT * FROM passengers
                   WHERE UPPER(ssr_codes) = UPPER(?)
                   ORDER BY last_name, first_name""",
                (ssr_code,),
            ).fetchall()
        elif seat_num and flight_num and departure_date:
            rows = conn.execute(
                """SELECT * FROM passengers
                   WHERE seat = ? AND flight_no = ? AND flight_date = ?""",
                (seat_num, flight_num, departure_date)
            ).fetchall()
        else:
            return jsonify({"error": "provide one of: last_name, cabin_class, ssr_code, or seat_num+flight_num+departure_date"}), 400

        return jsonify([dict(r) for r in rows])
    finally:
        conn.close()

@app.put("/passengers/<int:pax_id>/seat")
def assign_seat(pax_id):
    data = request.get_json()
    new_seat = (data.get("seat") or "").strip() or None
    conn = get_connection()
    try:
        pax = conn.execute(
            "SELECT flight_no, flight_date, origin, destination FROM passengers WHERE id=?",
            (pax_id,)
        ).fetchone()
        if not pax:
            return jsonify({"error": "Passenger not found"}), 404
        if new_seat:
            conflict = conn.execute(
                """SELECT last_name, first_name FROM passengers
                   WHERE seat=? AND flight_no=? AND flight_date=? AND origin=? AND destination=? AND id!=?""",
                (new_seat, pax["flight_no"], pax["flight_date"],
                 pax["origin"], pax["destination"], pax_id)
            ).fetchone()
            if conflict:
                return jsonify({
                    "error": f"Seat {new_seat} is already assigned to {conflict['last_name']}, {conflict['first_name']}",
                    "conflict": dict(conflict)
                }), 409
        conn.execute("UPDATE passengers SET seat=? WHERE id=?", (new_seat, pax_id))
        conn.commit()
        return jsonify({"success": True, "seat": new_seat})
    finally:
        conn.close()

# fetch travel doc
@app.get("/travel_documents/<document_type>/<document_no>")
def get_document(document_type, document_no):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM travel_documents WHERE document_type=? AND document_no=?",
            (document_type, document_no)
        ).fetchone()
        return jsonify(dict(row) if row else {})
    finally:
        conn.close()

# create travel doc
@app.post("/travel_documents")
def create_document():
    conn = get_connection()
    data = request.get_json()
    try:
        row = conn.execute(
            """INSERT INTO travel_documents (document_type, document_no, last_name, first_name, 
            nationality, country_of_issue, date_of_birth, date_of_expiry)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (data["document_type"], data["document_no"], data["last_name"],
             data["first_name"], data["nationality"], data["country_of_issue"], 
             data["date_of_birth"], data["date_of_expiry"])
        )
        conn.commit()
        return jsonify({"success": True})
    finally: conn.close()

# update travel doc
@app.put("/travel_documents/<document_type>/<document_no>")
def update_document(document_type, document_no):
    data = request.get_json()
    conn = get_connection()
    try:
        conn.execute(
            """UPDATE travel_documents SET last_name=?, first_name=?,
               nationality=?, country_of_issue=?, date_of_birth=?, date_of_expiry=?
               WHERE document_type=? AND document_no=?""",
            (data["last_name"], data["first_name"],
             data["nationality"], data["country_of_issue"],
             data["date_of_birth"], data["date_of_expiry"],
             document_type, document_no)
        )
        conn.commit()
        return jsonify({"success": True})
    finally:
        conn.close()

# delete travel doc
@app.delete("/travel_documents/<document_type>/<document_no>")
def delete_document(document_type, document_no):
    conn = get_connection()
    try:
        conn.execute(
            "DELETE FROM travel_documents WHERE document_type=? AND document_no=?",
            (document_type, document_no)
        )
        conn.commit()
        return jsonify({"success": True})
    finally:
        conn.close()

@app.get("/ssr_codes")
def list_ssr_codes():
    conn = get_connection()
    try:
        rows = conn.execute("SELECT * FROM ssr_codes ORDER BY code").fetchall()
        return jsonify([dict(r) for r in rows])
    finally:
        conn.close()


if __name__ == "__main__":
    app.run(debug=True)
