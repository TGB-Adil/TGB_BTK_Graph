import pandas as pd

from models.node import Node
from models.edge import Edge
from models.graph import Graph


class GraphService:

    LAYERS = {
        "500km": ("Grid_Connector_500km", "OAS_500km"),
        "100km": ("Grid_Connector_100km", "OAS_100km"),
        "50km": ("Grid_Connector_50km", "OAS_50km"),
        "10km": ("Grid_Connector_10km", "OAS_10km"),
        "5km": ("Grid_Connector_5km", "OAS_5km"),
        "1km": ("Grid_Connector_1km", "OAS_1km"),
        "500m": ("Grid_Connector_500m", "OAS_500m"),
        "100m": ("Grid_Connector_100m", "OAS_100m"),
        "50m": ("Grid_Connector_50m", "OAS_50m"),
        "10m": ("Grid_Connector_10m", "OAS_10m"),
    }

    @staticmethod
    def _number(value) -> float:
        if pd.isna(value):
            return 0.0
        return float(value)

    def build_graph(self, tables: dict, layer: str) -> Graph:
        if layer not in self.LAYERS:
            raise ValueError(f"Unsupported layer: {layer}")

        connector_name, oas_name = self.LAYERS[layer]

        connector_df = tables[connector_name]
        oas_df = tables[oas_name]
        details_df = tables["Customer_Order_Details_Table"]
        loading_df = tables["Loading_Meter"]
        weight_df = tables["Total_Weight"]

        graph = Graph(layer=layer)

        # One coordinate record per area seal.
        coordinates = (
            oas_df.drop_duplicates("as_code")
            .set_index("as_code")
        )

        # Attach detail IDs to customer orders.
        details = details_df[
            ["PAYLOAD_ID", "CustomerOrderID"]
        ].copy()

        details = details.rename(
            columns={"PAYLOAD_ID": "DETAIL_ID"}
        )

        # Metadata lookup by customer-order-detail ID.
        loading = loading_df[
            ["PAYLOAD_ID", "LoadingMeterPlanned"]
        ].rename(
            columns={
                "PAYLOAD_ID": "DETAIL_ID",
                "LoadingMeterPlanned": "LOADING_METER",
            }
        )

        weight = weight_df[
            ["PAYLOAD_ID", "WeightTotalPlanned"]
        ].rename(
            columns={
                "PAYLOAD_ID": "DETAIL_ID",
                "WeightTotalPlanned": "WEIGHT",
            }
        )

        detail_metadata = (
            details
            .merge(loading, on="DETAIL_ID", how="left")
            .merge(weight, on="DETAIL_ID", how="left")
        )

        detail_metadata["LOADING_METER"] = (
            detail_metadata["LOADING_METER"].fillna(0)
        )
        detail_metadata["WEIGHT"] = (
            detail_metadata["WEIGHT"].fillna(0)
        )

        # An order can have multiple details, so aggregate
        # detail values to customer-order level for each edge.
        order_metadata = (
            detail_metadata
            .groupby("CustomerOrderID", as_index=False)
            .agg(
                LOADING_METER=("LOADING_METER", "sum"),
                WEIGHT=("WEIGHT", "sum"),
            )
        )

        connector = connector_df.merge(
            order_metadata,
            left_on="CUSTOMER_ORDER",
            right_on="CustomerOrderID",
            how="left",
        )

        connector["LOADING_METER"] = (
            connector["LOADING_METER"].fillna(0)
        )
        connector["WEIGHT"] = connector["WEIGHT"].fillna(0)
        
        connector = connector.drop_duplicates(
            subset=[
                "CUSTOMER_ORDER",
                "FROM_AREASEAL",
                "TO_AREASEAL",
            ]
        )
        # Build directed edges and accumulate node totals.
        for row in connector.to_dict(orient="records"):
            source = row["FROM_AREASEAL"]
            target = row["TO_AREASEAL"]

            if pd.isna(source) or pd.isna(target):
                continue

            source = str(source)
            target = str(target)

            for node_id in (source, target):
                if node_id not in graph.nodes:
                    coord = (
                        coordinates.loc[node_id]
                        if node_id in coordinates.index
                        else None
                    )

                    node = Node(
                        area_seal=node_id,
                        cx=(
                            float(coord["as_cx_wgs"])
                            if coord is not None
                            and pd.notna(coord["as_cx_wgs"])
                            else None
                        ),
                        cy=(
                            float(coord["as_cy_wgs"])
                            if coord is not None
                            and pd.notna(coord["as_cy_wgs"])
                            else None
                        ),
                    )

                    graph.add_node(node)

            loading_meter = self._number(row["LOADING_METER"])
            weight_total = self._number(row["WEIGHT"])
            order_id = str(row["CUSTOMER_ORDER"])

            edge = graph.add_edge(
                Edge(source=source, target=target)
            )

            # Each connector row contributes one order record.
            order_record = {
                "customer_order": order_id,
                "loading_meter_planned": loading_meter,
                "weight_total_planned": weight_total,
            }

            edge.orders.append(order_record)
            edge.customer_orders.append(order_id)
            edge.loading_meter_planned += loading_meter
            edge.weight_total_planned += weight_total

            # Directional node totals.
            # Self-loops count once on the node, not twice.
            if source == target:
                node = graph.nodes[source]
                node.inbound_loading_meter += loading_meter
                node.outbound_loading_meter += loading_meter
                node.inbound_weight += weight_total
                node.outbound_weight += weight_total
                node.inbound_orders.append(order_record)
                node.outbound_orders.append(order_record)
            else:
                source_node = graph.nodes[source]
                target_node = graph.nodes[target]

                source_node.outbound_loading_meter += loading_meter
                source_node.outbound_weight += weight_total
                source_node.outbound_orders.append(order_record)

                target_node.inbound_loading_meter += loading_meter
                target_node.inbound_weight += weight_total
                target_node.inbound_orders.append(order_record)

        return graph