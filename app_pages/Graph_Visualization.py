import math
import html

import streamlit as st
import streamlit.components.v1 as components
import folium

from folium.plugins import PolyLineTextPath
from streamlit_folium import st_folium
from pyvis.network import Network

from data.table_loader import load_tables
from services.graph_service import GraphService


# ==================================================
# Cached resources
# ==================================================

@st.cache_data(show_spinner="Loading source tables...")
def get_tables():
    return load_tables()


@st.cache_resource
def get_graph_service():
    return GraphService()


# ==================================================
# General helpers
# ==================================================

def safe_html(value):
    """Escape values before inserting them into HTML."""
    return html.escape(str(value if value is not None else ""))


def get_valid_coordinates(node):
    """
    Return (latitude, longitude) if the node has valid coordinates.

    Assumes:
        node.cx = longitude
        node.cy = latitude
    """
    try:
        longitude = float(node.cx)
        latitude = float(node.cy)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(longitude) or not math.isfinite(latitude):
        return None

    if not (-180 <= longitude <= 180):
        return None

    if not (-90 <= latitude <= 90):
        return None

    if latitude == 0 and longitude == 0:
        return None

    return latitude, longitude

def get_valid_polygon_coordinates(node):
    """Return the four OAS corners in Folium's (latitude, longitude) order."""

    corners = [
        (node.bly_coord, node.blx_coord),  # Bottom-left
        (node.tly_coord, node.tlx_coord),  # Top-left
        (node.try_coord, node.trx_coord),  # Top-right
        (node.bry_coord, node.brx_coord),  # Bottom-right
    ]

    try:
        coordinates = [
            (float(latitude), float(longitude))
            for latitude, longitude in corners
        ]
    except (TypeError, ValueError):
        return None

    for latitude, longitude in coordinates:
        if not math.isfinite(latitude) or not math.isfinite(longitude):
            return None

        if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
            return None

    # Close the polygon.
    return coordinates + [coordinates[0]]


def get_order_value(order, *field_names, default=0):
    """Read a value from an order represented by a dict or object."""
    for field_name in field_names:
        if isinstance(order, dict):
            value = order.get(field_name)
        else:
            value = getattr(order, field_name, None)

        if value is not None:
            return value

    return default


def to_number(value):
    try:
        number = float(value or 0)
        return number if math.isfinite(number) else 0.0
    except (TypeError, ValueError):
        return 0.0


def format_number(value):
    return f"{to_number(value):,.2f}"


# ==================================================
# Order metrics
# ==================================================

def calculate_order_metrics(orders):
    """
    Calculate order count, total weight and total loading meters.

    These field aliases cover common order attribute names.
    """
    total_weight = 0.0
    total_loading_meters = 0.0

    for order in orders:
        weight = get_order_value(
            order,
            "weight",
            "total_weight",
            "Weight",
            "WEIGHT",
            "weight_total_planned",
            "WeightTotalPlanned",
            default=0,
        )

        loading_meters = get_order_value(
            order,
            "loading_meters",
            "loading_meter",
            "loadingMeters",
            "LoadingMeters",
            "LoadingMeter",
            "LDM",
            "ldm",
            "loading_meter_planned",
            "LoadingMeterPlanned",
            default=0,
        )

        total_weight += to_number(weight)
        total_loading_meters += to_number(loading_meters)

    return {
        "order_count": len(orders),
        "total_weight": total_weight,
        "total_loading_meters": total_loading_meters,
    }


def calculate_edge_metrics(edges, node_id, direction):
    """
    Sum edge-level weight and loading meters for a node.

    direction='inbound': edges whose target is the node.
    direction='outbound': edges whose source is the node.
    """
    matching_edges = []

    for edge in edges:
        if direction == "inbound" and edge.target == node_id:
            matching_edges.append(edge)
        elif direction == "outbound" and edge.source == node_id:
            matching_edges.append(edge)

    return {
        "connection_count": len(matching_edges),
        "weight": sum(
            to_number(edge.weight_total_planned)
            for edge in matching_edges
        ),
        "loading_meters": sum(
            to_number(edge.loading_meter_planned)
            for edge in matching_edges
        ),
    }


