# Golden dataset: verified question -> SQL pairs for evaluating the system.
# We hand-verify each gold_sql by running it against Chinook.
# expected_behavior tells the evaluator what the system SHOULD do:
#   "sql"           -> should generate SQL that matches the gold result
#   "clarification" -> should ask for clarification instead of guessing
#   "no_answer"     -> database cannot answer this; should not fabricate

GOLDEN_DATASET = [
    # --- Category: simple lookups ---
    {
        "id": "simple_01",
        "question": "How many customers are there?",
        "category": "simple",
        "gold_sql": "SELECT COUNT(*) FROM Customer;",
        "expected_behavior": "sql",
    },
    {
        "id": "simple_02",
        "question": "How many tracks are in the database?",
        "category": "simple",
        "gold_sql": "SELECT COUNT(*) FROM Track;",
        "expected_behavior": "sql",
    },
    {
        "id": "simple_03",
        "question": "List the names of all playlists.",
        "category": "simple",
        "gold_sql": "SELECT Name FROM Playlist;",
        "expected_behavior": "sql",
    },
    {
        "id": "simple_04",
        "question": "How many employees work at the company?",
        "category": "simple",
        "gold_sql": "SELECT COUNT(*) FROM Employee;",
        "expected_behavior": "sql",
    },
    {
        "id": "simple_05",
        "question": "What are the names of all the genres?",
        "category": "simple",
        "gold_sql": "SELECT Name FROM Genre;",
        "expected_behavior": "sql",
    },

    # --- Category: aggregations (GROUP BY, SUM, COUNT, AVG) ---
    {
        "id": "agg_01",
        "question": "What is the total revenue from all invoices?",
        "category": "aggregation",
        "gold_sql": "SELECT SUM(Total) FROM Invoice;",
        "expected_behavior": "sql",
    },
    {
        "id": "agg_02",
        "question": "Which 3 countries generate the most revenue?",
        "category": "aggregation",
        "gold_sql": (
            "SELECT BillingCountry, SUM(Total) AS TotalRevenue "
            "FROM Invoice GROUP BY BillingCountry "
            "ORDER BY TotalRevenue DESC LIMIT 3;"
        ),
        "expected_behavior": "sql",
    },
    {
        "id": "agg_03",
        "question": "How many tracks are there in each genre?",
        "category": "aggregation",
        "gold_sql": (
            "SELECT Genre.Name, COUNT(Track.TrackId) AS TrackCount "
            "FROM Genre JOIN Track ON Genre.GenreId = Track.GenreId "
            "GROUP BY Genre.GenreId;"
        ),
        "expected_behavior": "sql",
    },
    {
        "id": "agg_04",
        "question": "What is the average track length in milliseconds?",
        "category": "aggregation",
        "gold_sql": "SELECT AVG(Milliseconds) FROM Track;",
        "expected_behavior": "sql",
    },
    # --- Category: multi-table JOINs ---
    {
        "id": "join_01",
        "question": "List the top 5 artists with the most albums.",
        "category": "join",
        "gold_sql": (
            "SELECT Artist.Name, COUNT(Album.AlbumId) AS AlbumCount "
            "FROM Artist JOIN Album ON Artist.ArtistId = Album.ArtistId "
            "GROUP BY Artist.ArtistId ORDER BY AlbumCount DESC LIMIT 5;"
        ),
        "expected_behavior": "sql",
    },
    {
        "id": "join_02",
        "question": "Which tracks belong to the album 'Let There Be Rock'?",
        "category": "join",
        "gold_sql": (
            "SELECT Track.Name FROM Track "
            "JOIN Album ON Track.AlbumId = Album.AlbumId "
            "WHERE Album.Title = 'Let There Be Rock';"
        ),
        "expected_behavior": "sql",
    },
    {
        "id": "join_03",
        "question": "What are the names of customers who are supported by employee Jane Peacock?",
        "category": "join",
        "gold_sql": (
            "SELECT Customer.FirstName, Customer.LastName FROM Customer "
            "JOIN Employee ON Customer.SupportRepId = Employee.EmployeeId "
            "WHERE Employee.FirstName = 'Jane' AND Employee.LastName = 'Peacock';"
        ),
        "expected_behavior": "sql",
    },
    {
        "id": "join_04",
        "question": "How much total revenue did each sales support agent generate?",
        "category": "join",
        "gold_sql": (
            "SELECT Employee.FirstName, Employee.LastName, SUM(Invoice.Total) AS Revenue "
            "FROM Employee "
            "JOIN Customer ON Customer.SupportRepId = Employee.EmployeeId "
            "JOIN Invoice ON Invoice.CustomerId = Customer.CustomerId "
            "GROUP BY Employee.EmployeeId;"
        ),
        "expected_behavior": "sql",
    },
    {
        "id": "join_05",
        "question": "How many tracks are on the playlist called 'Classical'?",
        "category": "join",
        "gold_sql": (
            "SELECT COUNT(*) FROM Track "
            "JOIN PlaylistTrack ON Track.TrackId = PlaylistTrack.TrackId "
            "JOIN Playlist ON PlaylistTrack.PlaylistId = Playlist.PlaylistId "
            "WHERE Playlist.Name = 'Classical';"
        ),
        "expected_behavior": "sql",
    },

    # --- Category: date filters (invoice dates are 2021-2025) ---
    {
        "id": "date_01",
        "question": "How many invoices were issued in 2023?",
        "category": "date",
        "gold_sql": (
            "SELECT COUNT(*) FROM Invoice "
            "WHERE InvoiceDate >= '2023-01-01' AND InvoiceDate < '2024-01-01';"
        ),
        "expected_behavior": "sql",
    },
    {
        "id": "date_02",
        "question": "What was the total revenue in 2024?",
        "category": "date",
        "gold_sql": (
            "SELECT SUM(Total) FROM Invoice "
            "WHERE InvoiceDate >= '2024-01-01' AND InvoiceDate < '2025-01-01';"
        ),
        "expected_behavior": "sql",
    },
    {
        "id": "date_03",
        "question": "How many invoices were issued in the first quarter of 2022?",
        "category": "date",
        "gold_sql": (
            "SELECT COUNT(*) FROM Invoice "
            "WHERE InvoiceDate >= '2022-01-01' AND InvoiceDate < '2022-04-01';"
        ),
        "expected_behavior": "sql",
    },

    # --- Category: ambiguous questions (should ask for clarification) ---
    {
        "id": "ambig_01",
        "question": "Who is our best customer?",
        "category": "ambiguous",
        "gold_sql": None,
        "expected_behavior": "clarification",
    },
    {
        "id": "ambig_02",
        "question": "What are the top songs?",
        "category": "ambiguous",
        "gold_sql": None,
        "expected_behavior": "clarification",
    },
    {
        "id": "ambig_03",
        "question": "Show me the important invoices.",
        "category": "ambiguous",
        "gold_sql": None,
        "expected_behavior": "clarification",
    },

    # --- Category: unanswerable (data not in the database) ---
    {
        "id": "unans_01",
        "question": "What is the email address of the artist AC/DC?",
        "category": "unanswerable",
        "gold_sql": None,
        "expected_behavior": "no_answer",
    },
    {
        "id": "unans_02",
        "question": "How many customers visited the website last week?",
        "category": "unanswerable",
        "gold_sql": None,
        "expected_behavior": "no_answer",
    },
    {
        "id": "unans_03",
        "question": "What is the weather in the customer's city?",
        "category": "unanswerable",
        "gold_sql": None,
        "expected_behavior": "no_answer",
    },
    # --- More simple lookups ---
    {
        "id": "simple_06",
        "question": "How many albums are in the database?",
        "category": "simple",
        "gold_sql": "SELECT COUNT(*) FROM Album;",
        "expected_behavior": "sql",
    },
    {
        "id": "simple_07",
        "question": "How many artists are there?",
        "category": "simple",
        "gold_sql": "SELECT COUNT(*) FROM Artist;",
        "expected_behavior": "sql",
    },
    {
        "id": "simple_08",
        "question": "List all media type names.",
        "category": "simple",
        "gold_sql": "SELECT Name FROM MediaType;",
        "expected_behavior": "sql",
    },
    {
        "id": "simple_09",
        "question": "How many invoices are there in total?",
        "category": "simple",
        "gold_sql": "SELECT COUNT(*) FROM Invoice;",
        "expected_behavior": "sql",
    },
    {
        "id": "simple_10",
        "question": "What are the first and last names of all employees?",
        "category": "simple",
        "gold_sql": "SELECT FirstName, LastName FROM Employee;",
        "expected_behavior": "sql",
    },

    # --- More aggregations ---
    {
        "id": "agg_05",
        "question": "How many customers are there in each country?",
        "category": "aggregation",
        "gold_sql": (
            "SELECT Country, COUNT(*) AS CustomerCount FROM Customer "
            "GROUP BY Country ORDER BY CustomerCount DESC;"
        ),
        "expected_behavior": "sql",
    },
    {
        "id": "agg_06",
        "question": "What is the most expensive track price?",
        "category": "aggregation",
        "gold_sql": "SELECT MAX(UnitPrice) FROM Track;",
        "expected_behavior": "sql",
    },
    {
        "id": "agg_07",
        "question": "What is the average invoice total?",
        "category": "aggregation",
        "gold_sql": "SELECT AVG(Total) FROM Invoice;",
        "expected_behavior": "sql",
    },
    {
        "id": "agg_08",
        "question": "How many tracks does each media type have?",
        "category": "aggregation",
        "gold_sql": (
            "SELECT MediaType.Name, COUNT(Track.TrackId) AS TrackCount "
            "FROM MediaType JOIN Track ON MediaType.MediaTypeId = Track.MediaTypeId "
            "GROUP BY MediaType.MediaTypeId;"
        ),
        "expected_behavior": "sql",
    },

    # --- More JOINs ---
    {
        "id": "join_06",
        "question": "How many albums does the artist 'Iron Maiden' have?",
        "category": "join",
        "gold_sql": (
            "SELECT COUNT(*) FROM Album "
            "JOIN Artist ON Album.ArtistId = Artist.ArtistId "
            "WHERE Artist.Name = 'Iron Maiden';"
        ),
        "expected_behavior": "sql",
    },
    {
        "id": "join_07",
        "question": "Which customers are from Brazil? Show their names.",
        "category": "join",
        "gold_sql": (
            "SELECT FirstName, LastName FROM Customer WHERE Country = 'Brazil';"
        ),
        "expected_behavior": "sql",
    },
    {
        "id": "join_08",
        "question": "What is the total revenue from invoices billed to the USA?",
        "category": "join",
        "gold_sql": (
            "SELECT SUM(Total) FROM Invoice WHERE BillingCountry = 'USA';"
        ),
        "expected_behavior": "sql",
    },
    {
        "id": "join_09",
        "question": "List the genres of tracks in the album 'Big Ones'.",
        "category": "join",
        "gold_sql": (
            "SELECT DISTINCT Genre.Name FROM Genre "
            "JOIN Track ON Genre.GenreId = Track.GenreId "
            "JOIN Album ON Track.AlbumId = Album.AlbumId "
            "WHERE Album.Title = 'Big Ones';"
        ),
        "expected_behavior": "sql",
    },
    {
        "id": "join_10",
        "question": "Which 5 tracks are the longest by duration? Show their names.",
        "category": "join",
        "gold_sql": (
            "SELECT Name FROM Track ORDER BY Milliseconds DESC LIMIT 5;"
        ),
        "expected_behavior": "sql",
    },

    # --- More date filters ---
    {
        "id": "date_04",
        "question": "How many invoices were issued in 2025?",
        "category": "date",
        "gold_sql": (
            "SELECT COUNT(*) FROM Invoice "
            "WHERE InvoiceDate >= '2025-01-01' AND InvoiceDate < '2026-01-01';"
        ),
        "expected_behavior": "sql",
    },
    {
        "id": "date_05",
        "question": "What was the total revenue in 2021?",
        "category": "date",
        "gold_sql": (
            "SELECT SUM(Total) FROM Invoice "
            "WHERE InvoiceDate >= '2021-01-01' AND InvoiceDate < '2022-01-01';"
        ),
        "expected_behavior": "sql",
    },

    # --- More ambiguous ---
    {
        "id": "ambig_04",
        "question": "Which is the best album?",
        "category": "ambiguous",
        "gold_sql": None,
        "expected_behavior": "clarification",
    },
    {
        "id": "ambig_05",
        "question": "Show me recent sales.",
        "category": "ambiguous",
        "gold_sql": None,
        "expected_behavior": "clarification",
    },

    # --- More unanswerable ---
    {
        "id": "unans_04",
        "question": "What is the phone number of the artist Metallica?",
        "category": "unanswerable",
        "gold_sql": None,
        "expected_behavior": "no_answer",
    },
    {
        "id": "unans_05",
        "question": "How many songs were streamed on Spotify last month?",
        "category": "unanswerable",
        "gold_sql": None,
        "expected_behavior": "no_answer",
    },
    # --- Category: hard (adversarial / tricky cases) ---
    {
        "id": "hard_01",
        "question": "Which artist has the most tracks (not albums)?",
        "category": "hard",
        "gold_sql": (
            "SELECT Artist.Name, COUNT(Track.TrackId) AS TrackCount "
            "FROM Artist "
            "JOIN Album ON Artist.ArtistId = Album.ArtistId "
            "JOIN Track ON Album.AlbumId = Track.AlbumId "
            "GROUP BY Artist.ArtistId ORDER BY TrackCount DESC LIMIT 1;"
        ),
        "expected_behavior": "sql",
    },
    {
        "id": "hard_02",
        "question": "Which customers have never made a purchase?",
        "category": "hard",
        "gold_sql": (
            "SELECT Customer.FirstName, Customer.LastName FROM Customer "
            "LEFT JOIN Invoice ON Customer.CustomerId = Invoice.CustomerId "
            "WHERE Invoice.InvoiceId IS NULL;"
        ),
        "expected_behavior": "sql",
    },
    {
        "id": "hard_03",
        "question": "What is the average number of tracks per album?",
        "category": "hard",
        "gold_sql": (
            "SELECT CAST(COUNT(*) AS FLOAT) / COUNT(DISTINCT AlbumId) "
            "FROM Track WHERE AlbumId IS NOT NULL;"
        ),
        "expected_behavior": "sql",
    },
    {
        "id": "hard_04",
        "question": "Which genre generates the most revenue?",
        "category": "hard",
        "gold_sql": (
            "SELECT Genre.Name, SUM(InvoiceLine.UnitPrice * InvoiceLine.Quantity) AS Revenue "
            "FROM Genre "
            "JOIN Track ON Genre.GenreId = Track.GenreId "
            "JOIN InvoiceLine ON Track.TrackId = InvoiceLine.TrackId "
            "GROUP BY Genre.GenreId ORDER BY Revenue DESC LIMIT 1;"
        ),
        "expected_behavior": "sql",
    },
    {
        "id": "hard_05",
        "question": "How many customers have spent more than 40 dollars in total?",
        "category": "hard",
        "gold_sql": (
            "SELECT COUNT(*) FROM ("
            "SELECT CustomerId FROM Invoice "
            "GROUP BY CustomerId HAVING SUM(Total) > 40"
            ");"
        ),
        "expected_behavior": "sql",
    },
    {
        "id": "hard_06",
        "question": "Which employees have never been assigned a customer to support?",
        "category": "hard",
        "gold_sql": (
            "SELECT Employee.FirstName, Employee.LastName FROM Employee "
            "LEFT JOIN Customer ON Customer.SupportRepId = Employee.EmployeeId "
            "WHERE Customer.CustomerId IS NULL;"
        ),
        "expected_behavior": "sql",
    },
    {
        "id": "hard_07",
        "question": "What percentage of tracks have no composer listed?",
        "category": "hard",
        "gold_sql": (
            "SELECT 100.0 * SUM(CASE WHEN Composer IS NULL THEN 1 ELSE 0 END) / COUNT(*) "
            "FROM Track;"
        ),
        "expected_behavior": "sql",
    },
    {
        # Deliberately underspecified: "customers in the USA" could mean
        # Customer.Country or Invoice.BillingCountry. A mature system should
        # notice the ambiguity and ask, rather than silently pick one.
        "id": "hard_08",
        "question": "What is the total spending of customers in the USA?",
        "category": "hard",
        "gold_sql": None,
        "expected_behavior": "clarification",
    },
]


