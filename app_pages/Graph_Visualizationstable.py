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

    # Calculate node degree.
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

    # Only include edges whose endpoints are visible.
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

    # Build the interactive PyVis network.
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

    st.subheader("Interactive directed network")

    components.html(
        net.generate_html(),
        height=680,
        scrolling=True,
    )

    st.caption(
        f"Displaying {len(visible_ids):,} selected nodes and "
        f"{len(visible_edges):,} directed routes. "
        "Hover over nodes and edges to inspect details."
    )

    # Inspect an area.
    st.divider()
    st.subheader("Inspect an area")

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