def calculate_node_metrics(node, edges, node_id):
    """Collect inbound/outbound order and connected-edge metrics."""
    inbound_orders = list(node.inbound_orders or [])
    outbound_orders = list(node.outbound_orders or [])

    inbound = calculate_order_metrics(inbound_orders)
    outbound = calculate_order_metrics(outbound_orders)

    inbound_routes = calculate_edge_metrics(
        edges,
        node_id,
        "inbound",
    )

    outbound_routes = calculate_edge_metrics(
        edges,
        node_id,
        "outbound",
    )

    return {
        "inbound": inbound,
        "outbound": outbound,
        "inbound_routes": inbound_routes,
        "outbound_routes": outbound_routes,
    }


# ==================================================
# Styled node information
# ==================================================

def metric_tile(label, value, color, background):
    """Return a small styled HTML metric tile."""
    return f"""
        <div style="
            background:{background};
            border-left:4px solid {color};
            border-radius:7px;
            padding:9px 11px;
            margin-bottom:7px;
            flex:1;
            min-width:105px;
            box-sizing:border-box;
        ">
            <div style="
                font-size:11px;
                color:#475569;
                margin-bottom:4px;
            ">{safe_html(label)}</div>
            <div style="
                font-size:17px;
                font-weight:700;
                color:{color};
                line-height:1.3;
            ">{safe_html(value)}</div>
        </div>
    """


def build_node_popup(node_id, node, position, edges):
    """Create a styled geographic-map popup for an OAS node."""
    metrics = calculate_node_metrics(node, edges, node_id)

    inbound = metrics["inbound"]
    outbound = metrics["outbound"]
    inbound_routes = metrics["inbound_routes"]
    outbound_routes = metrics["outbound_routes"]

    inbound_tiles = (
        metric_tile(
            "Orders",
            f'{inbound["order_count"]:,}',
            "#1d4ed8",
            "#eff6ff",
        )
        + metric_tile(
            "Loading meters",
            f'{inbound["total_loading_meters"]:,.2f} m',
            "#1d4ed8",
            "#eff6ff",
        )
        + metric_tile(
            "Weight",
            f'{inbound["total_weight"]:,.2f}',
            "#1d4ed8",
            "#eff6ff",
        )
    )

    outbound_tiles = (
        metric_tile(
            "Orders",
            f'{outbound["order_count"]:,}',
            "#15803d",
            "#f0fdf4",
        )
        + metric_tile(
            "Loading meters",
            f'{outbound["total_loading_meters"]:,.2f} m',
            "#15803d",
            "#f0fdf4",
        )
        + metric_tile(
            "Weight",
            f'{outbound["total_weight"]:,.2f}',
            "#15803d",
            "#f0fdf4",
        )
    )

    return f"""
    <div style="
        width:340px;
        max-width:340px;
        font-family:Arial,sans-serif;
        color:#0f172a;
        font-size:12px;
    ">
        <div style="
            background:#172554;
            color:white;
            border-radius:8px;
            padding:12px 14px;
            margin-bottom:10px;
        ">
            <div style="
                font-size:10px;
                text-transform:uppercase;
                letter-spacing:1px;
                opacity:0.8;
            ">OAS AREA</div>
            <div style="
                font-size:17px;
                font-weight:700;
                margin-top:3px;
                overflow-wrap:anywhere;
            ">{safe_html(node_id)}</div>
            <div style="font-size:10px;margin-top:5px;opacity:0.85;">
                {position[0]:.6f}, {position[1]:.6f}
            </div>
        </div>

        <div style="
            font-weight:700;
            color:#1d4ed8;
            margin:5px 0 7px;
            font-size:13px;
        ">INBOUND</div>

        <div style="display:flex;gap:6px;">
            {inbound_tiles}
        </div>

        <div style="
            background:#f8fafc;
            padding:7px 9px;
            border-radius:6px;
            margin-bottom:10px;
            color:#475569;
        ">
            Incoming connections:
            <b>{inbound_routes["connection_count"]:,}</b>
        </div>

        <div style="
            font-weight:700;
            color:#15803d;
            margin:5px 0 7px;
            font-size:13px;
        ">OUTBOUND</div>

        <div style="display:flex;gap:6px;">
            {outbound_tiles}
        </div>

        <div style="
            background:#f8fafc;
            padding:7px 9px;
            border-radius:6px;
            margin-bottom:5px;
            color:#475569;
        ">
            Outgoing connections:
            <b>{outbound_routes["connection_count"]:,}</b>
        </div>
    </div>
    """


