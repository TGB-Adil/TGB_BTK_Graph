
import pandas as pd

from services.api_client import get_table


# Key = logical table name
# Value = complete API URL
TABLE_URLS = {
    # the graph that hzas areaseal from and to and also have customer order
    "Grid_Connector_500km": "http://btkdb.tgb.software:8005/partial/csv?db=Customer_order_3days_ahead&table=GraphConnector_CustomerOrder_500km",
    "Grid_Connector_100km": "http://btkdb.tgb.software:8005/partial/csv?db=Customer_order_3days_ahead&table=GraphConnector_CustomerOrder_100km",
    "Grid_Connector_50km": "http://btkdb.tgb.software:8005/partial/csv?db=Customer_order_3days_ahead&table=GraphConnector_CustomerOrder_50km",
    "Grid_Connector_10km": "http://btkdb.tgb.software:8005/partial/csv?db=Customer_order_3days_ahead&table=GraphConnector_CustomerOrder_10km",
    "Grid_Connector_5km": "http://btkdb.tgb.software:8005/partial/csv?db=Customer_order_3days_ahead&table=GraphConnector_CustomerOrder_5km",
    "Grid_Connector_1km": "http://btkdb.tgb.software:8005/partial/csv?db=Customer_order_3days_ahead&table=GraphConnector_CustomerOrder_1km",
    "Grid_Connector_500m": "http://btkdb.tgb.software:8005/partial/csv?db=Customer_order_3days_ahead&table=GraphConnector_CustomerOrder_500m",
    "Grid_Connector_100m": "http://btkdb.tgb.software:8005/partial/csv?db=Customer_order_3days_ahead&table=GraphConnector_CustomerOrder_100m",
    "Grid_Connector_50m": "http://btkdb.tgb.software:8005/partial/csv?db=Customer_order_3days_ahead&table=GraphConnector_CustomerOrder_50m",
    "Grid_Connector_10m": "http://btkdb.tgb.software:8005/partial/csv?db=Customer_order_3days_ahead&table=GraphConnector_CustomerOrder_10m",
    # the oas code cx and cy here
    "OAS_500km":"http://btkdb.tgb.software:8005/partial/csv?db=Customer_order_3days_ahead&table=OAS_L1_500km",
    "OAS_100km":"http://btkdb.tgb.software:8005/partial/csv?db=Customer_order_3days_ahead&table=OAS_L2_100km",
    "OAS_50km":"http://btkdb.tgb.software:8005/partial/csv?db=Customer_order_3days_ahead&table=OAS_L3_50km",
    "OAS_10km":"http://btkdb.tgb.software:8005/partial/csv?db=Customer_order_3days_ahead&table=OAS_L4_10km",
    "OAS_5km":"http://btkdb.tgb.software:8005/partial/csv?db=Customer_order_3days_ahead&table=OAS_L5_5km",
    "OAS_1km":"http://btkdb.tgb.software:8005/partial/csv?db=Customer_order_3days_ahead&table=OAS_L6_1km",
    "OAS_500m":"http://btkdb.tgb.software:8005/partial/csv?db=Customer_order_3days_ahead&table=OAS_L7_500m",
    "OAS_100m":"http://btkdb.tgb.software:8005/partial/csv?db=Customer_order_3days_ahead&table=OAS_L8_100m",
    "OAS_50m":"http://btkdb.tgb.software:8005/partial/csv?db=Customer_order_3days_ahead&table=OAS_L9_50m",
    "OAS_10m":"http://btkdb.tgb.software:8005/partial/csv?db=Customer_order_3days_ahead&table=OAS_L10_10m",
    # then attributes needed:
    "Customer_Order_Details_Table":"http://btkdb.tgb.software:8005/partial/csv?db=Customer_order_3days_ahead&table=DV_customer_order_detail_full_data_V2_TV_BTK_6b229421_customerorderdetail_Customer_Order_Detail_Customer_Order", # in here we have customer order that we have in each graph connector and we can make customer order details
    "Loading_Meter": "http://btkdb.tgb.software:8005/partial/csv?db=Customer_order_3days_ahead&table=DV_customer_order_detail_full_data_V2_TV_BTK_6b229421_customerorderdetail_LoadingMeterPlanned", # linked to the customer order details (Customer order -> customerOrderdetails{customer order key} -> attributes{customer order details key})
    "Total_Weight": "http://btkdb.tgb.software:8005/partial/csv?db=Customer_order_3days_ahead&table=DV_customer_order_detail_full_data_V2_TV_BTK_6b229421_customerorderdetail_WeightTotalPlanned"
}


def load_tables() -> dict:
    tables = {}

    for name, url in TABLE_URLS.items():
        if not url.strip():
            raise ValueError(
                f"URL has not been configured for table: {name}"
            )

        print(f"Loading {name}...")

        tables[name] = get_table(url)

        print(
            f"Loaded {name}: "
            f"{len(tables[name]):,} rows"
        )


    return tables