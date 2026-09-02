"""
One-time data-cleanup script: normalizes cabin class naming and remaps
passenger seats onto seats that actually exist in the flight's seat_configs
layout. Passengers whose current seat is already valid and unclaimed keep it;
others are reassigned to a free valid seat (same cabin preferred); if no seat
is available anywhere, the passenger is deleted.

Run once after seed_aircraft.py has assigned aircraft to flights:
    python3 remap_seats.py
"""
from pnr import get_connection

conn = get_connection()
with conn:
    renamed = conn.execute(
        "UPDATE passengers SET cabin_class='Business' WHERE cabin_class='Polaris Biz'"
    ).rowcount
    print(f"Renamed {renamed} 'Polaris Biz' passengers to 'Business'")

    flights = conn.execute("SELECT flight_no, flight_date, origin, destination FROM flights").fetchall()

    for f in flights:
        flight_key = (f["flight_no"], f["flight_date"], f["origin"], f["destination"])

        config_row = conn.execute(
            """SELECT a.config_code
               FROM flights fl JOIN aircraft a ON fl.aircraft_id = a.aircraft_id
               WHERE fl.flight_no=? AND fl.flight_date=? AND fl.origin=? AND fl.destination=?""",
            flight_key,
        ).fetchone()
        if not config_row or not config_row["config_code"]:
            print(f"Skipping {flight_key}: no seat config assigned")
            continue

        cabins = conn.execute(
            "SELECT cabin_class, row_first, row_last, seat_columns FROM seat_configs WHERE config_code=? ORDER BY row_first",
            (config_row["config_code"],),
        ).fetchall()

        # seats_by_cabin: cabin_class -> ordered list of seat labels
        seats_by_cabin = {}
        valid_seats = set()
        for c in cabins:
            cols = c["seat_columns"].split(",")
            seats = [f"{row}{col}" for row in range(c["row_first"], c["row_last"] + 1) for col in cols]
            seats_by_cabin.setdefault(c["cabin_class"], []).extend(seats)
            valid_seats.update(seats)

        passengers = conn.execute(
            """SELECT id, seat, cabin_class FROM passengers
               WHERE flight_no=? AND flight_date=? AND origin=? AND destination=?
               ORDER BY id""",
            flight_key,
        ).fetchall()

        claimed = set()
        needs_seat = []
        for p in passengers:
            if p["seat"] and p["seat"] in valid_seats and p["seat"] not in claimed:
                claimed.add(p["seat"])
            else:
                needs_seat.append(p)

        kept = len(passengers) - len(needs_seat)
        reassigned = 0
        deleted = 0

        for p in needs_seat:
            free_seat = None
            # prefer a free seat in the passenger's own cabin
            for seat in seats_by_cabin.get(p["cabin_class"], []):
                if seat not in claimed:
                    free_seat = seat
                    break
            if not free_seat:
                # fall back to any free seat in any cabin
                for seat in valid_seats:
                    if seat not in claimed:
                        free_seat = seat
                        break

            if free_seat:
                claimed.add(free_seat)
                conn.execute("UPDATE passengers SET seat=? WHERE id=?", (free_seat, p["id"]))
                reassigned += 1
            else:
                conn.execute("DELETE FROM passengers WHERE id=?", (p["id"],))
                deleted += 1

        print(f"{flight_key[0]} {flight_key[1]}: {kept} kept, {reassigned} reassigned, {deleted} deleted "
              f"(capacity {len(valid_seats)}, started with {len(passengers)} passengers)")

conn.close()
print("Done.")
