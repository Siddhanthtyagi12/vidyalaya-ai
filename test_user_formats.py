import psycopg2

def test_user_formats():
    project_ref = "dcrdwpkoytycopvnriqn"
    host = "3.111.105.85" # ap-south-1
    password = "siddhant@vanshika1234"
    
    formats = [
        f"postgres.{project_ref}",
        f"postgres@{project_ref}",
        f"{project_ref}.postgres",
        project_ref,
        "postgres"
    ]
    
    for user in formats:
        for port in [6543, 5432]:
            print(f"Testing User: {user} on Port: {port}...")
            try:
                conn = psycopg2.connect(
                    host=host,
                    user=user,
                    password=password,
                    database="postgres",
                    port=port,
                    sslmode="require",
                    connect_timeout=5
                )
                print(f"!!! SUCCESS !!! User: {user}, Port: {port}")
                conn.close()
                return
            except Exception as e:
                print(f"FAILED: {e}")

if __name__ == "__main__":
    test_user_formats()