def build_node_hover(node_id, node, edges):
    """Return plain-text hover details for PyVis (no raw HTML markup)."""
    metrics = calculate_node_metrics(node, edges, node_id)
    inbound = metrics["inbound"]
    outbound = metrics["outbound"]

    return (
        f"OAS AREA: {node_id}\n\n"
        f"INBOUND\n"
        f"Orders: {inbound['order_count']:,}\n"
        f"Loading meters: {format_number(inbound['total_loading_meters'])} m\n"
        f"Weight: {format_number(inbound['total_weight'])}\n\n"
        f"OUTBOUND\n"
        f"Orders: {outbound['order_count']:,}\n"
        f"Loading meters: {format_number(outbound['total_loading_meters'])} m\n"
        f"Weight: {format_number(outbound['total_weight'])}"
    )


# ==================================================
# Geographic map
# ==================================================

def build_geographic_map(graph, visible_ids, visible_edges):
    """
    Create a Folium map with larger OAS markers, styled node popups,
    and directed route tooltips.
    """
    coordinates = {}

    for node_id in visible_ids:
        node = graph.nodes[node_id]
        position = get_valid_coordinates(node)

        if position is not None:
            coordinates[node_id] = position

    if not coordinates:
        return None, 0, 0

    center_latitude = sum(
        position[0] for position in coordinates.values()
    ) / len(coordinates)

    center_longitude = sum(
        position[1] for position in coordinates.values()
    ) / len(coordinates)

    geographic_map = folium.Map(
        location=[center_latitude, center_longitude],
        zoom_start=6,
        tiles="OpenStreetMap",
        control_scale=True,
    )

    route_layer = folium.FeatureGroup(
        name="Directed routes",
        show=True,
    )

    node_layer = folium.FeatureGroup(
        name="OAS centre points",
        show=True,
    )

    polygon_layer = folium.FeatureGroup(
        name="OAS Area Seal polygons",
        show=False,
    )

    # --------------------------------------------------
    # Directed edges
    # --------------------------------------------------

    drawn_edges = 0

    for edge in visible_edges:
        source = edge.source
        target = edge.target

        if source not in coordinates or target not in coordinates:
            continue

        source_position = coordinates[source]
        target_position = coordinates[target]

        if source == target:
            continue

        order_count = len(set(edge.customer_orders))
        loading_meters = float(edge.loading_meter_planned or 0)
        weight = float(edge.weight_total_planned or 0)

        popup_html = f"""
        <div style="
            width: 260px;
            font-family: Arial, sans-serif;
            color: #1f2937;
            border-radius: 10px;
            overflow: hidden;
        ">
            <div style="
                background: linear-gradient(135deg, #154360, #2874a6);
                color: white;
                padding: 13px 15px;
            ">
                <div style="
                    font-size: 11px;
                    text-transform: uppercase;
                    letter-spacing: 1px;
                    opacity: 0.85;
                ">
                    OAS Route
                </div>
                <div style="
                    font-size: 15px;
                    font-weight: bold;
                    margin-top: 5px;
                    overflow-wrap: anywhere;
                ">
                    {safe_html(str(source))}
                </div>
                <div style="font-size: 18px; margin: 3px 0;">↓</div>
                <div style="
                    font-size: 15px;
                    font-weight: bold;
                    overflow-wrap: anywhere;
                ">
                    {safe_html(str(target))}
                </div>
            </div>

            <div style="
                padding: 12px;
                background: #f8fafc;
            ">
                <div style="
                    display: grid;
                    grid-template-columns: 1fr 1fr;
                    gap: 8px;
                ">
                    <div style="
                        background: white;
                        border: 1px solid #dbeafe;
                        border-radius: 8px;
                        padding: 10px;
                    ">
                        <div style="font-size: 11px; color: #64748b;">
                            Customer Orders
                        </div>
                        <div style="
                            font-size: 21px;
                            font-weight: bold;
                            color: #1d4ed8;
                            margin-top: 4px;
                        ">
                            {order_count:,}
                        </div>
                    </div>

                    <div style="
                        background: white;
                        border: 1px solid #d1fae5;
                        border-radius: 8px;
                        padding: 10px;
                    ">
                        <div style="font-size: 11px; color: #64748b;">
                            Loading Meters
                        </div>
                        <div style="
                            font-size: 21px;
                            font-weight: bold;
                            color: #047857;
                            margin-top: 4px;
                        ">
                            {loading_meters:,.2f}
                        </div>
                    </div>

                    <div style="
                        grid-column: 1 / -1;
                        background: white;
                        border: 1px solid #e5e7eb;
                        border-radius: 8px;
                        padding: 10px;
                    ">
                        <div style="font-size: 11px; color: #64748b;">
                            Total Planned Weight
                        </div>
                        <div style="
                            font-size: 20px;
                            font-weight: bold;
                            color: #374151;
                            margin-top: 4px;
                        ">
                            {weight:,.2f}
                        </div>
                    </div>
                </div>
            </div>
        </div>
        """

        route = folium.PolyLine(
            locations=[source_position, target_position],
            color="#e74c3c",
            weight=4,
            opacity=0.85,
            tooltip=folium.Tooltip(
                f"""
                <div style="
                    font-family: Arial, sans-serif;
                    padding: 5px 8px;
                    min-width: 150px;
                ">
                    <b>{safe_html(str(source))}</b>
                    <span style="color: #e74c3c;"> → </span>
                    <b>{safe_html(str(target))}</b>
                    <hr style="margin: 5px 0;">
                    Orders: <b>{order_count:,}</b><br>
                    Loading meters: <b>{loading_meters:,.2f}</b><br>
                    Weight: <b>{weight:,.2f}</b>
                    <div style="
                        color: #64748b;
                        font-size: 10px;
                        margin-top: 5px;
                    ">
                        Click route for details
                    </div>
                </div>
                """,
                sticky=True,
            ),
            popup=folium.Popup(
                popup_html,
                max_width=300,
                min_width=270,
            ),
        )

        route.add_to(route_layer)

        # Direction indicators along the route.
        PolyLineTextPath(
            route,
            "  ▶  ",
            repeat=True,
            offset=7,
            attributes={
                "fill": "#ffffff",
                "stroke": "#c0392b",
                "stroke-width": "2px",
                "font-weight": "bold",
                "font-size": "14",
            },
        ).add_to(route_layer)

        drawn_edges += 1

    # --------------------------------------------------
    # OAS nodes
    # --------------------------------------------------

    for node_id, position in coordinates.items():
        node = graph.nodes[node_id]
        polygon_coordinates = get_valid_polygon_coordinates(node)

        if polygon_coordinates is not None:
            folium.Polygon(
                locations=polygon_coordinates,
                color="#2563eb",
                weight=2,
                fill=True,
                fill_color="#60a5fa",
                fill_opacity=0.20,
                tooltip=folium.Tooltip(
                    f"<b>OAS Area:</b> {safe_html(node_id)}",
                    sticky=True,
                ),
                popup=folium.Popup(
                    f"<b>OAS Area:</b> {safe_html(node_id)}",
                    max_width=300,
                ),
            ).add_to(polygon_layer)
        degree_count = sum(
            1 for edge in visible_edges
            if edge.source == node_id or edge.target == node_id
        )

        inbound_count = len(node.inbound_orders)
        outbound_count = len(node.outbound_orders)

        if inbound_count and outbound_count:
            node_color = "#2563eb"
        elif outbound_count:
            node_color = "#dc2626"
        elif inbound_count:
            node_color = "#16a34a"
        else:
            node_color = "#6b7280"

        popup_html = build_node_popup(
            node_id,
            node,
            position,
            visible_edges,
        )

        folium.CircleMarker(
            location=position,
            radius=11 + min(degree_count, 12) * 0.6,
            color=node_color,
            weight=3,
            fill=True,
            fill_color=node_color,
            fill_opacity=0.92,
            tooltip=folium.Tooltip(
                f"<b>OAS Area:</b> {safe_html(node_id)}",
                sticky=True,
            ),
            popup=folium.Popup(
                popup_html,
                max_width=390,
            ),
        ).add_to(node_layer)

    route_layer.add_to(geographic_map)
    node_layer.add_to(geographic_map)
    polygon_layer.add_to(geographic_map)
    folium.LayerControl(
        collapsed=False,
    ).add_to(geographic_map)

    return geographic_map, len(coordinates), drawn_edges


