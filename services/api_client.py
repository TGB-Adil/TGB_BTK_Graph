
import io
import requests
import pandas as pd


def get_table(url: str, params: dict | None = None) -> pd.DataFrame:
    """
    Fetch a CSV table from an API and return it as a DataFrame.

    Args:
        url: API endpoint URL.
        params: Query parameters to pass to the API.

    Returns:
        pandas.DataFrame containing the CSV data.
    """
    response = requests.get(
        url,
        params=params,
        timeout=120
    )
    response.raise_for_status()

    return pd.read_csv(io.BytesIO(response.content))


if __name__ == "__main__":
    url = "http://btkdb.tgb.software:8005/partial/csv?db=Customer_order_3days_ahead&table=GraphConnector_CustomerOrder_500km"

    df = get_table(url)

    print(df.head())
    print("Rows:", len(df))
    print("Columns:", df.columns.tolist())