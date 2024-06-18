import json

import networkx as nx
import plotly.graph_objects as go

# Load the JSON data
with open("taskgraph.json", "r") as file:
    data = json.load(file)

# Define the specific task to extract hierarchy
specific_task = "test-apk-fenix-debug"


# Function to extract dependencies for the specific task up to a certain depth
def extract_hierarchy(task_id, task_dict, depth, current_level=0):
    if (
        current_level < depth
        and task_id in task_dict
        and "dependencies" in task_dict[task_id]
    ):
        dependencies = task_dict[task_id]["dependencies"]
        return {
            task_id: {
                dep: extract_hierarchy(dep, task_dict, depth, current_level + 1)
                for dep in dependencies.values()
            }
        }
    return {}


# Set the depth limit
depth_limit = 3

# Create a hierarchy tree for the specific task up to the specified depth
hierarchy_tree = extract_hierarchy(specific_task, data, depth_limit)


# Function to add nodes and edges to the graph
def add_edges(graph, tree):
    for parent, children in tree.items():
        for child, grand_children in children.items():
            graph.add_edge(parent, child)
            add_edges(graph, grand_children)


# Create a directed graph
G = nx.DiGraph()

# Add nodes and edges to the graph
add_edges(G, hierarchy_tree)


# Define a function for hierarchical positioning
def hierarchy_pos(G, root=None, width=1.0, vert_gap=1.0, vert_loc=0, xcenter=0.5):
    pos = _hierarchy_pos(G, root, width, vert_gap, vert_loc, xcenter, pos={})
    return pos


def _hierarchy_pos(
    G,
    root,
    width=2.0,  # Increase the width
    vert_gap=2.0,  # Increase the vertical gap
    vert_loc=0,
    xcenter=0.5,
    pos=None,
    parent=None,
    parsed=None,
):
    if pos is None:
        pos = {root: (xcenter, vert_loc)}
    else:
        pos[root] = (xcenter, vert_loc)

    children = list(G.neighbors(root))
    if not isinstance(G, nx.DiGraph) and parent is not None:
        children.remove(parent)

    if len(children) != 0:
        dx = width / len(children)
        nextx = xcenter - width / 2 - dx / 2
        for child in children:
            nextx += dx
            pos = _hierarchy_pos(
                G,
                child,
                width=dx,
                vert_gap=vert_gap,
                vert_loc=vert_loc - vert_gap,
                xcenter=nextx,
                pos=pos,
                parent=root,
            )
    return pos


# Get positions for nodes
pos = hierarchy_pos(G, root=specific_task)

# Create edges
edge_x = []
edge_y = []
for edge in G.edges():
    x0, y0 = pos[edge[0]]
    x1, y1 = pos[edge[1]]
    edge_x.append(x0)
    edge_x.append(x1)
    edge_x.append(None)
    edge_y.append(y0)
    edge_y.append(y1)
    edge_y.append(None)

edge_trace = go.Scatter(
    x=edge_x, y=edge_y, line=dict(width=1, color="#888"), hoverinfo="none", mode="lines"
)

# Create nodes
node_x = []
node_y = []
for node in G.nodes():
    x, y = pos[node]
    node_x.append(x)
    node_y.append(y)

node_trace = go.Scatter(
    x=node_x,
    y=node_y,
    mode="markers+text",
    text=list(G.nodes()),
    textposition="top center",
    hoverinfo="text",
    marker=dict(
        showscale=True,
        colorscale="YlGnBu",
        size=10,
        colorbar=dict(
            thickness=15, title="Node Connections", xanchor="left", titleside="right"
        ),
    ),
)

# Create the figure
fig = go.Figure(
    data=[edge_trace, node_trace],
    layout=go.Layout(
        title=f"Dependency Tree for {specific_task}",
        titlefont_size=16,
        showlegend=False,
        hovermode="closest",
        margin=dict(b=20, l=5, r=5, t=40),
        annotations=[dict(text="", showarrow=False, xref="paper", yref="paper")],
        xaxis=dict(showgrid=False, zeroline=False),
        yaxis=dict(showgrid=False, zeroline=False),
    ),
)

# Show the figure
fig.show()

# Write out HTML
fig.write_html("dependency_tree.html")
