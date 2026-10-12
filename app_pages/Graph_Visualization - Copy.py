import math

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
# Geographic coordinate helpers
# ==================================================

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

    # Reject (0, 0), which often represents missing coordinates.
    if latitude == 0 and longitude == 0:
        return None

    return latitude, longitude


# ==================================================
# Build geographic map
# ==================================================

def build_geographic_map(graph, visible_ids, visible_edges):
    """
    Create a Folium map with:
        - OAS nodes as circle markers
        - Directed routes as lines
        - Arrow symbols along route lines
        - Node and edge information in tooltips
    """

    # Keep only visible nodes with valid geographic coordinates.
    coordinates = {}

    for node_id in visible_ids:
        node = graph.nodes[node_id]
        position = get_valid_coordinates(node)

        if position is not None:
            coordinates[node_id] = position

    if not coordinates:
        return None, 0, 0

    # Center map on the visible geographic nodes.
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

    # --------------------------------------------------
    # Separate map layers
    # --------------------------------------------------

    route_layer = folium.FeatureGroup(
        name="Directed routes",
        show=True,
    )

    node_layer = folium.FeatureGroup(
        name="OAS nodes",
        show=True,
    )

    # --------------------------------------------------
    # Draw directed edges
    # --------------------------------------------------

    drawn_edges = 0

    for edge in visible_edges:
        source = edge.source
        target = edge.target

        # Both endpoints must have valid coordinates.
        if source not in coordinates or target not in coordinates:
            continue

        source_position = coordinates[source]
        target_position = coordinates[target]

        # Skip self-loops on the geographic map.
        # They are still available in the graph and route tables.
        if source == target:
            continue

        route_tooltip = (
            f"From: {source}<br>"
            f"To: {target}<br>"
            f"Customer orders: {len(set(edge.customer_orders))}<br>"
            f"Loading meter: {edge.loading_meter_planned:.2f}<br>"
            f"Weight: {edge.weight_total_planned:.2f}"
        )

        route = folium.PolyLine(
            locations=[
                source_position,
                target_position,
            ],
            color="#d62728",
            weight=2,
            opacity=0.7,
            tooltip=folium.Tooltip(
                route_tooltip,
                sticky=True,
            ),
        )

        route.add_to(route_layer)

        # Add repeating arrow symbols to show route direction.
        PolyLineTextPath(
            route,
            "▶",
            repeat=True,
            offset=7,
            attributes={
                "fill": "#d62728",
                "font-weight": "bold",
                "font-size": "12",
            },
        ).add_to(route_layer)

        drawn_edges += 1

    # --------------------------------------------------
    # Draw OAS nodes
    # --------------------------------------------------

    for node_id, position in coordinates.items():
        node = graph.nodes[node_id]

        inbound_count = len(node.inbound_orders)
        outbound_count = len(node.outbound_orders)
        degree_count = (
            len([
                edge for edge in visible_edges
                if edge.source == node_id
            ])
            +
            len([
                edge for edge in visible_edges
                if edge.target == node_id
                and edge.source != node_id
            ])
        )

        popup_html = f"""
        <div style="width: 230px;">
            <h4>OAS Area</h4>
            <b>Area seal:</b> {node_id}<br>
            <b>Latitude:</b> {position[0]:.6f}<br>
            <b>Longitude:</b> {position[1]:.6f}<br>
            <b>Inbound orders:</b> {inbound_count}<br>
            <b>Outbound orders:</b> {outbound_count}<br>
            <b>Visible connections:</b> {degree_count}
        </div>
        """

        folium.CircleMarker(
            location=position,
            radius=6 + min(degree_count, 10) * 0.5,
            color="#154360",
            weight=1,
            fill=True,
            fill_color="#3498db",
            fill_opacity=0.85,
            tooltip=f"OAS Area: {node_id}",
            popup=folium.Popup(
                popup_html,
                max_width=300,
            ),
        ).add_to(node_layer)

    route_layer.add_to(geographic_map)
    node_layer.add_to(geographic_map)

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
    # Select OAS layer
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
    # Visualization controls
    # --------------------------------------------------

    col1, col2 = st.columns(2)

    with col1:
        max_nodes = st.slider(
            "Maximum nodes to display",
            min_value=10,
            max_value=500,
            value=100,
            step=10,
            key="graph_max_nodes",
        )

    with col2:
        show_self_loops = st.checkbox(
            "Show self-loops in network",
            value=False,
            key="graph_show_self_loops",
        )

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

    # Choose the most connected nodes.
    visible_ids = {
        node_id
        for node_id, _ in sorted(
            degree.items(),
            key=lambda item: item[1],
            reverse=True,
        )[:max_nodes]
    }

    # Edges are displayed only when both endpoints are selected.
    visible_edges = [
        edge
        for edge in edges
        if edge.source in visible_ids
        and edge.target in visible_ids
        and (
            show_self_loops
            or edge.source != edge.target
        )
    ]

    # ==================================================
    # Section 1: Geographic Map
    # ==================================================

    st.divider()
    st.subheader("Geographic Map")
    st.caption(
        "Blue circles represent OAS areas. Red directed lines "
        "represent routes between areas. Hover over a line for "
        "route details and click a node for its coordinates."
    )

    geographic_map, mapped_nodes, mapped_edges = (
        build_geographic_map(
            graph,
            visible_ids,
            visible_edges,
        )
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

        if mapped_edges < sum(
            1 for edge in visible_edges
            if edge.source != edge.target
        ):
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

        net.add_node(
            node_id,
            label=str(node_id),
            title=(
                f"Area: {node_id}\n"
                f"Inbound orders: {len(node.inbound_orders)}\n"
                f"Outbound orders: {len(node.outbound_orders)}"
            ),
            size=12 + min(degree.get(node_id, 0), 30),
        )

    for edge in visible_edges:
        net.add_edge(
            edge.source,
            edge.target,
            arrows="to",
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
        "navigationButtons": true,
        "keyboard": true
      },
      "edges": {
        "arrows": {
          "to": {
            "enabled": true,
            "scaleFactor": 0.7
          }
        }
      },
      "physics": {
        "stabilization": {
          "iterations": 150
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

    # ==================================================
    # Section 3: Inspect an OAS Area
    # ==================================================

    st.divider()
    st.subheader("Inspect an Area")

    selected_id = st.selectbox(
        "Area seal",
        options=sorted(graph.nodes.keys()),
        key="graph_inspected_area",
    )

    selected = graph.nodes[selected_id]

    incoming = [
        edge
        for edge in edges
        if edge.target == selected_id
    ]

    outgoing = [
        edge
        for edge in edges
        if edge.source == selected_id
    ]

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Inbound orders",
        f"{len(selected.inbound_orders):,}",
    )

    col2.metric(
        "Outbound orders",
        f"{len(selected.outbound_orders):,}",
    )

    col3.metric(
        "Connected routes",
        f"{len(incoming) + len(outgoing):,}",
    )

    left, right = st.columns(2)

    with left:
        st.markdown("**Incoming routes**")

        st.dataframe(
            [
                {
                    "From": edge.source,
                    "Customer orders": len(set(edge.customer_orders)),
                    "Loading meter": edge.loading_meter_planned,
                    "Weight": edge.weight_total_planned,
                }
                for edge in incoming
            ],
            use_container_width=True,
            hide_index=True,
        )

    with right:
        st.markdown("**Outgoing routes**")

        st.dataframe(
            [
                {
                    "To": edge.target,
                    "Customer orders": len(set(edge.customer_orders)),
                    "Loading meter": edge.loading_meter_planned,
                    "Weight": edge.weight_total_planned,
                }
                for edge in outgoing
            ],
            use_container_width=True,
            hide_index=True,
        )