def get_dataset():
    """Return the full golden dataset."""
    return GOLDEN_DATASET


if __name__ == "__main__":
    # Quick sanity check: run every gold_sql against the database and
    # print its result, so we can VERIFY the gold SQL is actually correct.
    from sqlalchemy import create_engine, text

    engine = create_engine("sqlite:///data/chinook.db")

    print(f"Verifying {len(GOLDEN_DATASET)} gold queries...\n")
    for case in GOLDEN_DATASET:
        if case["gold_sql"] is None:
            print(f"[{case['id']}] (no SQL — {case['expected_behavior']})")
            continue
        try:
            with engine.connect() as conn:
                rows = conn.execute(text(case["gold_sql"])).fetchall()
            preview = rows[:3]  # show first 3 rows
            print(f"[{case['id']}] {case['question']}")
            print(f"    -> {len(rows)} rows, sample: {preview}")
        except Exception as e:
            print(f"[{case['id']}] ERROR: {e}")
        print()

        # --- Explore actual date ranges so date-filter questions are realistic ---
    print("\n" + "=" * 50)
    print("DATE RANGE EXPLORATION")
    print("=" * 50)
    with engine.connect() as conn:
        inv = conn.execute(text(
            "SELECT MIN(InvoiceDate), MAX(InvoiceDate) FROM Invoice"
        )).fetchall()
        print("Invoice dates:", inv)

        hire = conn.execute(text(
            "SELECT MIN(HireDate), MAX(HireDate) FROM Employee"
        )).fetchall()
        print("Employee hire dates:", hire)

        # How many invoices per year, to pick a good year for a test question
        per_year = conn.execute(text(
            "SELECT strftime('%Y', InvoiceDate) AS yr, COUNT(*) "
            "FROM Invoice GROUP BY yr ORDER BY yr"
        )).fetchall()
        print("Invoices per year:", per_year)