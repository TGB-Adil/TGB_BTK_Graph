
import streamlit as st
import streamlit.components.v1 as components

from pyvis.network import Network

from data.table_loader import load_tables
from services.graph_service import GraphService


@st.cache_data(show_spinner="Loading source tables...")
def get_tables():
    return load_tables()


@st.cache_resource
def get_graph_service():
    return GraphService()


def render_page():
    st.title("Graph Visualization")
    st.caption("Explore directed connections between OAS areas")

    try:
        tables = get_tables()
        service = get_graph_service()
    except Exception as exc:
        st.error(f"Could not load source tables: {exc}")
        return

    # Keep the actual supported layer names from GraphService.
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

    col1, col2, col3 = st.columns(3)

    col1.metric("Total nodes", f"{len(nodes):,}")
    col2.metric("Total directed edges", f"{len(edges):,}")

    unique_orders = {
        order_id
        for edge in edges
        for order_id in edge.customer_orders
    }

    col3.metric("Customer orders", f"{len(unique_orders):,}")

    if not nodes:
        st.info("No nodes are available for this OAS layer.")
        return

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
            "Show self-loops",
            value=False,
            key="graph_show_self_loops",
        )

    # --------------------------------------------------------
    # NODE DEGREE
    # --------------------------------------------------------

    degree = {
        node.area_seal: 0
        for node in nodes
    }

    for edge in edges:
        degree[edge.source] = degree.get(edge.source, 0) + 1

        if edge.target != edge.source:
            degree[edge.target] = degree.get(edge.target, 0) + 1

    # Select the most connected nodes.
    visible_ids = {
        node_id
        for node_id, _ in sorted(
            degree.items(),
            key=lambda item: item[1],
            reverse=True,
        )[:max_nodes]
    }

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

    # --------------------------------------------------------
    # CALCULATE NODE INBOUND / OUTBOUND METRICS
    # --------------------------------------------------------
    #
    # Order counts come from the node's existing order sets.
    # Planned loading meters and weight are summed from the
    # edges in each direction.
    #
    # Incoming edge: edge.target == node.area_seal
    # Outgoing edge: edge.source == node.area_seal
    # --------------------------------------------------------

    node_metrics = {}

    for node_id, node in graph.nodes.items():
        incoming_edges = [
            edge for edge in edges
            if edge.target == node_id
        ]

        outgoing_edges = [
            edge for edge in edges
            if edge.source == node_id
        ]

        inbound_weight = sum(
            edge.weight_total_planned or 0
            for edge in incoming_edges
        )

        inbound_loading_meters = sum(
            edge.loading_meter_planned or 0
            for edge in incoming_edges
        )

        outbound_weight = sum(
            edge.weight_total_planned or 0
            for edge in outgoing_edges
        )

        outbound_loading_meters = sum(
            edge.loading_meter_planned or 0
            for edge in outgoing_edges
        )

        node_metrics[node_id] = {
            "inbound_orders": len(node.inbound_orders),
            "inbound_weight": inbound_weight,
            "inbound_loading_meters": inbound_loading_meters,
            "outbound_orders": len(node.outbound_orders),
            "outbound_weight": outbound_weight,
            "outbound_loading_meters": outbound_loading_meters,
            "incoming_routes": len(incoming_edges),
            "outgoing_routes": len(outgoing_edges),
        }

    # --------------------------------------------------------
    # BUILD INTERACTIVE PYVIS NETWORK
    # --------------------------------------------------------

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
        metrics = node_metrics[node_id]

        # Display all requested node metadata on hover.
        node_title = (
            f"Area: {node_id}\n"
            "\n"
            "INBOUND\n"
            f"Orders: {metrics['inbound_orders']:,}\n"
            f"Weight: {metrics['inbound_weight']:,.2f}\n"
            f"Loading meters: "
            f"{metrics['inbound_loading_meters']:,.2f} m\n"
            f"Incoming routes: {metrics['incoming_routes']:,}\n"
            "\n"
            "OUTBOUND\n"
            f"Orders: {metrics['outbound_orders']:,}\n"
            f"Weight: {metrics['outbound_weight']:,.2f}\n"
            f"Loading meters: "
            f"{metrics['outbound_loading_meters']:,.2f} m\n"
            f"Outgoing routes: {metrics['outgoing_routes']:,}"
        )

        net.add_node(
            node_id,
            label=str(node_id),
            title=node_title,
            size=12 + min(degree.get(node_id, 0), 30),
        )

    for edge in visible_edges:
        net.add_edge(
            edge.source,
            edge.target,
            arrows="to",
            title=(
                f"From: {edge.source}\n"
                f"To: {edge.target}\n"
                f"Customer orders: "
                f"{len(set(edge.customer_orders)):,}\n"
                f"Loading meters: "
                f"{edge.loading_meter_planned:,.2f}\n"
                f"Weight: {edge.weight_total_planned:,.2f}"
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

    st.subheader("Interactive directed network")

    components.html(
        net.generate_html(),
        height=680,
        scrolling=True,
    )

    st.caption(
        f"Displaying {len(visible_ids):,} selected nodes and "
        f"{len(visible_edges):,} directed routes. "
        "Hover over nodes to inspect inbound/outbound totals "
        "and over edges to inspect route details."
    )

    # --------------------------------------------------------
    # INSPECT AN AREA
    # --------------------------------------------------------

    st.divider()
    st.subheader("Inspect an area")

    selected_id = st.selectbox(
        "Area seal",
        options=sorted(graph.nodes.keys()),
        key="graph_inspected_area",
    )

    selected = graph.nodes[selected_id]
    metrics = node_metrics[selected_id]

    incoming = [
        edge for edge in edges
        if edge.target == selected_id
    ]

    outgoing = [
        edge for edge in edges
        if edge.source == selected_id
    ]

    st.markdown(f"### Area: {selected_id}")

    inbound_col1, inbound_col2, inbound_col3 = st.columns(3)

    inbound_col1.metric(
        "Inbound orders",
        f"{metrics['inbound_orders']:,}",
    )

    inbound_col2.metric(
        "Inbound weight",
        f"{metrics['inbound_weight']:,.2f}",
    )

    inbound_col3.metric(
        "Inbound loading meters",
        f"{metrics['inbound_loading_meters']:,.2f} m",
    )

    outbound_col1, outbound_col2, outbound_col3 = st.columns(3)

    outbound_col1.metric(
        "Outbound orders",
        f"{metrics['outbound_orders']:,}",
    )

    outbound_col2.metric(
        "Outbound weight",
        f"{metrics['outbound_weight']:,.2f}",
    )

    outbound_col3.metric(
        "Outbound loading meters",
        f"{metrics['outbound_loading_meters']:,.2f} m",
    )

    st.metric(
        "Total connected routes",
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
                    "Loading meters": edge.loading_meter_planned,
                    "Weight": edge.weight_total_planned,
                }
                for edge in incoming
            ],
            width="stretch",
            hide_index=True,
        )

    with right:
        st.markdown("**Outgoing routes**")

        st.dataframe(
            [
                {
                    "To": edge.target,
                    "Customer orders": len(set(edge.customer_orders)),
                    "Loading meters": edge.loading_meter_planned,
                    "Weight": edge.weight_total_planned,
                }
                for edge in outgoing
            ],
            width="stretch",
            hide_index=True,
        )