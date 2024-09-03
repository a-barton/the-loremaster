import psycopg2
import boto3
from botocore.exceptions import ClientError
import json
import os


def handler(event, context):
    try:
        print("EVENT RECEIVED:")
        print(json.dumps(event))
        db_creds_secret_name = os.environ.get("DB_CREDS_SECRET_NAME")
        db_creds = get_secret(db_creds_secret_name)

        # Connect to RDS
        conn = psycopg2.connect(
            dbname=db_creds["dbname"],
            user=db_creds["username"],
            password=db_creds["password"],
            host=db_creds["host"],
            port=db_creds["port"],
        )

        cur = conn.cursor()

        # Execute PGVector extension installation
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")

        # Close the cursor and connection
        cur.close()
        conn.close()
    
        return {"statusCode": 200}

    except Exception as e:
        print(f"Error: {str(e)}")
        return {"statusCode": 500, "body": str(e)}
    


def get_secret(secret_name: str) -> dict:
    secret_client = boto3.client("secretsmanager")
    try:
        get_secret_value_response = secret_client.get_secret_value(SecretId=secret_name)
        return json.loads(get_secret_value_response["SecretString"])
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceNotFoundException":
            print("The requested secret was not found")
        elif e.response["Error"]["Code"] == "InvalidParameterException":
            print("The request parameter was invalid")
        else:
            print(e)