# ==================================================
# Page: Graph Visualization
# ==================================================

def render_page():

    st.title("Graph Visualization")
    st.caption(
        "Explore directed OAS connections as a network and on a map."
    )

    # --------------------------------------------------
    # Load data
    # --------------------------------------------------

    try:
        tables = get_tables()
        service = get_graph_service()
    except Exception as exc:
        st.error(f"Could not load source tables: {exc}")
        return

    # --------------------------------------------------
    # Select OAS layer - unchanged
    # --------------------------------------------------

    layer = st.selectbox(
        "Select OAS grid layer",
        options=list(service.LAYERS.keys()),
        key="graph_visualization_layer",
    )

    with st.spinner(f"Building {layer} network..."):
        try:
            graph = service.build_graph(tables, layer)
        except Exception as exc:
            st.error(f"Could not build graph: {exc}")
            return

    nodes = list(graph.nodes.values())
    edges = list(graph.edges.values())

    # --------------------------------------------------
    # Summary metrics
    # --------------------------------------------------

    unique_orders = {
        order_id
        for edge in edges
        for order_id in edge.customer_orders
    }

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Total nodes",
        f"{len(nodes):,}",
    )

    col2.metric(
        "Total directed edges",
        f"{len(edges):,}",
    )

    col3.metric(
        "Customer orders",
        f"{len(unique_orders):,}",
    )

    if not nodes:
        st.info("No nodes are available for this OAS layer.")
        return

    # --------------------------------------------------
    # Visualization controls - unchanged
    # --------------------------------------------------

    # col1, col2 = st.columns(2)

    # with col1:
    #     max_nodes = st.slider(
    #         "Maximum nodes to display",
    #         min_value=10,
    #         max_value=500,
    #         value=100,
    #         step=10,
    #         key="graph_max_nodes",
    #     )

    # with col2:
    #     show_self_loops = st.checkbox(
    #         "Show self-loops in network",
    #         value=False,
    #         key="graph_show_self_loops",
    #     )

    # --------------------------------------------------
    # Calculate node degree
    # --------------------------------------------------

    degree = {
        node.area_seal: 0
        for node in nodes
    }

    for edge in edges:
        degree[edge.source] = degree.get(edge.source, 0) + 1

        if edge.target != edge.source:
            degree[edge.target] = degree.get(edge.target, 0) + 1

    # visible_ids = {
    #     node_id
    #     for node_id, _ in sorted(
    #         degree.items(),
    #         key=lambda item: item[1],
    #         reverse=True,
    #     )[:max_nodes]
    # }
    visible_ids = {
        node_id
        for node_id, _ in sorted(
            degree.items(),
            key=lambda item: item[1],
            reverse=True,
        )
    }

    visible_edges = [
        edge
        for edge in edges
        if edge.source in visible_ids
        and edge.target in visible_ids
        and 
        (True or edge.source != edge.target)
        
    ]

    # ==================================================
    # Section 1: Geographic Map
    # ==================================================

    st.divider()
    st.subheader("Geographic Map")
    st.caption(
        "Larger circles represent OAS areas. Hover over a route for "
        "its metrics and click a node for styled inbound/outbound "
        "order, loading-meter and weight information."
    )

    geographic_map, mapped_nodes, mapped_edges = build_geographic_map(
        graph,
        visible_ids,
        visible_edges,
    )

    if geographic_map is None:
        st.warning(
            "No selected nodes have valid geographic coordinates. "
            "Check that node.cx contains longitude and node.cy "
            "contains latitude."
        )
    else:
        st_folium(
            geographic_map,
            height=650,
            use_container_width=True,
            returned_objects=[],
            key="oas_geographic_map",
        )

        map_col1, map_col2 = st.columns(2)

        map_col1.metric(
            "Mapped nodes",
            f"{mapped_nodes:,}",
        )

        map_col2.metric(
            "Mapped directed routes",
            f"{mapped_edges:,}",
        )

        if mapped_nodes < len(visible_ids):
            st.warning(
                f"{len(visible_ids) - mapped_nodes:,} selected nodes "
                "were omitted from the map because their coordinates "
                "were missing or invalid."
            )

        expected_map_edges = sum(
            1 for edge in visible_edges
            if edge.source != edge.target
        )

        if mapped_edges < expected_map_edges:
            st.info(
                "Some routes were omitted from the map because one "
                "or both endpoint nodes lacked valid coordinates."
            )

    # ==================================================
    # Section 2: Interactive Network Graph
    # ==================================================

    st.divider()
    st.subheader("Interactive Directed Network")

    net = Network(
        height="650px",
        width="100%",
        directed=True,
        bgcolor="#ffffff",
        font_color="#222222",
        cdn_resources="in_line",
    )

    net.barnes_hut()

    for node_id in visible_ids:
        node = graph.nodes[node_id]

        metrics = calculate_node_metrics(
            node,
            edges,
            node_id,
        )

        inbound = metrics["inbound"]
        outbound = metrics["outbound"]

        if inbound["order_count"] and outbound["order_count"]:
            node_color = {
                "background": "#2563eb",  # Blue: both
                "border": "#1e40af",
            }
        elif inbound["order_count"]:
            node_color = {
                "background": "#dc2626",  # Red: inbound only
                "border": "#991b1b",
            }
        elif outbound["order_count"]:
            node_color = {
                "background": "#16a34a",  # Green: outbound only
                "border": "#166534",
            }
        else:
            node_color = {
                "background": "#9ca3af",  # Gray: neither
                "border": "#4b5563",
            }

        node_hover = build_node_hover(
            node_id,
            node,
            edges,
        )

        net.add_node(
            node_id,
            label=str(node_id),
            title=node_hover,
            color=node_color,
            size=25 + min(degree.get(node_id, 0), 35),
            borderWidth=3,
            font={
                "size": 16,
                "bold": True,
            },
        )

    for edge in visible_edges:
        net.add_edge(
            edge.source,
            edge.target,
            arrows="to",
            width=3,
            title=(
                f"Customer orders: {len(set(edge.customer_orders))}\n"
                f"Loading meter: {edge.loading_meter_planned:.2f}\n"
                f"Weight: {edge.weight_total_planned:.2f}"
            ),
        )

    net.set_options("""
    {
    "interaction": {
        "hover": true,
        "tooltipDelay": 100,
        "navigationButtons": true,
        "keyboard": true,
        "dragNodes": true,
        "dragView": true,
        "zoomView": true
    },
    "nodes": {
        "shape": "dot",
        "font": {
        "size": 16
        },
        "scaling": {
        "min": 25,
        "max": 60
        },
        "physics": true
    },
    "edges": {
        "width": 3,
        "smooth": {
        "enabled": false
        },
        "arrows": {
        "to": {
            "enabled": true,
            "scaleFactor": 0.8
        }
        }
    },
    "physics": {
        "enabled": true,
        "solver": "barnesHut",
        "barnesHut": {
        "gravitationalConstant": -2000,
        "centralGravity": 0.15,
        "springLength": 180,
        "springConstant": 0.025,
        "damping": 0.8,
        "avoidOverlap": 0.5
        },
        "maxVelocity": 15,
        "minVelocity": 0.5,
        "timestep": 0.35,
        "stabilization": {
        "enabled": true,
        "iterations": 500,
        "updateInterval": 50,
        "fit": true
        }
    }
    }
    """)

    components.html(
        net.generate_html(),
        height=680,
        scrolling=True,
    )

    st.caption(
        f"Displaying {len(visible_ids):,} nodes and "
        f"{len(visible_edges):,} directed routes in the network."
    )
