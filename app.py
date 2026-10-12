import streamlit as st
import pandas as pd

from data.table_loader import load_tables
from services.graph_service import GraphService
from app_pages.Graph_Visualization import render_page
from app_pages.Area_Seal_Explorer import render_page as render_area_seal_explorer


# ==================================================
# Page configuration
# ==================================================

st.set_page_config(
    page_title="TGB OAS Graph Visualizer",
    page_icon="./TGBIMG.jpg",
    layout="wide",
)
st.markdown(
    """
    <style>
    [data-testid="stSidebarNav"] span {
        font-size: 18px !important;
    }

    [data-testid="stSidebarNav"] li {
        min-height: 48px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ==================================================
# Shared cached resources
# ==================================================

@st.cache_data(show_spinner="Loading source tables...")
def get_tables():
    return load_tables()


@st.cache_resource
def get_graph_service():
    return GraphService()


# ==================================================
# Page 1: Dashboard
# ==================================================

def dashboard_page():
    st.title("OAS Graph Visualizer")
    st.caption(
        "Dashboard — customer-order routes across OAS grid layers"
    )

    try:
        tables = get_tables()
        graph_service = get_graph_service()
    except Exception as exc:
        st.error(f"Could not load source tables: {exc}")
        return

    layer = st.selectbox(
        "Select OAS grid layer",
        options=list(graph_service.LAYERS.keys()),
        key="dashboard_layer",
    )

    with st.spinner(f"Building graph for {layer}..."):
        try:
            graph = graph_service.build_graph(tables, layer)
        except Exception as exc:
            st.error(f"Could not build graph: {exc}")
            return

    nodes = list(graph.nodes.values())
    edges = list(graph.edges.values())

    unique_orders = {
        order_id
        for edge in edges
        for order_id in edge.customer_orders
    }

    self_loops = sum(
        edge.source == edge.target
        for edge in edges
    )

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Nodes", f"{len(nodes):,}")
    col2.metric("Directed edges", f"{len(edges):,}")
    col3.metric("Customer orders", f"{len(unique_orders):,}")
    col4.metric("Self-loops", f"{self_loops:,}")

    col5, col6 = st.columns(2)

    col5.metric(
        "Loading meter total",
        f"{sum(edge.loading_meter_planned for edge in edges):,.2f}",
    )

    col6.metric(
        "Weight total",
        f"{sum(edge.weight_total_planned for edge in edges):,.2f}",
    )

    # Directed routes.
    st.divider()
    st.subheader(f"Directed routes — {layer}")

    edge_df = pd.DataFrame([
        {
            "From area seal": edge.source,
            "To area seal": edge.target,
            "Customer orders": len(set(edge.customer_orders)),
            "Loading meter planned": edge.loading_meter_planned,
            "Weight total planned": edge.weight_total_planned,
            "Self-loop": edge.source == edge.target,
        }
        for edge in edges
    ])

    st.dataframe(
        edge_df,
        use_container_width=True,
        hide_index=True,
    )

    # Nodes.
    st.divider()
    st.subheader("Nodes")

    node_df = pd.DataFrame([
        {
            "Area seal": node.area_seal,
            "Longitude": node.cx,
            "Latitude": node.cy,
            "Inbound orders": len(node.inbound_orders),
            "Outbound orders": len(node.outbound_orders),
            "Inbound loading meter": node.inbound_loading_meter,
            "Outbound loading meter": node.outbound_loading_meter,
            "Inbound weight": node.inbound_weight,
            "Outbound weight": node.outbound_weight,
        }
        for node in nodes
    ])

    st.dataframe(
        node_df,
        use_container_width=True,
        hide_index=True,
    )


# ==================================================
# Page 2: Graph Visualization
# ==================================================

def graph_visualization_page():
    render_page()
    
def area_seal_explorer_page():
    render_area_seal_explorer()


area_seal_explorer = st.Page(
    area_seal_explorer_page,
    title="Area Seal Explorer",
    icon="📍",
)

# ==================================================
# Navigation
# ==================================================

dashboard = st.Page(
    dashboard_page,
    title="Dashboard",
    icon="📊",
    default=True,
)

graph_visualization = st.Page(
    graph_visualization_page,
    title="Graph Visualization",
    icon="🕸️",
)

navigation = st.navigation([
    dashboard,
    graph_visualization,
    area_seal_explorer,
])

navigation.run()