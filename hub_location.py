
# #vasilis code
import time
import pandas as pd
from dash import dcc, html, Input, Output, State, callback_context
from concurrent.futures import ThreadPoolExecutor
import geopandas as gpd
import networkx as nx
import gurobipy as gp
from gurobipy import GRB
from collections import defaultdict
import pyproj
import random
import dash
from dash import dcc, html, Output, Input, callback_context
import dash_bootstrap_components as dbc
import dash_leaflet as dl
import pickle
import numpy as np
from dash.exceptions import PreventUpdate
from concurrent.futures import ThreadPoolExecutor
import plotly.express as px
import pyproj
import random
import matplotlib.pyplot as plt
from shapely.geometry import LineString
from geopy.distance import geodesic
from pyproj import Proj, transform
from pyproj import CRS, Transformer
import plotly.graph_objects as go
import time
import ast
import json
from itertools import product
import os
import matlab.engine

def mparouti():
    def load_scenario_energy_cost_parameters(seed: float = None):
        # set seed if provided
        if seed:
            np.random.seed(seed=seed)

        congestion_tiers = {
            'road': {
                'no': 1,
                'light': 1.3,
                'moderate': 1.65,
                'heavy': 2.2
            },
            'rail': {
                'no': 1,
                'light': 1.1,
                'moderate': 1.35,
                'heavy': 1.8
            },
            'waterway': {
                'no': 1,
                'light': 1.03,
                'moderate': 1.25,
                'heavy': 1.6
            }}

        # Define speed and cost multipliers for each mode
        dist_factor = {'road': 3.67, 'rail': 0.25, 'waterway': 0.05}
        # cost_multipliers = {'road': 1.67, 'rail': 0.65, 'waterway': 0.05} #usd per ton-mile 1.95
        # TODO: in what units? miles/hour?
        speeds = {'road': 60, 'rail': 55, 'waterway': 10}
        # value_of_time_multiplier = {'high': 21, 'moderate': 12, 'low': 0.7}
        value_of_time = {'high': 21, 'moderate': 12, 'low': 0.7}  # usd per ton-hour
        # value_of_time_multiplier_delay = {'high': 1.5, 'moderate': 0.10, 'low': 0.005}

        # TODO: add in parameter to allow for these to be random or not and add in a seed for it for reproducibility; may want to feed these into the model as fixed values and allow for us/the user to provide random values or not
        # Dwell times in hours
        # dwell_times = {'road': (2, 2), 'rail': (12, 12), 'waterway': (16, 16)}
        # TODO: can allow for randomization to occur in this method with a passable random seed (as above)
        dwell_times = {'road': 4, 'rail': 12, 'waterway': 16}

        # $/ton
        transfer_costs = {
            ('road', 'road'): 0,
            ('rail', 'rail'): 0,
            ('waterway', 'waterway'): 0,
            ('road', 'rail'): 1.62,
            ('rail', 'road'): 1.62,
            ('road', 'waterway'): 1.62,
            ('waterway', 'road'): 1.62,
            ('rail', 'waterway'): 1.62,
            ('waterway', 'rail'): 1.62}

        # base arc capacities by mode, when not specified for each arc
        # TODO: in what units? should be tons
        base_arc_mode_capacities = {
            'road': 6 * 4810 * 1e6,
            'rail': 6 * 4810 * 1e6,
            'waterway': 6 * 4810 * 1e6,
        }

        # base node capacities at candidate hubs, when not specified for each node
        # TODO: generalize these to allow for node-specific capacities
        # TODO: in what units? should be tons
        base_node_capacity = 6 * 4810 * 1e6

        emissions_rates = {  # g CO2/ton-mile
            'road': {'diesel': 65.25, 'battery-electric': 21.71, 'biodiesel': 56.75, 'hydrogen': 27.73,
                     'e-fuel': 25.54},
            'rail': {'diesel': 25.75, 'battery-electric': 6.65, 'biodiesel': 22.42, 'hydrogen': 9.43, 'e-fuel': 5.54},
            # 'waterway': {'diesel': 10.89, 'battery-electric': 3.29, 'biodiesel': 9.52, 'hydrogen': 4.00, 'e-fuel': 3.5}
            'waterway': {'diesel': 10.89, 'battery-electric': 3.29, 'biodiesel': 9.52, 'hydrogen': 4.00, 'e-fuel': 3.5}
        }
        fuel_cost = {  # c per-tone mile
            'road': {'diesel': 2.49, 'battery-electric': 1.01, 'biodiesel': 2.13, 'hydrogen': 1.44, 'e-fuel': 1.98},
            'rail': {'diesel': 0.99, 'battery-electric': 0.31, 'biodiesel': 0.85, 'hydrogen': 0.49, 'e-fuel': 0.46},
            # 'waterway': {'diesel': 0.37, 'battery-electric': 0.15, 'biodiesel': 0.35, 'hydrogen': 0.21, 'e-fuel': 0.21}
            'waterway': {'diesel': 0.37, 'battery-electric': 0.15, 'biodiesel': 0.35, 'hydrogen': 0.21, 'e-fuel': 0.21}
        }
        s_c_carbon = 185e-6  # $ / g CO2

        return (dist_factor, speeds, value_of_time, dwell_times, transfer_costs, base_arc_mode_capacities,
                base_node_capacity, emissions_rates, fuel_cost, s_c_carbon)

    def congestion_cost_calculations(G: nx.MultiDiGraph, arc_capacities=None, model_package=None):
        #   - updated travel times per link (i.e., by mode)

        # if model package exists
        if model_package:
            # calculate congestion impacts
            # if no arc capacities, initialize as empty dict
            if arc_capacities is None:
                arc_capacities = dict()
            # congestion calculation updates and function should keep track of:
            #   - current solution flows on each link (i.e., link flows must be summed across all OD demands)
            #   - link capacity information and BPR parameters
            # unpack model components
            _, x, _ = model_package

            # G.graph['model_parameters'] = {
            #     'candidate_hub_pairs': candidate_hub_pairs,
            #     'hub_costs': hub_costs,
            #     'arc_costs_record': arc_costs_record,
            #     'arc_data_record': arc_data_record,
            #     'arcs': arcs,
            #     'arc_costs': arc_costs
            #     'od_pairs': od_pairs
            # }
            arcs = G.graph['model_parameters']['arcs']
            arc_data_record = G.graph['model_parameters']['arc_data_record']
            # od_pairs = G.graph['model_parameters']['od_pairs']

            # compute the total link flows for each link
            arc_flows = {(i, j): 0 for i, j, _ in arcs}
            for i, j, q in arcs:
                arc_flows[i, j] += x[i, j, q].X

            # coefficients for congestion functions at the links
            alpha_values = {'road': 0.15, 'rail': 0.15, 'waterway': 0.15}
            beta_values = {'road': 4.0, 'rail': 4.0, 'waterway': 4.0}

            # initialize base congestion travel times as 0; increased congestion travel time [hours]
            congestion_travel_time_increase = {(i, j): 0 for i, j in arc_flows.keys()}
            # for each of the links
            for (i, j,), a_flow in arc_flows.items():
                # get the link type
                link_type = G.edges[i, j, 0]['link_type']
                # if link type is not virtual
                if link_type not in {'O_link', 'D_link', 'transfer'}:
                    # extract the BPR parameters for this mode
                    alpha = alpha_values[link_type]
                    beta = beta_values[link_type]
                    # if arc has a capacity
                    if (i, j) in arc_capacities.items():
                        # get base free flow travel time [hours]
                        free_flow_travel_time = arc_data_record['travel_time']
                        # increased congestion travel time [hours], relative to the free flow travel time
                        congestion_travel_time_increase[i, j] = free_flow_travel_time * (
                                    (1 + alpha * (a_flow / arc_capacities[i, j]) ** beta) - 1)
                    # otherwise, if arc is uncapacitated, increased congestion travel time stays as 0
            return congestion_travel_time_increase

        # otherwise, return no congestion levels
        return None

    def run_model_congestion_iterations(G: nx.MultiDiGraph, od_pairs: list, hub_budget: float = None,
                                        hub_costs: dict = None,
                                        mode_tech: dict = None, length_attr='miles',
                                        capped_arcs=False, capped_nodes=False, arc_capacities: dict = None,
                                        node_capacities: dict = None,
                                        fixed_hubs=None, restricted_nodes=None, restricted_edges=None,
                                        congestion_level=None, congestion=False,
                                        seed: float = None,
                                        max_iter=100, time_limit=3600, relative_change_tolerance=0.01):
        # run the iterative congestion model, updating the congestion-related travel times after each solution
        #   - initial congestion will be modeled at 0
        #   - use BPR function
        #   - terminate based on <max_iter>, <relative_change_tolerance>, or <time_limit> criteria
        #       - is <relative_change_tolerance> based on the objective function

        iter = 0
        solution_time_out = False
        relative_difference = np.inf
        incumbent_obj_value = np.inf
        model_package = None
        total_runtime = 0
        # while max iteration not exceeded, solution time limit not reached, and relative change tolerance not reached, continue iterating
        while iter < max_iter or not solution_time_out or relative_difference > relative_change_tolerance:
            # calculate congestion times based on current solution
            congestion_travel_time_increase = congestion_cost_calculations(G=G, arc_capacities=arc_capacities,
                                                                           model_package=model_package)
            # pass new congestion times to next model iteration and solve
            G, model_package, runtime = run_model(G=G, od_pairs=od_pairs, hub_budget=hub_budget, hub_costs=hub_costs,
                                                  mode_tech=mode_tech,
                                                  length_attr=length_attr, capped_arcs=capped_arcs,
                                                  capped_nodes=capped_nodes,
                                                  arc_capacities=arc_capacities, node_capacities=node_capacities,
                                                  fixed_hubs=fixed_hubs,
                                                  restricted_nodes=restricted_nodes, restricted_edges=restricted_edges,
                                                  congestion_travel_time_increase=congestion_travel_time_increase,
                                                  model_package=model_package, solution_time_limit=time_limit,
                                                  seed=seed)
            # update remaining solution time limit
            time_limit -= runtime
            # add to total runtime
            total_runtime += runtime
            # if solution has timed out
            solution_time_out = time_limit <= 0
            # update iteration counter
            iter += 1
            # calculate the relative difference between the successive objective function values
            m, _, _ = model_package
            relative_difference = (incumbent_obj_value - m.objVal) / incumbent_obj_value
            # update the incumbent objective value
            incumbent_obj_value = m.objVal

        print(f'Terminated after: '
              f'\n \t {iter} out of {max_iter} iterations '
              f'\n {total_runtime} total runtime '
              f'\n within {relative_difference} of between successive objectives')

        return G

    def transform_results_to_viz(optimization_results):
        transformed_results = []

        for line in optimization_results:
            if "demand is" in line:
                # Extract the origin, destination, and total demand from the header line
                origin, destination = line.split(" to ")[0], line.split(" to ")[1].split(":")[0]
                origin = origin.split("_")[0] if "_" in origin else origin
                destination = destination.split("_")[0] if "_" in destination else destination
                # demand = int(line.split("demand is ")[1].split(" units")[0])
                demand = int(float(line.split("demand is ")[1].split(" units")[0]))

                # Add the total demand entry
                transformed_results.append((origin, destination, demand, 'total_demand'))
            elif "->" in line:
                # Extract flows and modes
                segments = line.strip().split(", flow: ")
                mode_info = segments[0].split(": ")
                mode = mode_info[1].strip()
                flow = int(float(segments[1].split(" ")[0]))
                nodes = mode_info[0].split(" -> ")
                start_node = nodes[0].strip()
                end_node = nodes[1].strip()

                # Simplify node names for visualization if needed
                start_node = start_node.split("_")[0] if "_" in start_node else start_node
                end_node = end_node.split("_")[0] if "_" in end_node else end_node

                # Skip transfer, O_link, and D_link nodes
                if mode.lower() == "transfer" or mode.lower() in ["o_link", "d_link"] or start_node == end_node:
                    continue

                # Append the transformed result
                transformed_results.append((start_node, end_node, flow, mode))
        return transformed_results

    def generate_viz_results(flows_by_od, G, open_hubs):
        optimization_results = []
        hub_ids = []  # List to store unique hub IDs

        # Extract unique hub IDs from open_hubs
        for hub_pair in open_hubs:
            for hub in hub_pair:
                hub_id = hub.split("_")[0] if "_" in hub else hub
                if hub_id not in hub_ids:
                    hub_ids.append(hub_id)

        # Process each OD pair
        for (k, l, demand, commodity), flow_list in flows_by_od.items():
            if flow_list:  # Only process if there's flow
                # Add the total demand entry
                optimization_results.append(f"{k} to {l}: demand is {demand} units")

                # Create a directed graph for this OD pair to trace the path
                flow_graph = nx.DiGraph()
                for i, j, flow_value in flow_list:
                    flow_graph.add_edge(i, j, flow=flow_value)

                # Find all paths from origin to destination for the OD pair
                for path in nx.all_simple_paths(flow_graph, source=k, target=l):
                    # For each path, extract each edge in sequence
                    for i, j in zip(path[:-1], path[1:]):
                        flow_value = flow_graph[i][j]['flow']
                        link_type = "Unknown"
                        for key in G[i][j]:
                            link_type = G[i][j][key].get("link_type", "Unknown")  # Get link type for the edge
                            break  # Only consider the first key
                        optimization_results.append(f"     {i} -> {j}: {link_type}, flow: {flow_value:.2f} units")

        # Transform the results to the desired visualization format
        return transform_results_to_viz(optimization_results), hub_ids
    #-----------------------------------------

    #------------------------------------------------------------------------------------------------------------------------------

def init():
    nodes_gdf = gpd.read_file("hub_loc_files/filtered_nodes.shp")
    water_edges_gdf = gpd.read_file("hub_loc_files/national_network/water_links/water_links.shp")
    rail_edges_gdf_BNSF = gpd.read_file("hub_loc_files/national_network/BNSF_base_links/BNSF_base_links.shp")
    # rail_edges_gdf_CN = gpd.read_file("hub_loc_files/national_network/CN_base_links/CN_base_links.shp")
    # rail_edges_gdf_CPKC = gpd.read_file("hub_loc_files/national_network/CPKC_base_links/CPKC_base_links.shp")
    # rail_edges_gdf_CSXT = gpd.read_file("hub_loc_files/national_network/CSXT_base_links/CSXT_base_links.shp")
    # rail_edges_gdf_NS = gpd.read_file("hub_loc_files/national_network/NS_base_links/NS_base_links.shp")
    rail_edges_gdf_UP = gpd.read_file("hub_loc_files/national_network/UP_base_links/UP_base_links.shp")
    # road_edges_gdf = gpd.read_file("hub_loc_files/national_network/NHWN_links_clean/NHWN_links_clean.shp")

    to_crs = 'EPSG:4326'
    to_epsg = '4326'
    if nodes_gdf.crs is not None:
        nodes_gdf.to_crs(crs=to_crs, inplace=True)
    else:
        nodes_gdf.to_crs(epsg=to_epsg, inplace=True)

    if water_edges_gdf.crs is not None:
        water_edges_gdf.to_crs(crs=to_crs, inplace=True)
    else:
        water_edges_gdf.to_crs(epsg=to_epsg, inplace=True)

    if 'id' not in nodes_gdf.columns:
        nodes_gdf["id"] = range(len(nodes_gdf))
    if 'id' not in water_edges_gdf.columns:
        water_edges_gdf["id"] = range(len(water_edges_gdf))
    if 'id' not in rail_edges_gdf_BNSF.columns:
        rail_edges_gdf_BNSF["id"] = range(len(rail_edges_gdf_BNSF))
    # if 'id' not in rail_edges_gdf_CN.columns:
    #     rail_edges_gdf_CN["id"] = range(len(rail_edges_gdf_CN))
    # if 'id' not in rail_edges_gdf_CPKC.columns:
    #     rail_edges_gdf_CPKC["id"] = range(len(rail_edges_gdf_CPKC))
    # if 'id' not in rail_edges_gdf_CSXT.columns:
    #     rail_edges_gdf_CSXT["id"] = range(len(rail_edges_gdf_CSXT))
    # if 'id' not in rail_edges_gdf_NS.columns:
    #     rail_edges_gdf_NS["id"] = range(len(rail_edges_gdf_NS))
    if 'id' not in rail_edges_gdf_UP.columns:
        rail_edges_gdf_UP["id"] = range(len(rail_edges_gdf_UP))
    # if 'id' not in road_edges_gdf.columns:
    #     road_edges_gdf["id"] = range(len(road_edges_gdf))

    if 'size' not in nodes_gdf.columns:
        nodes_gdf["size"] = 2  # Default size

    color_map = {
        "rail": "red",
        "road": "green",
        "water": "blue",
        np.nan: "grey",  # For NaN/NULL values
        None: "grey"  # Ensure None values also get grey
    }
    nodes_gdf["color"] = nodes_gdf["modeType"].map(color_map).fillna("grey")

    def extract_line_coords(geometry):
        if geometry.geom_type == "LineString":
            return [list(geometry.coords)]
        elif geometry.geom_type == "MultiLineString":
            return [list(line.coords) for line in geometry.geoms]
        else:
            return []

    water_edges_gdf["color"] = "#0077BE"
    rail_edges_gdf_BNSF["color"] = "orange"
    # rail_edges_gdf_CN["color"] = "green"
    # rail_edges_gdf_CPKC["color"] = "grey"
    # rail_edges_gdf_CSXT["color"] = "yellow"
    # rail_edges_gdf_NS["color"] = "navy"
    rail_edges_gdf_UP["color"] = "purple"
    # road_edges_gdf["color"] = "black"

    water_edges_gdf["coordinates"] = water_edges_gdf.geometry.apply(extract_line_coords)
    rail_edges_gdf_BNSF["coordinates"] = rail_edges_gdf_BNSF.geometry.apply(extract_line_coords)
    # rail_edges_gdf_CN["coordinates"] = rail_edges_gdf_CN.geometry.apply(extract_line_coords)
    # rail_edges_gdf_CPKC["coordinates"] = rail_edges_gdf_CPKC.geometry.apply(extract_line_coords)
    # rail_edges_gdf_CSXT["coordinates"] = rail_edges_gdf_CSXT.geometry.apply(extract_line_coords)
    # rail_edges_gdf_NS["coordinates"] = rail_edges_gdf_NS.geometry.apply(extract_line_coords)
    rail_edges_gdf_UP["coordinates"] = rail_edges_gdf_UP.geometry.apply(extract_line_coords)
    # road_edges_gdf["coordinates"] = road_edges_gdf.geometry.apply(extract_line_coords)
    scenario_data = pd.read_csv("hub_loc_files/scenario_data.csv")  # Ensure this file contains relevant values

    return nodes_gdf, water_edges_gdf, rail_edges_gdf_BNSF, rail_edges_gdf_UP, scenario_data

def get_hub_location(app, nodes_gdf, water_edges_gdf, rail_edges_gdf_BNSF, rail_edges_gdf_UP, scenario_data):
    od_pairs = []
    selected_nodes = []
    return html.Div([
    # Header with Images and Title
    html.Div([
        html.Div([
            # html.Img(src=app.get_asset_url("Picture1.png"),
            #          style={"width": "150px", "height": "auto", "marginRight": "10px"}),
            html.Img(src=app.get_asset_url("NUTC_logo.jpg"),
                     style={"width": "300px", "height": "auto"})
        ], style={"width": "20%", "display": "flex", "justifyContent": "flex-start",              "paddingLeft": "20px",
              "paddingRight": "20px"}),
        html.Div(html.H1("Multimodal Facility Location and Routing Optimization",
                         style={"textAlign": "center", "whiteSpace": "normal", "wordWrap": "break-word"}),
                 style={"width": "60%", "display": "inline-block", "verticalAlign": "middle"}),
        html.Div(html.Img(src=app.get_asset_url("VU_logo.png"),
                          style={"width": "200px", "height": "auto"}),
                 style={"width": "20%", "display": "inline-block", "textAlign": "right",              "paddingLeft": "20px",
              "paddingRight": "20px"})
    ], style={"display": "flex", "alignItems": "center", "justifyContent": "space-between",
              "marginBottom": "14px"}),
    dcc.Store(id='selected-nodes', data={"origin": None, "destination": None}),
    dcc.Store(id='od-pairs', data=[]),

    html.Label("Which question would you like to answer? How can we ____",
               style={'fontSize': '22px', 'fontWeight': 'bold',              "paddingLeft": "20px",
              "paddingRight": "20px"}),

    # Replace dropdown with radio buttons
    dcc.RadioItems(
        id="main-selection-radio",
        options=[
            {
                "label": "Achieve a fuel/energy reduction target by optimally routing freight flows on the National Freight Network?",
                "value": "emission"},
            # {
            #     "label": "Reduce travel & dwell times by re-optimizing freight flows on the National Freight Network?",
            #     "value": "travel_time"},
            # {
            #     "label": "Set a realistic energy/fuel reduction target by optimally routing and (if applicable) allocating infrastructure?",
            #     "value": "energy"},
            # {
            #     "label": "Reduce transportation costs by optimally routing freight flows on the National Freight Network?",
            #     "value": "dist_cost"},
            {"label": "Optimally route a user-selected set of freight flows based on preferred objective?",
             "value": "optimization"},
            {"label": "Re-optimize freight flow routing in the case of disruptions?",
             "value": "disruption"}
        ],
        value=None,  # No preselected option
        labelStyle={'display': 'block', 'marginBottom': '10px','fontSize': '22px'},  # Each option appears on a new line
        style={'marginBottom': '20px',
               "paddingLeft": "20px",
               "paddingRight": "20px"
               }
    ),

    # Common Map
    html.Div([
        dcc.Loading(
            id="loading-map",
            type="circle",
            children=[
                dl.Map(center=[nodes_gdf.geometry.y.mean(), nodes_gdf.geometry.x.mean()], zoom=5, children=[
                    dl.TileLayer(url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"),  # OSM Basemap
                    *[dl.Polyline(
                        positions=[(point[1], point[0]) for point in coords],
                        color=row["color"],
                        weight=1,
                        opacity=0.7,
                        children=dl.Tooltip(f"Waterway Edge ID: {row['id']}")
                    ) for _, row in water_edges_gdf.iterrows() for coords in row["coordinates"]],
                    *[dl.Polyline(
                        positions=[(point[1], point[0]) for point in coords],
                        color=row["color"],
                        weight=1,
                        opacity=0.7,
                        children=dl.Tooltip(f"Rail-BNSF Edge ID: {row['id']}")
                    ) for _, row in rail_edges_gdf_BNSF.iterrows() for coords in row["coordinates"]],

                    # *[dl.Polyline(
                    #     positions=[(point[1], point[0]) for point in coords],
                    #     color=row["color"],
                    #     weight=1,
                    #     opacity=0.7,
                    #     children=dl.Tooltip(f"Rail-CN Edge ID: {row['id']}")
                    # ) for _, row in rail_edges_gdf_CN.iterrows() for coords in row["coordinates"]],
                    # *[dl.Polyline(
                    #     positions=[(point[1], point[0]) for point in coords],
                    #     color=row["color"],
                    #     weight=1,
                    #     opacity=0.7,
                    #     children=dl.Tooltip(f"Rail-CPKC Edge ID: {row['id']}")
                    # ) for _, row in rail_edges_gdf_CPKC.iterrows() for coords in row["coordinates"]],
                    # *[dl.Polyline(
                    #     positions=[(point[1], point[0]) for point in coords],
                    #     color=row["color"],
                    #     weight=1,
                    #     opacity=0.7,
                    #     children=dl.Tooltip(f"Rail-CSTX Edge ID: {row['id']}")
                    # ) for _, row in rail_edges_gdf_CSXT.iterrows() for coords in row["coordinates"]],
                    # *[dl.Polyline(
                    #     positions=[(point[1], point[0]) for point in coords],
                    #     color=row["color"],
                    #     weight=1,
                    #     opacity=0.7,
                    #     children=dl.Tooltip(f"Rail-NS Edge ID: {row['id']}")
                    # ) for _, row in rail_edges_gdf_NS.iterrows() for coords in row["coordinates"]],
                    *[dl.Polyline(
                        positions=[(point[1], point[0]) for point in coords],
                        color=row["color"],
                        weight=1,
                        opacity=0.7,
                        children=dl.Tooltip(f"Rail-UP Edge ID: {row['id']}")
                    ) for _, row in rail_edges_gdf_UP.iterrows() for coords in row["coordinates"]],

                    # *[dl.Polyline(
                    #     positions=[(point[1], point[0]) for point in coords],
                    #     color=row["color"],
                    #     weight=1,
                    #     opacity=0.3,
                    #     children=dl.Tooltip(f"Road Edge ID: {row['id']}")
                    # ) for _, row in road_edges_gdf.iterrows() for coords in row["coordinates"]],

                    *[dl.CircleMarker(
                        center=[row.geometry.y, row.geometry.x],
                        radius=row["size"],
                        color=row["color"],
                        fillColor=row["color"],
                        fillOpacity=0.5,
                        children=[
                            dl.Popup(
                                f"ID: {row['id']}<br>Mode: {row['modeType']}<br>Total Flows: {row['total']}<br>Foreign: {row['foreign']}<br>Exports: {row['exports']}<br>Imports: {row['imports']}<br>Domestic: {row['domestic']}<br>Terminal Type: {row['termType']}<br>Capacity: {row['capacity']}"),
                            dl.Tooltip(f"Click for details"),
                        ],
                        id=f"node-{row['id']}",
                        n_clicks=0
                    ) for _, row in nodes_gdf.iterrows()]
                ], style={"height": "800px", "width": "100%"}),

                # ----------------------------- initialize dropdowns etc. to avoid errors following
                html.Div(id='node-selection-status', style={"display": "none"}),

                html.Div([
                    html.Label("Select Demand Flow:"),
                    dcc.Dropdown(id='demand-flow', options=[
                        {'label': str(v), 'value': v} for v in []
                    ], multi=False)
                ], style={"display": "none"}),

                html.Div([
                    html.Label("Select Commodity Type:"),
                    dcc.Dropdown(id='commodity-type', options=[
                        {'label': k.capitalize(), 'value': k} for k in
                        ["Grain, Chemicals", "Building Materials, Furniture", "Auto, Pharma, Perishables"]
                    ], multi=False)
                ], style={"display": "none"}),

                html.Button("Add OD Pair", id='add-od-pair', n_clicks=0, style={"display": "none"}),

                html.Div(id='od-pair-list', style={"display": "none"}),

                html.Button("Initiate Optimization", id='initiate-optimization', n_clicks=0,
                            style={"display": "none"}),

                # --------------------------------------
                html.Div([  # legend begins here
                    html.Div("Legend", style={"font-weight": "bold", "marginBottom": "5px"}),

                    # Node Types
                    html.Div("Nodes:", style={"font-weight": "bold", "marginBottom": "3px"}),
                    html.Div([
                        html.Div(style={"backgroundColor": "red", "width": "20px", "height": "20px",
                                        "borderRadius": "50%",
                                        "display": "inline-block", "marginRight": "5px"}),
                        html.Span("Rail Node")
                    ]),
                    html.Div([
                        html.Div(style={"backgroundColor": "blue", "width": "20px", "height": "20px",
                                        "borderRadius": "50%",
                                        "display": "inline-block", "marginRight": "5px"}),
                        html.Span("Maritime Node")
                    ]),
                    html.Div([
                        html.Div(style={"backgroundColor": "grey", "width": "20px", "height": "20px",
                                        "borderRadius": "50%",
                                        "display": "inline-block", "marginRight": "5px"}),
                        html.Span("O-D Node")
                    ]),

                    html.Hr(style={"margin": "8px 0"}),  # Separator Line

                    # Link Types
                    html.Div("Links:", style={"font-weight": "bold", "marginBottom": "3px"}),
                    html.Div([
                        html.Div(style={"backgroundColor": "orange", "width": "20px", "height": "5px",
                                        "display": "inline-block", "marginRight": "5px"}),
                        html.Span("Rail-BNSF Link")
                    ]),

                    # html.Div([
                    #     html.Div(style={"backgroundColor": "green", "width": "20px", "height": "5px",
                    #                     "display": "inline-block", "marginRight": "5px"}),
                    #     html.Span("Rail-CN Link")
                    # ]),

                    html.Div([
                        html.Div(style={"backgroundColor": "purple", "width": "20px", "height": "5px",
                                        "display": "inline-block", "marginRight": "5px"}),
                        html.Span("Rail-UP Link")
                    ]),

                    html.Div([
                        html.Div(style={"backgroundColor": "#0077BE", "width": "20px", "height": "5px",
                                        "display": "inline-block", "marginRight": "5px"}),
                        html.Span("Water Link")
                    ]),
                ], style={
                    "position": "absolute",
                    "top": "10px",
                    "right": "10px",
                    "padding": "10px",
                    "backgroundColor": "white",
                    "borderRadius": "5px",
                    "boxShadow": "2px 2px 5px rgba(0,0,0,0.3)",
                    "zIndex": "1000",
                    "fontSize": "12px"
                })
            ]
        )
    ], style={"marginBottom": "20px",
              "paddingLeft": "20px",
              "paddingRight": "20px"
              }),


    # # Dynamic Content Placeholder
    # html.Div(id="dynamic-content"),

    # Placeholder Div for showing the selected content dynamically
    html.Div(id="question-content"),

    html.Footer("Developed by the NUTC team © 2025", style={"textAlign": "center", "marginTop": "50px"})
])


def register_hub_location_callbacks(app, nodes_gdf, water_edges_gdf, rail_edges_gdf_BNSF, rail_edges_gdf_UP, scenario_data):
    # @app.callback(
    #     Output("dynamic-content", "children"),
    #     Input("main-selection-dropdown", "value"),
    #     prevent_initial_call=True
    # )
    @app.callback(
        Output("question-content", "children"),
        Input("main-selection-radio", "value"),
        prevent_initial_call=True
    )

    def update_content(selection):
        fuel_options = [
            {"label": "Diesel", "value": "diesel"},
            {"label": "Battery-Electric", "value": "battery-electric"},
            {"label": "Hydrogen", "value": "hydrogen"},
            {"label": "Biodiesel", "value": "biodiesel"},
            {"label": "E-Fuel", "value": "e-fuel"}
        ]
        intermodal_facility_toggle = html.Div([
            html.Div([
            html.Label("Allow for new Intermodal/Multimodal facilities to be opened?"),
            dcc.RadioItems(
                id="intermodal-toggle",
                options=[
                    {"label": "Yes", "value": "yes"},
                    {"label": "No", "value": "no"}
                ],
                value="no",
                inline=True
            ),
            html.Div([
                html.Label("Number of new facilities allowed:"),
                dcc.Slider(
                    id="intermodal-slider",
                    min=1, max=50, step=5, value=1,
                    marks={i: str(i) for i in range(1, 51)}
                )
            ], id="intermodal-slider-container", style={"display": "none"})
        ], style={"marginBottom": "20px",
                  "paddingLeft": "20px",
                  "paddingRight": "20px"
                  }),
            html.Div(id="num-facilities-output")
        ])

        if selection == "emission":
            return html.Div([
                html.H5("Network Design Minimizing Total Cost Subject to Fuel/Energy Constraints"),

                # Objective Selection with Radio Buttons
                html.Label("Select Optimization Objective:",style={"fontSize": "18px", "fontWeight": "bold"}),
                dcc.RadioItems(
                    id="optimization-emissions-objective",
                    options=[
                        # {"label": "Energy Cost", "value": "energy"},
                        {"label": "Emissions", "value": "emissions"},
                        {"label": "Travel Time", "value": "time"},
                        {"label": "Transportation Cost", "value": "cost"},
                        {"label": "Multi-objective", "value": "custom"}  # Shows weight inputs if selected
                    ],
                    value="energy",
                    inline=False,
                    labelStyle={"display": "block", "fontSize": "17px", "marginBottom": "6px"}
                ),


                html.Label("Select Truck Fuel Technology:"),
                dcc.Dropdown(id="truck-fuel-dropdown", options=fuel_options, value="diesel",style={"fontSize": "17px"}),

                html.Label("Select Rail Fuel Technology:"),
                dcc.Dropdown(id="rail-fuel-dropdown", options=fuel_options, value="diesel",style={"fontSize": "17px"}),

                html.Label("Select Waterway Fuel Technology:"),
                dcc.Dropdown(id="waterway-fuel-dropdown", options=fuel_options, value="diesel",style={"fontSize": "17px"}),

                html.Label("Select Fuel/Energy Reduction (%)", style={"fontSize": "17px"}),
                dcc.Slider(
                    id="emission-slider",
                    min=0, max=50, step=10, value=0,
                    marks={0: "0%", 10: "10%", 20: "20%", 30: "30%", 40: "40%", 50: "50%"}
                ),

                intermodal_facility_toggle,  # Add the toggle question and slider here
                dbc.Col([
                    html.Div([
                        dbc.Button("Run Model", id="run-model-btn", className="me-2",style={"fontSize": "16px"}),
                        dcc.Loading(
                            id="loading-spinner",
                            type="circle",
                            children=html.Div(id='model-results')
                        )
                    ], className="text-center")
                ]),

                # html.Div([
                #     html.H6("Baseline defined as all minimum travel cost using existing facilities",
                #             style={"textAlign": "center", "marginBottom": "10px", "fontWeight": "bold"})
                # ]),

                html.Div([
                    html.Div(dcc.Graph(id="ton_mile_share_fig"), style={"width": "33%", "display": "inline-block"}),
                    html.Div(dcc.Graph(id="emissions_share_fig"), style={"width": "33%", "display": "inline-block"}),
                    # html.Div(dcc.Graph(id="modal_shift_fig"), style={"width": "33%", "display": "inline-block"}),
                    html.Div(dcc.Graph(id="mode_share_fig"), style={"width": "33%", "display": "inline-block"}),
                    html.Div(dcc.Graph(id="stacked_cost_fig"), style={"width": "33%", "display": "inline-block"}),
                    html.Div(dcc.Graph(id="fig_dual_y"), style={"width": "33%", "display": "inline-block"}),
                ]),
                # html.Div([
                #     html.Div(dcc.Graph(id="ton_mile_share_fig"), style={"width": "25%", "display": "inline-block"}),
                #     html.Div(dcc.Graph(id="emissions_share_fig"), style={"width": "25%", "display": "inline-block"}),
                #     html.Div(dcc.Graph(id="mode_share_fig"), style={"width": "25%", "display": "inline-block"}),
                #     html.Div(dcc.Graph(id="fig_dual_y"), style={"width": "25%", "display": "inline-block"}),
                # ]),

            ], style={"marginBottom": "20px",
                      "paddingLeft": "20px",
                      "paddingRight": "20px"
                      })

        # elif selection == "travel_time":
        #     return html.Div([
        #         html.H5("Network Design Minimizing Total Cost Subject to Travel Time Constraints"),
        #
        #         html.Label("Select Truck Fuel Technology:"),
        #         dcc.Dropdown(id="truck-fuel-dropdown", options=fuel_options, value="diesel"),
        #
        #         html.Label("Select Rail Fuel Technology:"),
        #         dcc.Dropdown(id="rail-fuel-dropdown", options=fuel_options, value="diesel"),
        #
        #         html.Label("Select Waterway Fuel Technology:"),
        #         dcc.Dropdown(id="waterway-fuel-dropdown", options=fuel_options, value="diesel"),
        #
        #         html.Label("Select Travel Time Reduction (%)"),
        #         dcc.Slider(
        #             id="time-slider",
        #             min=0, max=30, step=5, value=0,
        #             marks={0: "0%", 5: "5%", 10: "10%", 15: "15%", 20: "20%", 25: "25%", 30: "30%"}
        #         ),
        #
        #         intermodal_facility_toggle,  # Add the toggle question and slider here
        #         dbc.Col([
        #             html.Div([
        #                 dbc.Button("Run Model", id="run-model-btn-time", className="me-2"),
        #                 dcc.Loading(
        #                     id="loading-spinner",
        #                     type="circle",
        #                     children=html.Div(id='model-results-time')
        #                 )
        #             ], className="text-center")
        #         ]),
        #
        #         # html.Div([
        #         #     html.H6("Baseline defined as all minimum travel cost using existing facilities",
        #         #             style={"textAlign": "center", "marginBottom": "10px", "fontWeight": "bold"})
        #         # ]),
        #
        #         html.Div([
        #             html.Div(dcc.Graph(id="ton_mile_share_fig_travel_time"), style={"width": "33%", "display": "inline-block"}),
        #             html.Div(dcc.Graph(id="emissions_share_fig_travel_time"), style={"width": "33%", "display": "inline-block"}),
        #             # html.Div(dcc.Graph(id="modal_shift_fig"), style={"width": "33%", "display": "inline-block"}),
        #             html.Div(dcc.Graph(id="mode_share_fig_travel_time"), style={"width": "33%", "display": "inline-block"}),
        #             # html.Div(dcc.Graph(id="stacked_cost_fig_travel_time"), style={"width": "33%", "display": "inline-block"}),
        #             html.Div(dcc.Graph(id="fig_dual_y_travel_time"), style={"width": "33%", "display": "inline-block"}),
        #         ]),
        #
        #     ], style={"marginBottom": "20px",
        #               "paddingLeft": "20px",
        #               "paddingRight": "20px"
        #               })

        # elif selection == "energy":
        #     return html.Div([
        #         html.H5("Network Design Minimizing Total Cost Subject to Energy Constraints"),
        #
        #         html.Label("Select Truck Fuel Technology:"),
        #         dcc.Dropdown(id="truck-fuel-dropdown", options=fuel_options, value="diesel"),
        #
        #         html.Label("Select Rail Fuel Technology:"),
        #         dcc.Dropdown(id="rail-fuel-dropdown", options=fuel_options, value="diesel"),
        #
        #         html.Label("Select Waterway Fuel Technology:"),
        #         dcc.Dropdown(id="waterway-fuel-dropdown", options=fuel_options, value="diesel"),
        #
        #         html.Label("Select Energy Reduction (%)"),
        #         dcc.Slider(
        #             id="energy-slider",
        #             min=0, max=30, step=5, value=0,
        #             marks={0: "0%", 5: "5%", 10: "10%", 15: "15%", 20: "20%", 25: "25%", 30: "30%"}
        #         ),
        #
        #         intermodal_facility_toggle,  # Add the toggle question and slider here
        #         dbc.Col([
        #             html.Div([
        #                 dbc.Button("Run Model", id="run-model-btn-energy", className="me-2"),
        #                 dcc.Loading(
        #                     id="loading-spinner",
        #                     type="circle",
        #                     children=html.Div(id='model-results-energy')
        #                 )
        #             ], className="text-center")
        #         ]),
        #
        #         # html.Div([
        #         #     html.H6("Baseline defined as all minimum travel cost using existing facilities",
        #         #             style={"textAlign": "center", "marginBottom": "10px", "fontWeight": "bold"})
        #         # ]),
        #
        #         html.Div([
        #             html.Div(dcc.Graph(id="ton_mile_share_fig_energy"), style={"width": "33%", "display": "inline-block"}),
        #             html.Div(dcc.Graph(id="emissions_share_fig_energy"), style={"width": "33%", "display": "inline-block"}),
        #             # html.Div(dcc.Graph(id="modal_shift_fig"), style={"width": "33%", "display": "inline-block"}),
        #             html.Div(dcc.Graph(id="mode_share_fig_energy"), style={"width": "33%", "display": "inline-block"}),
        #             html.Div(dcc.Graph(id="stacked_cost_fig_energy"), style={"width": "33%", "display": "inline-block"}),
        #             html.Div(dcc.Graph(id="fig_dual_y_energy"), style={"width": "33%", "display": "inline-block"}),
        #         ]),
        #
        #     ], style={"marginBottom": "20px",
        #               "paddingLeft": "20px",
        #               "paddingRight": "20px"
        #               })
        #
        # elif selection == "dist_cost":
        #     return html.Div([
        #         html.H5("Network Design Minimizing Total Cost Subject to Transportation Cost Constraints"),
        #
        #         html.Label("Select Truck Fuel Technology:"),
        #         dcc.Dropdown(id="truck-fuel-dropdown", options=fuel_options, value="diesel"),
        #
        #         html.Label("Select Rail Fuel Technology:"),
        #         dcc.Dropdown(id="rail-fuel-dropdown", options=fuel_options, value="diesel"),
        #
        #         html.Label("Select Waterway Fuel Technology:"),
        #         dcc.Dropdown(id="waterway-fuel-dropdown", options=fuel_options, value="diesel"),
        #
        #         html.Label("Select Transportation Cost Reduction (%)"),
        #         dcc.Slider(
        #             id="dist-slider",
        #             min=0, max=50, step=10, value=0,
        #             marks={0: "0%", 10: "10%", 20: "20%", 30: "30%", 40: "40%", 50: "50%"}
        #         ),
        #
        #         intermodal_facility_toggle,  # Add the toggle question and slider here
        #         dbc.Col([
        #             html.Div([
        #                 dbc.Button("Run Model", id="run-model-btn-dist", className="me-2"),
        #                 dcc.Loading(
        #                     id="loading-spinner",
        #                     type="circle",
        #                     children=html.Div(id='model-results-dist')
        #                 )
        #             ], className="text-center")
        #         ]),
        #
        #         # html.Div([
        #         #     html.H6("Baseline defined as all minimum travel cost using existing facilities",
        #         #             style={"textAlign": "center", "marginBottom": "10px", "fontWeight": "bold"})
        #         # ]),
        #
        #         html.Div([
        #             html.Div(dcc.Graph(id="ton_mile_share_fig_dist"), style={"width": "33%", "display": "inline-block"}),
        #             html.Div(dcc.Graph(id="emissions_share_fig_dist"), style={"width": "33%", "display": "inline-block"}),
        #             # html.Div(dcc.Graph(id="modal_shift_fig"), style={"width": "33%", "display": "inline-block"}),
        #             html.Div(dcc.Graph(id="mode_share_fig_dist"), style={"width": "33%", "display": "inline-block"}),
        #             html.Div(dcc.Graph(id="stacked_cost_fig_dist"), style={"width": "33%", "display": "inline-block"}),
        #             html.Div(dcc.Graph(id="fig_dual_y_dist"), style={"width": "33%", "display": "inline-block"}),
        #         ]),
        #
        #
        #     ], style={"marginBottom": "20px",
        #               "paddingLeft": "20px",
        #               "paddingRight": "20px"
        #               })

        elif selection == "optimization":
            return html.Div([
                html.H5("Flow Assignment and Facility Location Optimization"),

                html.Div([
                    html.H5("User Guide", style={"fontSize": "17px","marginBottom": "10px", "color": "#333"}),
                    html.P("Choose your OD pair:", style={"fontSize": "17px","fontWeight": "bold"}),
                    html.Ul([
                        html.Li(
                            "Choose the objective that you want to optimize for, or choose Multi-Objective and adjust objective weights."),
                        html.Li("Choose Origin by clicking on the preferred node in the map."),
                        html.Li("Choose Destination by clicking on the preferred node in the map."),
                        html.Li("Choose demand flows, either custom or predefined for given OD pair."),
                        html.Li("Choose commodity."),
                        html.Li("Add OD pair in the scenario (click Add OD pair)."),
                        html.Li("Choose to allow or not the creation of new intermodal/multimodal facilities."),
                        html.Li("Choose additional OD pairs, or Run model.")
                    ])
                ], style={
                    "width": "35%",
                    "backgroundColor": "#f9f9f9",
                    "border": "1px solid #ddd",
                    "borderRadius": "8px",
                    "padding": "15px",
                    "fontSize": "17px",
                    "height": "fit-content"
                }),

                # Objective Selection with Radio Buttons
                html.Label("Select Optimization Objective:"),
                dcc.RadioItems(
                    id="optimization-objective",
                    options=[
                        {"label": "Energy Cost", "value": "energy"},
                        {"label": "Emissions", "value": "emissions"},
                        {"label": "Travel Time", "value": "time"},
                        {"label": "Transportation Cost", "value": "cost"},
                        {"label": "Custom", "value": "custom"}  # Shows weight inputs if selected
                    ],
                    value="energy",
                    inline=False
                ),

                # Custom Weights Section (Initially Hidden)
                html.Div([
                    html.Label("Set Weights for Optimization Objectives (Sum must be 1):"),
                    html.Div([
                        html.Label("Energy Cost Weight:"),
                        dcc.Input(id="weight-energy", type="number", min=0, max=1, step=0.01, value=0.25),
                        html.Label("Emissions Weight:"),
                        dcc.Input(id="weight-emissions", type="number", min=0, max=1, step=0.01, value=0.25),
                        html.Label("Travel Time Weight:"),
                        dcc.Input(id="weight-time", type="number", min=0, max=1, step=0.01, value=0.25),
                        html.Label("Cost Weight:"),
                        dcc.Input(id="weight-cost", type="number", min=0, max=1, step=0.01, value=0.25),
                    ], style={"display": "flex", "gap": "10px"}),
                    html.Div(id="weight-validation-message", style={"color": "red", "marginTop": "5px"}),
                ], id="custom-weight-container", style={"display": "none", "marginTop": "10px"}),

                dcc.Store(id="optimization-preferences-store"),

                html.Hr(),
                html.H6("Selected Node Details:"),
                html.Div(id="node-info",
                         style={"fontSize": "14px", "marginTop": "10px", "padding": "10px",
                                "border": "1px solid #ddd"}),
                html.Div(id='node-selection-status', style={"marginTop": "10px", "fontWeight": "bold"}),
                html.Div([
                    html.Label("Enter Demand Flow (thousand tons) or Select Predefined Option:"),
                    dcc.RadioItems(id='demand-flow-option',
                                   options=[
                                       {'label': "Enter Manually", 'value': "manual"},
                                       {'label': "Use Predefined 2024 Freight Flows for Given O-D Pair", 'value': "predefined"}
                                   ],
                                   value="manual",
                                   inline=True),
                    dcc.Input(id='demand-flow-input', type='number', placeholder='Enter demand (tons)',
                              style={'marginTop': '10px'}),
                ], style={"marginTop": "10px"}),
                html.Div([
                    html.Label("Select Commodity Type:"),
                    dcc.Dropdown(
                        id='commodity-type',
                        options=[
                            {'label': "Grain, Chemicals", 'value': 'low'},
                            {'label': "Building Materials, Furniture", 'value': 'moderate'},
                            {'label': "Auto, Pharma, Perishables", 'value': 'high'}
                        ],
                        multi=False
                    )
                ], style={"marginTop": "10px"}),

                intermodal_facility_toggle,

                html.Button("Add OD Pair", id='add-od-pair', n_clicks=0, style={"marginTop": "10px","backgroundColor": "purple", "color": "white"}),
                html.Div(id='od-pair-list', style={"marginTop": "10px", "whiteSpace": "pre-wrap"}),

                html.Button("Reset OD Selection", id="reset-od-selection", n_clicks=0, style={"marginTop": "10px","backgroundColor": "purple", "color": "white"}),

                dbc.Col([
                    html.Div([
                        dbc.Button("Run Model", id="initiate-optimization",  n_clicks=0,
                                   style={"marginTop": "10px","backgroundColor": "purple", "color": "white"}),
                        dcc.Loading(
                            id="loading-spinner",
                            type="circle",
                            children=html.Div(id='model-run-status')
                        )
                    ], className="text-center")
                ]),

            html.Div([
                html.Div(dcc.Graph(id='stacked_cost_fig_opt'), style={"width": "50%", "display": "inline-block"}),
                html.Div(dcc.Graph(id="fig_dual_y_opt"), style={"width": "50%", "display": "inline-block"}),
            ], style={"marginTop": "10px"}),


            ], style={"marginBottom": "20px",
                      "paddingLeft": "20px",
                      "paddingRight": "20px"
                      }),

        elif selection == "disruption":
            return html.Div([
                html.H5("Respond to Disruptions: Adaptive and Resilient Freight Networks"),
                html.Label("Select Disrupted Corridor/Port:"),
                dcc.Dropdown(
                    id="disruption-dropdown",
                    options=[
                        {"label": "Mississippi River Waterway Corridor", "value": "mississippi"},
                        # {"label": "Boston to Orlando Intermodal Corridor (Interstate I-95)", "value": "chicago"},
                        # {"label": "Port of L.A. and Port of Long Beach", "value": "la"}
                    ],
                    value="mississippi"
                ),
                html.Button("Apply Disruption", id="disrupt-button",
                            style={"backgroundColor": "purple", "color": "white"}),
            ], style={"marginBottom": "20px",
                      "paddingLeft": "20px",
                      "paddingRight": "20px"
                      }),

        return dash.no_update

    #------------------------------------------------------------------------------------------------------------------------------ for choice being emissions - start
    def get_facility_outputs(toggle_value, slider_value):
        global num_facilities
        if toggle_value == "yes":
            num_facilities = slider_value
            return {"display": "block"}, f"Number of Facilities: {num_facilities}", num_facilities
        else:
            num_facilities = 0
            return {"display": "none"}, "", num_facilities

    @app.callback(
        Output("intermodal-slider-container", "style"),
        Output("num-facilities-output", "children"),
        Output("intermodal-slider", "value"),
        Input("intermodal-toggle", "value"),
        Input("intermodal-slider", "value"),
    )
    def update_slider_and_display(toggle_value, slider_value):
        style, label, slider_val = get_facility_outputs(toggle_value, slider_value)
        return style, label, slider_val

    @app.callback(
        [Output("model-results", "children"),
         Output("ton_mile_share_fig", "figure"),
         Output("emissions_share_fig", "figure"),
         # Output("modal_shift_fig", "figure"),
         Output("mode_share_fig", "figure"),
         Output("stacked_cost_fig", "figure"),
         Output("fig_dual_y", "figure"),],
        [Input("run-model-btn", "n_clicks"),
         ],
        [State("optimization-emissions-objective", "value"),
        State("emission-slider", "value"),
         State("truck-fuel-dropdown", "value"),
         State("rail-fuel-dropdown", "value"),
         State("waterway-fuel-dropdown", "value")],
        prevent_initial_call=True
    )
    def execute_model(n_clicks, opt_em, emission_reduction, truck_fuel, rail_fuel, waterway_fuel):
        ctx = callback_context
        if not ctx.triggered:
            return dash.no_update, False

        run_model, load_scenario_energy_cost_parameters, congestion_cost_calculations, run_model_congestion_iterations, transform_results_to_viz, generate_viz_results = mparouti()

        file_name = "hub_loc_files\od_pairs_dash_emissions.json"
        with open(file_name, "r") as f:
            od_pairs = json.load(f)

        file_path = "hub_loc_files\exploded_national_FINAL_dashboard_1_3_2025.pkl"
        with open(file_path, 'rb') as file:
            loaded_graph_exploded = pickle.load(file)

        file_name = "hub_loc_files\link_flows_base_emissions.json"
        with open(file_name, "r") as f:
            link_flows_loaded = json.load(f)
        link_flows_loaded = {eval(k): v for k, v in link_flows_loaded.items()}

        scenarios = [
            {
                'name': 'Baseline Scenario',
                'od_pairs': od_pairs,
                'congestion_level': 'no',
                'max_open_intermediate_hubs': num_facilities,
                'restricted_edges': None,
                'fixed_hubs': None,
                'road_energy_type': truck_fuel,
                'rail_energy_type': rail_fuel,
                'waterway_energy_type': waterway_fuel,
                'arc_cap': False,
                'node_cap': False,
                'congestion': False,
                'dwell_t': True,
                'emissions_reduction': emission_reduction/100,
                'base_link_flows': link_flows_loaded,
            },
        ]

        global results
        results = {}
        for scenario in scenarios:
            G, (m, x, z), runtime, hub_ids, df_system_totals, df_results = run_model(
                scenario=scenario,
                G=loaded_graph_exploded,
                od_pairs=scenario['od_pairs'],
                hub_budget=scenario.get('max_open_intermediate_hubs'),
                mode_tech={'road': scenario.get('road_energy_type'), 'rail': scenario.get('rail_energy_type'),
                           'waterway': scenario.get('waterway_energy_type')},
                congestion_travel_time_increase=None,
                fixed_hubs=scenario.get('fixed_hubs'),
                restricted_nodes=scenario.get('restricted_node'),
                restricted_edges=scenario.get('restricted_edges'),
                capped_arcs=scenario.get('arc_cap'),
                capped_nodes=scenario.get('node_cap'),
                emissions_lever=True,
                reduction_factor_emissions=emission_reduction/100,
                base_tt=719.0472477924085,
                base_dt=372,
                base_dist=15664.958477593225,
                base_emissions=419012407794.12,
                base_emissions_g=49632.55999999998,
                base_tt_cost=14726327196.219152,
                base_dt_cost=16087422555.999998,
                base_dist_cost=174638210099.76627,
                base_energy_cost=2281204878.0702214,
                base_emissions_cost=1120596676.8463018,
                base_link_flows=scenario.get('base_link_flows'),
                base_mode_ton_miles={'waterway': {'low': 4956904169207.093,
                    'moderate': 0.0,
                    'high': 0.0},
                   'road': {'low': 1273797055677.7185,
                    'moderate': 885746067073.6261,
                    'high': 220172979977.71442},
                   'rail': {'low': 5056351985974.221,
                    'moderate': 931205216065.5125,
                    'high': 0.0}},
                base_mode_emissions={'waterway': {'low': 53980686402666.7,
                    'moderate': 0.0,
                    'high': 0.0},
                   'road': {'low': 83115257882969.19,
                    'moderate': 57794930876554.984,
                    'high': 14366286943545.424},
                   'rail': {'low': 130201063638835.17,
                    'moderate': 23978534313686.9,
                    'high': 0.0}},
                base_mode_ton_mile_shares={'waterway': {'low': 0.4391672544290296,
                    'moderate': 0.0,
                    'high': 0.0},
                   'road': {'low': 0.11285470457889621,
                    'moderate': 0.48749026751188757,
                    'high': 1.0},
                   'rail': {'low': 0.4479780409921208,
                    'moderate': 0.5125097324880447,
                    'high': 0.0}},
                base_mode_emissions_shares={'waterway': {'low': 0.2019502082040518,
                    'moderate': 0.0,
                    'high': 0.0},
                   'road': {'low': 0.3109472063617531,
                    'moderate': 0.7067687634625093,
                    'high': 1.0},
                   'rail': {'low': 0.4871025854342008,
                    'moderate': 0.29323123653743566,
                    'high': 0.0}},
                base_total_ton_miles={'low': 11287053210858.506,
                       'moderate': 1816951283139.2617,
                       'high': 220172979977.71442},
                base_total_emissions={'low': 267297007924469.53,
                   'moderate': 81773465190246.39,
                   'high': 14366286943545.424}
            )

        #----------------------------- keep
        model_output_text = html.Div([
            html.P(f"Emission Reduction Target: {emission_reduction}%"),
            html.P(f"Selected Truck Fuel: {truck_fuel}"),
            html.P(f"Selected Rail Fuel: {rail_fuel}"),
            html.P(f"Selected Waterway Fuel: {waterway_fuel}"),
        ],style={"display": "none"})
        #-------------------------------

        mode_ton_mile_shares = results[scenario['name']]['mode_ton_mile_shares']
        mode_emissions_shares = results[scenario['name']]['mode_emissions_shares']
        base_mode_ton_mile_shares = results[scenario['name']]['base_mode_ton_mile_shares']
        base_mode_emissions_shares = results[scenario['name']]['base_mode_emissions_shares']

        commodity_classes = ['low', 'moderate', 'high']

        # Define the desired mode order
        mode_order = ["waterway", "rail", "road"]

        colors_ = {'road': 'red', 'rail': 'orange', 'waterway': 'blue'}
        ton_mile_share_fig = go.Figure()

        for mode in mode_order:
            # Baseline Trace
            ton_mile_share_fig.add_trace(go.Bar(
                x=commodity_classes,
                y=[base_mode_ton_mile_shares[mode][cls] for cls in commodity_classes],
                name=f"{mode.capitalize()} (Baseline)",
                marker=dict(color=colors_[mode], pattern=dict(shape="\\")),
                offsetgroup=f"{mode}_baseline",
                legendgroup=f"{mode}_baseline"
            ))

            # Scenario Trace
            ton_mile_share_fig.add_trace(go.Bar(
                x=commodity_classes,
                y=[mode_ton_mile_shares[mode][cls] for cls in commodity_classes],
                name=f"{mode.capitalize()} (Scenario)",
                marker_color=colors_[mode],
                offsetgroup=f"{mode}_scenario",
                legendgroup=f"{mode}_scenario"
            ))

        # Update layout
        ton_mile_share_fig.update_layout(
            barmode="group",
            title="Mode Ton-Mile Share by Commodity Class",
            xaxis_title="Commodity Class",
            yaxis_title="Ton-Mile Share",
            legend_title="Mode & Scenario",
            height=500,
            xaxis_tickangle=-45,
            title_font=dict(size=20),
            xaxis=dict(title_font=dict(size=16), tickfont=dict(size=14)),
            yaxis=dict(title_font=dict(size=16), tickfont=dict(size=14)),
            legend=dict(font=dict(size=14))
        )

        # Emissions Share Figure
        emissions_share_fig = go.Figure()

        for mode in mode_order:
            # Baseline Trace
            emissions_share_fig.add_trace(go.Bar(
                x=commodity_classes,
                y=[base_mode_emissions_shares[mode][cls] for cls in commodity_classes],
                name=f"{mode.capitalize()} (Baseline)",
                marker=dict(color=colors_[mode], pattern=dict(shape="\\")),
                offsetgroup=f"{mode}_baseline",
                legendgroup=f"{mode}_baseline"
            ))

            # Scenario Trace
            emissions_share_fig.add_trace(go.Bar(
                x=commodity_classes,
                y=[mode_emissions_shares[mode][cls] for cls in commodity_classes],
                name=f"{mode.capitalize()} (Scenario)",
                marker_color=colors_[mode],
                offsetgroup=f"{mode}_scenario",
                legendgroup=f"{mode}_scenario"
            ))

        # Update layout
        emissions_share_fig.update_layout(
            barmode="group",
            title="Mode Emissions Share by Commodity Class",
            xaxis_title="Commodity Class",
            yaxis_title="Emissions Share",
            legend_title="Mode & Scenario",
            height=500,
            xaxis_tickangle=-45,
            title_font=dict(size=20),
            xaxis=dict(title_font=dict(size=16), tickfont=dict(size=14)),
            yaxis=dict(title_font=dict(size=16), tickfont=dict(size=14)),
            legend=dict(font=dict(size=14))
        )

        # # Add current scenario shares
        # for mode in mode_ton_mile_shares.keys():
        #     ton_mile_share_fig.add_trace(
        #         go.Bar(
        #             x=commodity_classes,
        #             y=[mode_ton_mile_shares[mode][cls] for cls in commodity_classes],
        #             name=f"{mode.capitalize()} (Scenario)",
        #             marker_color=colors[mode]
        #         )
        #     )
        #
        # # Baseline bars (patterned fill)
        # for mode in base_mode_ton_mile_shares.keys():
        #     ton_mile_share_fig.add_trace(
        #         go.Bar(
        #             x=commodity_classes,
        #             y=[base_mode_ton_mile_shares[mode][cls] for cls in commodity_classes],
        #             name=f"{mode.capitalize()} (Baseline)",
        #             marker=dict(
        #                 color=colors[mode],
        #                 pattern=dict(shape="\\")  # Options: '/', '\\', 'x', '-', '|', '+', '.'
        #             )
        #         )
        #     )
        #
        # ton_mile_share_fig.update_layout(
        #     barmode='group',
        #     title="Mode Ton-Mile Share by Commodity Class",
        #     xaxis_title="Commodity Class",
        #     yaxis_title="Ton-Mile Share",
        #     legend_title="Mode",
        #     height=400
        # )
        #
        # # Prepare the bar chart for Mode Emissions Shares
        # emissions_share_fig = go.Figure()
        #
        # # Add current scenario shares
        # for mode in mode_emissions_shares.keys():
        #     emissions_share_fig.add_trace(
        #         go.Bar(
        #             x=commodity_classes,
        #             y=[mode_emissions_shares[mode][cls] for cls in commodity_classes],
        #             name=f"{mode.capitalize()} (Scenario)",
        #             marker_color=colors[mode]
        #         )
        #     )
        #
        # # Baseline bars (patterned fill)
        # for mode in base_mode_emissions_shares.keys():
        #     emissions_share_fig.add_trace(
        #         go.Bar(
        #             x=commodity_classes,
        #             y=[base_mode_emissions_shares[mode][cls] for cls in commodity_classes],
        #             name=f"{mode.capitalize()} (Baseline)",
        #             marker=dict(
        #                 color=colors[mode],
        #                 pattern=dict(shape="\\")  # You can vary this by mode too if desired
        #             )
        #         )
        #     )
        #
        # emissions_share_fig.update_layout(
        #     barmode='group',
        #     title="Mode Emissions Share by Commodity Class",
        #     xaxis_title="Commodity Class",
        #     yaxis_title="Emissions Share",
        #     legend_title="Mode",
        #     height=400
        # )

        # total_tm_scenario2 = sum(df_system_totals["Scenario 2"])
        #
        # aggregate_shift = df_results.groupby(['Mode_From', 'Mode_To'])['Delta_TM_Mode_To'].sum().reset_index()
        # aggregate_shift['Modal_Shift_Category'] = aggregate_shift['Mode_From'].str.capitalize() + " → " + \
        #                                           aggregate_shift['Mode_To'].str.capitalize()
        # aggregate_shift['Percent_of_System'] = 100 * aggregate_shift['Delta_TM_Mode_To'] / total_tm_scenario2
        # aggregate_shift = aggregate_shift.sort_values(by='Percent_of_System', ascending=False)
        #
        # # Create Plotly bar chart
        # modal_shift_fig = go.Figure(
        #     data=[
        #         go.Bar(
        #             x=aggregate_shift['Modal_Shift_Category'],
        #             y=aggregate_shift['Percent_of_System'],
        #             marker_color='teal',
        #             text=[f"{x:.2f}%" for x in aggregate_shift['Percent_of_System']],
        #             textposition='outside'
        #         )
        #     ],
        #     layout=go.Layout(
        #         title="System-wide Modal Shifts (% of Total Ton-Miles in Scenario 2)",
        #         xaxis_title="Modal Shift Category",
        #         yaxis_title="Percent of System Ton-Miles Shifted",
        #         yaxis=dict(gridcolor='lightgray'),
        #         height=400
        #     )
        # )

        df_percent_system_totals = df_system_totals.copy()
        df_percent_system_totals["Scenario 1"] = 100 * df_system_totals["Scenario 1"] / df_system_totals[
            "Scenario 1"].sum()
        df_percent_system_totals["Scenario 2"] = 100 * df_system_totals["Scenario 2"] / df_system_totals[
            "Scenario 2"].sum()

        modes = df_percent_system_totals["Mode"].tolist()
        scenario1_percent = df_percent_system_totals["Scenario 1"].tolist()
        scenario2_percent = df_percent_system_totals["Scenario 2"].tolist()

        # Define color mapping
        mode_colors = {
            "road": "red",
            "rail": "orange",
            "waterway": "blue"
        }

        mode_share_fig = go.Figure()

        for i, mode in enumerate(modes):
            mode_lower = mode.lower()  # Ensure lowercase match for the mapping
            color = mode_colors.get(mode_lower, "gray")  # Default to gray if not found

            mode_share_fig.add_trace(go.Bar(
                x=["Baseline", "Current Scenario"],
                y=[scenario1_percent[i], scenario2_percent[i]],
                name=mode.capitalize(),
                marker_color=color
            ))

        mode_share_fig.update_layout(
            barmode='stack',
            title="Mode Share of Total Ton-Miles",
            xaxis_title="Scenario",
            yaxis_title="Percentage Share (%)",
            yaxis=dict(gridcolor='lightgray'),
            legend_title="Mode",
            height=450,
            title_font=dict(size=20),
            xaxis=dict(title_font=dict(size=16), tickfont=dict(size=14)),
            # yaxis=dict(title_font=dict(size=16), tickfont=dict(size=14)),
            legend=dict(font=dict(size=14))

        )

        metric_names = [
            "Travel Time Cost", "Dwell Time Cost", "Distance Cost",
            "Energy Cost", "Emissions Cost"
        ]

        # Extract raw values
        base_values = [
            results[scenario['name']]['base_tt_cost'],
            results[scenario['name']]['base_dt_cost'],
            results[scenario['name']]['base_dist_cost'],
            results[scenario['name']]['base_energy_cost'],
            results[scenario['name']]['base_emissions_cost']
        ]
        current_values = [
            results[scenario['name']]['travel_time_cost'],
            results[scenario['name']]['dwell_time_cost'],
            results[scenario['name']]['transportation_cost'],
            results[scenario['name']]['energy_cost'],
            results[scenario['name']]['emissions_cost']
        ]

        # Compute total costs
        base_total = sum(base_values)
        current_total = sum(current_values)

        # Compute percentage share of each component
        base_percentages = [(val / base_total) * 100 for val in base_values]
        current_percentages = [(val / current_total) * 100 for val in current_values]

        # Create stacked bar chart
        stacked_cost_fig = go.Figure()

        # Add each cost component as a separate trace
        colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd']

        for i, name in enumerate(metric_names):
            stacked_cost_fig.add_trace(go.Bar(
                name=name,
                x=['Baseline', 'Current'],
                y=[base_percentages[i], current_percentages[i]],
                marker_color=colors[i],
                text=[f"{base_percentages[i]:.1f}%", f"{current_percentages[i]:.1f}%"],
                textposition='auto'
            ))

        # Update layout
        stacked_cost_fig.update_layout(
            title="Cost Component Shares of Total Cost",
            barmode='stack',
            yaxis=dict(title='Share of Total Cost (%)', range=[0, 100]),
            xaxis=dict(title='Scenario'),
            legend_title="Cost Components",
            template='plotly_white',
            height=500,
            title_font=dict(size=20),
            # xaxis=dict(title_font=dict(size=16), tickfont=dict(size=14)),
            # yaxis=dict(title_font=dict(size=16), tickfont=dict(size=14)),
            legend=dict(font=dict(size=14))
        )

        metric_names_filtered = ['Travel Time', 'Emissions']

        # Extract just travel time and emissions
        base_tt = results[scenario['name']]['base_tt']
        base_emissions = results[scenario['name']]['base_emissions_g']
        current_tt = results[scenario['name']]['travel_time']
        current_emissions = results[scenario['name']]['emissions_g']

        # Compute percentage change
        percent_change_tt = abs(((current_tt - base_tt) / base_tt) * 100)
        percent_change_emissions = (((current_emissions - base_emissions) / base_emissions) * 100)

        # Create the figure
        fig_dual_y = go.Figure()

        # Travel Time % Change Bar (Y-axis 1 - left)
        fig_dual_y.add_trace(go.Bar(
            name='Travel Time % Change',
            x=[metric_names_filtered[0]],
            y=[percent_change_tt],
            marker_color='orange',
            yaxis='y'
        ))

        # Emissions % Change Bar (Y-axis 2 - right)
        fig_dual_y.add_trace(go.Bar(
            name='Emissions % Change',
            x=[metric_names_filtered[1]],
            y=[percent_change_emissions],
            marker_color='green',
            yaxis='y2'
        ))

        # Layout with dual Y-axes (both now showing percentage change)
        fig_dual_y.update_layout(
            title="Percentage Change in Travel Time and Emissions",
            title_font=dict(size=20),
            xaxis=dict(tickfont=dict(size=14)),
            yaxis=dict(
                title="Travel Time (% Change)",
                title_font=dict(size=16),
                tickfont=dict(size=14, color="orange")
            ),
            yaxis2=dict(
                title="Emissions (% Change)",
                title_font=dict(size=16),
                tickfont=dict(size=14, color="green"),
                overlaying='y',
                side='right',
                zeroline=True,
                zerolinecolor='gray',
            ),
            barmode='group',
            template='plotly_white',
            legend=dict(orientation='h', yanchor='bottom', y=-0.3, xanchor='center', x=0.5),
            height=500,
        )

        # return model_output_text, ton_mile_share_fig, emissions_share_fig, modal_shift_fig, mode_share_fig, stacked_cost_fig, fig_dual_y
        return model_output_text, ton_mile_share_fig, emissions_share_fig, mode_share_fig, stacked_cost_fig, fig_dual_y

        # return model_output_text, ton_mile_share_fig, emissions_share_fig, mode_share_fig, fig_dual_y

    # code part for showing hubs if the model opens hubs (to show on the map)
    # #need to either get into the above function and callback, or maybe return the hub_ids from the above
    # @app.callback(
    #     Output("loading-map", "children"),
    #     Input("hub_ids_store", "data"),
    #     State("loading-map", "children"),
    #     prevent_initial_call=True
    # )
    # def update_hub_nodes(hub_ids, existing_map_children):
    #     if not hub_ids:
    #         return existing_map_children
    #
    #     # Extract original dl.Map object
    #     dl_map = None
    #     for child in existing_map_children:
    #         if isinstance(child, dl.Map):
    #             dl_map = child
    #             break
    #
    #     if dl_map is None:
    #         return existing_map_children  # fallback
    #
    #     # Get current children of the map
    #     map_layers = list(dl_map.children)
    #
    #     # Create new hub markers
    #     hub_nodes = nodes_gdf[nodes_gdf["id"].astype(str).isin(hub_ids)]
    #     hub_markers = [
    #         dl.CircleMarker(
    #             center=[row.geometry.y, row.geometry.x],
    #             radius=8,
    #             color="red",
    #             fillColor="red",
    #             fillOpacity=0.8,
    #             children=[
    #                 dl.Popup(f"Hub ID: {row['id']}<br>Type: {row['modeType']}"),
    #                 dl.Tooltip(f"Hub {row['id']}"),
    #             ],
    #             id=f"hub-node-{row['id']}",
    #         ) for _, row in hub_nodes.iterrows()
    #     ]
    #
    #     # Append hub markers to existing map layers
    #     updated_layers = map_layers + hub_markers
    #
    #     # Recreate the dl.Map object with updated children
    #     updated_map = dl.Map(
    #         center=dl_map.center,
    #         zoom=dl_map.zoom,
    #         children=updated_layers,
    #         style=dl_map.style,
    #         id=dl_map.id
    #     )
    #
    #     # Return updated map inside loading container
    #     return [updated_map]

    # ------------------------------------------------------------------------------------------------------------------------------ for choice being emissions - end

    # ------------------------------------------------------------------------------------------------------------------------------ for choice being travel time - start
    def get_facility_outputs(toggle_value, slider_value):
        global num_facilities
        if toggle_value == "yes":
            num_facilities = slider_value
            return {"display": "block"}, f"Number of Facilities: {num_facilities}", num_facilities
        else:
            num_facilities = 0
            return {"display": "none"}, "", num_facilities

    @app.callback(
        Output("intermodal-slider-container-time", "style"),
        Output("num-facilities-output-time", "children"),
        Output("intermodal-slider-time", "value"),
        Input("intermodal-toggle-time", "value"),
        Input("intermodal-slider-time", "value"),
    )
    def update_slider_and_display(toggle_value, slider_value):
        style, label, slider_val = get_facility_outputs(toggle_value, slider_value)
        return style, label, slider_val

    @app.callback(
        [Output("model-results-time", "children"),
         Output("ton_mile_share_fig_travel_time", "figure"),
         Output("emissions_share_fig_travel_time", "figure"),
         # Output("modal_shift_fig", "figure"),
         Output("mode_share_fig_travel_time", "figure"),
         Output("stacked_cost_fig_travel_time", "figure"),
         Output("fig_dual_y_travel_time", "figure"), ],
        [Input("run-model-btn-time", "n_clicks")],
        [State("time-slider", "value"),
         State("truck-fuel-dropdown", "value"),
         State("rail-fuel-dropdown", "value"),
         State("waterway-fuel-dropdown", "value")],
        prevent_initial_call=True
    )
    def execute_model(n_clicks, travel_time_reduction, truck_fuel, rail_fuel, waterway_fuel):
        ctx = callback_context
        if not ctx.triggered:
            return dash.no_update, False

        run_model, load_scenario_energy_cost_parameters, congestion_cost_calculations, run_model_congestion_iterations, transform_results_to_viz, generate_viz_results = mparouti()

        file_name = "hub_loc_files\od_pairs_dash_emissions.json"
        with open(file_name, "r") as f:
            od_pairs = json.load(f)

        file_path = "hub_loc_files\exploded_national_FINAL_dashboard_1_3_2025.pkl"
        with open(file_path, 'rb') as file:
            loaded_graph_exploded = pickle.load(file)

        file_name = "hub_loc_files\link_flows_base_emissions.json"
        with open(file_name, "r") as f:
            link_flows_loaded = json.load(f)
        link_flows_loaded = {eval(k): v for k, v in link_flows_loaded.items()}

        scenarios = [
            {
                'name': 'Baseline Scenario',
                'od_pairs': od_pairs,
                'congestion_level': 'no',
                'max_open_intermediate_hubs': num_facilities,
                'restricted_edges': None,
                'fixed_hubs': None,
                'road_energy_type': truck_fuel,
                'rail_energy_type': rail_fuel,
                'waterway_energy_type': waterway_fuel,
                'arc_cap': False,
                'node_cap': False,
                'congestion': False,
                'dwell_t': True,
                'travel_time_reduction': travel_time_reduction / 100,
                'base_link_flows': link_flows_loaded,
            },
        ]

        global results
        results = {}
        for scenario in scenarios:
            G, (m, x, z), runtime, hub_ids, df_system_totals, df_results = run_model(
                scenario=scenario,
                G=loaded_graph_exploded,
                od_pairs=scenario['od_pairs'],
                hub_budget=scenario.get('max_open_intermediate_hubs'),
                mode_tech={'road': scenario.get('road_energy_type'), 'rail': scenario.get('rail_energy_type'),
                           'waterway': scenario.get('waterway_energy_type')},
                congestion_travel_time_increase=None,
                fixed_hubs=scenario.get('fixed_hubs'),
                restricted_nodes=scenario.get('restricted_node'),
                restricted_edges=scenario.get('restricted_edges'),
                capped_arcs=scenario.get('arc_cap'),
                capped_nodes=scenario.get('node_cap'),
                travel_time_lever=True,
                reduction_factor_travel_time=travel_time_reduction / 100,
                base_tt=719.0472477924085,
                base_dt=372,
                base_dist=15664.958477593225,
                base_emissions=419012407794.12,
                base_emissions_g=49632.55999999998,
                base_tt_cost=14726327196.219152,
                base_dt_cost=16087422555.999998,
                base_dist_cost=174638210099.76627,
                base_energy_cost=2281204878.0702214,
                base_emissions_cost=1120596676.8463018,
                base_link_flows=scenario.get('base_link_flows'),
                base_mode_ton_miles={'waterway': {'low': 4956904169207.093,
                                                  'moderate': 0.0,
                                                  'high': 0.0},
                                     'road': {'low': 1273797055677.7185,
                                              'moderate': 885746067073.6261,
                                              'high': 220172979977.71442},
                                     'rail': {'low': 5056351985974.221,
                                              'moderate': 931205216065.5125,
                                              'high': 0.0}},
                base_mode_emissions={'waterway': {'low': 53980686402666.7,
                                                  'moderate': 0.0,
                                                  'high': 0.0},
                                     'road': {'low': 83115257882969.19,
                                              'moderate': 57794930876554.984,
                                              'high': 14366286943545.424},
                                     'rail': {'low': 130201063638835.17,
                                              'moderate': 23978534313686.9,
                                              'high': 0.0}},
                base_mode_ton_mile_shares={'waterway': {'low': 0.4391672544290296,
                                                        'moderate': 0.0,
                                                        'high': 0.0},
                                           'road': {'low': 0.11285470457889621,
                                                    'moderate': 0.48749026751188757,
                                                    'high': 1.0},
                                           'rail': {'low': 0.4479780409921208,
                                                    'moderate': 0.5125097324880447,
                                                    'high': 0.0}},
                base_mode_emissions_shares={'waterway': {'low': 0.2019502082040518,
                                                         'moderate': 0.0,
                                                         'high': 0.0},
                                            'road': {'low': 0.3109472063617531,
                                                     'moderate': 0.7067687634625093,
                                                     'high': 1.0},
                                            'rail': {'low': 0.4871025854342008,
                                                     'moderate': 0.29323123653743566,
                                                     'high': 0.0}},
                base_total_ton_miles={'low': 11287053210858.506,
                                      'moderate': 1816951283139.2617,
                                      'high': 220172979977.71442},
                base_total_emissions={'low': 267297007924469.53,
                                      'moderate': 81773465190246.39,
                                      'high': 14366286943545.424}
            )

        # ----------------------------- keep
        model_output_text_time = html.Div([
            html.P(f"Travel Time Reduction Target: {travel_time_reduction}%"),
            html.P(f"Selected Truck Fuel: {truck_fuel}"),
            html.P(f"Selected Rail Fuel: {rail_fuel}"),
            html.P(f"Selected Waterway Fuel: {waterway_fuel}"),
        ], style={"display": "none"})
        # -------------------------------

        mode_ton_mile_shares = results[scenario['name']]['mode_ton_mile_shares']
        mode_emissions_shares = results[scenario['name']]['mode_emissions_shares']
        base_mode_ton_mile_shares = results[scenario['name']]['base_mode_ton_mile_shares']
        base_mode_emissions_shares = results[scenario['name']]['base_mode_emissions_shares']

        commodity_classes = ['low', 'moderate', 'high']

        # Define the desired mode order
        mode_order = ["waterway", "rail", "road"]

        colors_ = {'road': 'red', 'rail': 'orange', 'waterway': 'blue'}
        ton_mile_share_fig_travel_time = go.Figure()

        for mode in mode_order:
            # Baseline Trace
            ton_mile_share_fig_travel_time.add_trace(go.Bar(
                x=commodity_classes,
                y=[base_mode_ton_mile_shares[mode][cls] for cls in commodity_classes],
                name=f"{mode.capitalize()} (Baseline)",
                marker=dict(color=colors_[mode], pattern=dict(shape="\\")),
                offsetgroup=f"{mode}_baseline",
                legendgroup=f"{mode}_baseline"
            ))

            # Scenario Trace
            ton_mile_share_fig_travel_time.add_trace(go.Bar(
                x=commodity_classes,
                y=[mode_ton_mile_shares[mode][cls] for cls in commodity_classes],
                name=f"{mode.capitalize()} (Scenario)",
                marker_color=colors_[mode],
                offsetgroup=f"{mode}_scenario",
                legendgroup=f"{mode}_scenario"
            ))

        # Update layout
        ton_mile_share_fig_travel_time.update_layout(
            barmode="group",
            title="Mode Ton-Mile Share by Commodity Class",
            xaxis_title="Commodity Class",
            yaxis_title="Ton-Mile Share",
            legend_title="Mode & Scenario",
            height=500,
            xaxis_tickangle=-45
        )

        # Emissions Share Figure
        emissions_share_fig_travel_time = go.Figure()

        for mode in mode_order:
            # Baseline Trace
            emissions_share_fig_travel_time.add_trace(go.Bar(
                x=commodity_classes,
                y=[base_mode_emissions_shares[mode][cls] for cls in commodity_classes],
                name=f"{mode.capitalize()} (Baseline)",
                marker=dict(color=colors_[mode], pattern=dict(shape="\\")),
                offsetgroup=f"{mode}_baseline",
                legendgroup=f"{mode}_baseline"
            ))

            # Scenario Trace
            emissions_share_fig_travel_time.add_trace(go.Bar(
                x=commodity_classes,
                y=[mode_emissions_shares[mode][cls] for cls in commodity_classes],
                name=f"{mode.capitalize()} (Scenario)",
                marker_color=colors_[mode],
                offsetgroup=f"{mode}_scenario",
                legendgroup=f"{mode}_scenario"
            ))

        # Update layout
        emissions_share_fig_travel_time.update_layout(
            barmode="group",
            title="Mode Emissions Share by Commodity Class",
            xaxis_title="Commodity Class",
            yaxis_title="Emissions Share",
            legend_title="Mode & Scenario",
            height=500,
            xaxis_tickangle=-45
        )

        df_percent_system_totals = df_system_totals.copy()
        df_percent_system_totals["Scenario 1"] = 100 * df_system_totals["Scenario 1"] / df_system_totals[
            "Scenario 1"].sum()
        df_percent_system_totals["Scenario 2"] = 100 * df_system_totals["Scenario 2"] / df_system_totals[
            "Scenario 2"].sum()

        modes = df_percent_system_totals["Mode"].tolist()
        scenario1_percent = df_percent_system_totals["Scenario 1"].tolist()
        scenario2_percent = df_percent_system_totals["Scenario 2"].tolist()

        mode_share_fig_travel_time = go.Figure()

        for i, mode in enumerate(modes):
            mode_share_fig_travel_time.add_trace(go.Bar(
                x=["Baseline", "Current Scenario"],
                y=[scenario1_percent[i], scenario2_percent[i]],
                name=mode.capitalize()
            ))

        mode_share_fig_travel_time.update_layout(
            barmode='stack',
            title="Mode Share of Total Ton-Miles",
            xaxis_title="Scenario",
            yaxis_title="Percentage Share (%)",
            yaxis=dict(gridcolor='lightgray'),
            legend_title="Mode",
            height=450
        )

        metric_names = [
            "Travel Time Cost", "Dwell Time Cost", "Distance Cost",
            "Energy Cost", "Emissions Cost"
        ]

        # Extract raw values
        base_values = [
            results[scenario['name']]['base_tt_cost'],
            results[scenario['name']]['base_dt_cost'],
            results[scenario['name']]['base_dist_cost'],
            results[scenario['name']]['base_energy_cost'],
            results[scenario['name']]['base_emissions_cost']
        ]
        current_values = [
            results[scenario['name']]['travel_time_cost'],
            results[scenario['name']]['dwell_time_cost'],
            results[scenario['name']]['transportation_cost'],
            results[scenario['name']]['energy_cost'],
            results[scenario['name']]['emissions_cost']
        ]

        # Compute total costs
        base_total = sum(base_values)
        current_total = sum(current_values)

        # Compute percentage share of each component
        base_percentages = [(val / base_total) * 100 for val in base_values]
        current_percentages = [(val / current_total) * 100 for val in current_values]

        # Create stacked bar chart
        stacked_cost_fig_travel_time = go.Figure()

        # Add each cost component as a separate trace
        colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd']

        for i, name in enumerate(metric_names):
            stacked_cost_fig_travel_time.add_trace(go.Bar(
                name=name,
                x=['Baseline', 'Current'],
                y=[base_percentages[i], current_percentages[i]],
                marker_color=colors[i],
                text=[f"{base_percentages[i]:.1f}%", f"{current_percentages[i]:.1f}%"],
                textposition='auto'
            ))

        # Update layout
        stacked_cost_fig_travel_time.update_layout(
            title="Cost Component Shares of Total Cost",
            barmode='stack',
            yaxis=dict(title='Share of Total Cost (%)', range=[0, 100]),
            xaxis=dict(title='Scenario'),
            legend_title="Cost Components",
            template='plotly_white',
            height=500
        )

        metric_names_filtered = ['Travel Time', 'Emissions']

        # Extract just travel time and emissions
        base_tt = results[scenario['name']]['base_tt']
        base_emissions = results[scenario['name']]['base_emissions_g']
        current_tt = results[scenario['name']]['travel_time']
        current_emissions = results[scenario['name']]['emissions_g']

        # Compute percentage change
        percent_change_tt = ((current_tt - base_tt) / base_tt) * 100
        percent_change_emissions = ((current_emissions - base_emissions) / base_emissions) * 100

        # Create the figure
        fig_dual_y_travel_time = go.Figure()

        # Travel Time % Change Bar (Y-axis 1 - left)
        fig_dual_y_travel_time.add_trace(go.Bar(
            name='Travel Time % Change',
            x=[metric_names_filtered[0]],
            y=[percent_change_tt],
            marker_color='orange',
            yaxis='y'
        ))

        # Emissions % Change Bar (Y-axis 2 - right)
        fig_dual_y_travel_time.add_trace(go.Bar(
            name='Emissions % Change',
            x=[metric_names_filtered[1]],
            y=[percent_change_emissions],
            marker_color='green',
            yaxis='y2'
        ))

        # Layout with dual Y-axes (both now showing percentage change)
        fig_dual_y_travel_time.update_layout(
            title="Percentage Change in Travel Time and Emissions",
            yaxis=dict(
                title="Travel Time (% Change)",
                tickfont=dict(color="orange"),
                zeroline=True,
                zerolinecolor='gray'
            ),
            yaxis2=dict(
                title="Emissions (% Change)",
                tickfont=dict(color="green"),
                overlaying='y',
                side='right',
                zeroline=True,
                zerolinecolor='gray'
            ),
            barmode='group',
            template='plotly_white',
            legend=dict(orientation='h', yanchor='bottom', y=-0.3, xanchor='center', x=0.5),
            height=500
        )

        # return model_output_text, ton_mile_share_fig, emissions_share_fig, modal_shift_fig, mode_share_fig, stacked_cost_fig, fig_dual_y
        return model_output_text_time, ton_mile_share_fig_travel_time, emissions_share_fig_travel_time, mode_share_fig_travel_time, stacked_cost_fig_travel_time, fig_dual_y_travel_time

    # ------------------------------------------------------------------------------------------------------------------------------ for choice being travel time - end

    # ------------------------------------------------------------------------------------------------------------------------------ for choice being fuel - start
    def get_facility_outputs(toggle_value, slider_value):
        global num_facilities
        if toggle_value == "yes":
            num_facilities = slider_value
            return {"display": "block"}, f"Number of Facilities: {num_facilities}", num_facilities
        else:
            num_facilities = 0
            return {"display": "none"}, "", num_facilities

    @app.callback(
        Output("intermodal-slider-container-energy", "style"),
        Output("num-facilities-output-energy", "children"),
        Output("intermodal-slider-energy", "value"),
        Input("intermodal-toggle-energy", "value"),
        Input("intermodal-slider-energy", "value"),
    )
    def update_slider_and_display(toggle_value, slider_value):
        style, label, slider_val = get_facility_outputs(toggle_value, slider_value)
        return style, label, slider_val

    @app.callback(
        [Output("model-results-energy", "children"),
         Output("ton_mile_share_fig_energy", "figure"),
         Output("emissions_share_fig_energy", "figure"),
         # Output("modal_shift_fig", "figure"),
         Output("mode_share_fig_energy", "figure"),
         Output("stacked_cost_fig_energy", "figure"),
         Output("fig_dual_y_energy", "figure"), ],
        [Input("run-model-btn-energy", "n_clicks")],
        [State("energy-slider", "value"),
         State("truck-fuel-dropdown", "value"),
         State("rail-fuel-dropdown", "value"),
         State("waterway-fuel-dropdown", "value")],
        prevent_initial_call=True
    )
    def execute_model(n_clicks, energy_reduction, truck_fuel, rail_fuel, waterway_fuel):
        ctx = callback_context
        if not ctx.triggered:
            return dash.no_update, False

        run_model, load_scenario_energy_cost_parameters, congestion_cost_calculations, run_model_congestion_iterations, transform_results_to_viz, generate_viz_results = mparouti()

        file_name = "hub_loc_files\od_pairs_dash_emissions.json"
        with open(file_name, "r") as f:
            od_pairs = json.load(f)

        file_path = "hub_loc_files\exploded_national_FINAL_dashboard_1_3_2025.pkl"
        with open(file_path, 'rb') as file:
            loaded_graph_exploded = pickle.load(file)

        file_name = "hub_loc_files\link_flows_base_emissions.json"
        with open(file_name, "r") as f:
            link_flows_loaded = json.load(f)
        link_flows_loaded = {eval(k): v for k, v in link_flows_loaded.items()}

        scenarios = [
            {
                'name': 'Baseline Scenario',
                'od_pairs': od_pairs,
                'congestion_level': 'no',
                'max_open_intermediate_hubs': num_facilities,
                'restricted_edges': None,
                'fixed_hubs': None,
                'road_energy_type': truck_fuel,
                'rail_energy_type': rail_fuel,
                'waterway_energy_type': waterway_fuel,
                'arc_cap': False,
                'node_cap': False,
                'congestion': False,
                'dwell_t': True,
                'energy_reduction': energy_reduction / 100,
                'base_link_flows': link_flows_loaded,
            },
        ]

        global results
        results = {}
        for scenario in scenarios:
            G, (m, x, z), runtime, hub_ids, df_system_totals, df_results = run_model(
                scenario=scenario,
                G=loaded_graph_exploded,
                od_pairs=scenario['od_pairs'],
                hub_budget=scenario.get('max_open_intermediate_hubs'),
                mode_tech={'road': scenario.get('road_energy_type'), 'rail': scenario.get('rail_energy_type'),
                           'waterway': scenario.get('waterway_energy_type')},
                congestion_travel_time_increase=None,
                fixed_hubs=scenario.get('fixed_hubs'),
                restricted_nodes=scenario.get('restricted_node'),
                restricted_edges=scenario.get('restricted_edges'),
                capped_arcs=scenario.get('arc_cap'),
                capped_nodes=scenario.get('node_cap'),
                energy_lever=True,
                reduction_factor_energy=energy_reduction / 100,
                base_tt=719.0472477924085,
                base_dt=372,
                base_dist=15664.958477593225,
                base_emissions=419012407794.12,
                base_emissions_g=49632.55999999998,
                base_tt_cost=14726327196.219152,
                base_dt_cost=16087422555.999998,
                base_dist_cost=174638210099.76627,
                base_energy_cost=2281204878.0702214,
                base_emissions_cost=1120596676.8463018,
                base_link_flows=scenario.get('base_link_flows'),
                base_mode_ton_miles={'waterway': {'low': 4956904169207.093,
                                                  'moderate': 0.0,
                                                  'high': 0.0},
                                     'road': {'low': 1273797055677.7185,
                                              'moderate': 885746067073.6261,
                                              'high': 220172979977.71442},
                                     'rail': {'low': 5056351985974.221,
                                              'moderate': 931205216065.5125,
                                              'high': 0.0}},
                base_mode_emissions={'waterway': {'low': 53980686402666.7,
                                                  'moderate': 0.0,
                                                  'high': 0.0},
                                     'road': {'low': 83115257882969.19,
                                              'moderate': 57794930876554.984,
                                              'high': 14366286943545.424},
                                     'rail': {'low': 130201063638835.17,
                                              'moderate': 23978534313686.9,
                                              'high': 0.0}},
                base_mode_ton_mile_shares={'waterway': {'low': 0.4391672544290296,
                                                        'moderate': 0.0,
                                                        'high': 0.0},
                                           'road': {'low': 0.11285470457889621,
                                                    'moderate': 0.48749026751188757,
                                                    'high': 1.0},
                                           'rail': {'low': 0.4479780409921208,
                                                    'moderate': 0.5125097324880447,
                                                    'high': 0.0}},
                base_mode_emissions_shares={'waterway': {'low': 0.2019502082040518,
                                                         'moderate': 0.0,
                                                         'high': 0.0},
                                            'road': {'low': 0.3109472063617531,
                                                     'moderate': 0.7067687634625093,
                                                     'high': 1.0},
                                            'rail': {'low': 0.4871025854342008,
                                                     'moderate': 0.29323123653743566,
                                                     'high': 0.0}},
                base_total_ton_miles={'low': 11287053210858.506,
                                      'moderate': 1816951283139.2617,
                                      'high': 220172979977.71442},
                base_total_emissions={'low': 267297007924469.53,
                                      'moderate': 81773465190246.39,
                                      'high': 14366286943545.424}
            )

        # ----------------------------- keep
        model_output_text_time = html.Div([
            html.P(f"Travel Time Reduction Target: {energy_reduction}%"),
            html.P(f"Selected Truck Fuel: {truck_fuel}"),
            html.P(f"Selected Rail Fuel: {rail_fuel}"),
            html.P(f"Selected Waterway Fuel: {waterway_fuel}"),
        ], style={"display": "none"})
        # -------------------------------

        mode_ton_mile_shares = results[scenario['name']]['mode_ton_mile_shares']
        mode_emissions_shares = results[scenario['name']]['mode_emissions_shares']
        base_mode_ton_mile_shares = results[scenario['name']]['base_mode_ton_mile_shares']
        base_mode_emissions_shares = results[scenario['name']]['base_mode_emissions_shares']

        commodity_classes = ['low', 'moderate', 'high']

        # Define the desired mode order
        mode_order = ["waterway", "rail", "road"]

        colors_ = {'road': 'red', 'rail': 'orange', 'waterway': 'blue'}
        ton_mile_share_fig_energy = go.Figure()

        for mode in mode_order:
            # Baseline Trace
            ton_mile_share_fig_energy.add_trace(go.Bar(
                x=commodity_classes,
                y=[base_mode_ton_mile_shares[mode][cls] for cls in commodity_classes],
                name=f"{mode.capitalize()} (Baseline)",
                marker=dict(color=colors_[mode], pattern=dict(shape="\\")),
                offsetgroup=f"{mode}_baseline",
                legendgroup=f"{mode}_baseline"
            ))

            # Scenario Trace
            ton_mile_share_fig_energy.add_trace(go.Bar(
                x=commodity_classes,
                y=[mode_ton_mile_shares[mode][cls] for cls in commodity_classes],
                name=f"{mode.capitalize()} (Scenario)",
                marker_color=colors_[mode],
                offsetgroup=f"{mode}_scenario",
                legendgroup=f"{mode}_scenario"
            ))

        # Update layout
        ton_mile_share_fig_energy.update_layout(
            barmode="group",
            title="Mode Ton-Mile Share by Commodity Class",
            xaxis_title="Commodity Class",
            yaxis_title="Ton-Mile Share",
            legend_title="Mode & Scenario",
            height=500,
            xaxis_tickangle=-45
        )

        # Emissions Share Figure
        emissions_share_fig_energy = go.Figure()

        for mode in mode_order:
            # Baseline Trace
            emissions_share_fig_energy.add_trace(go.Bar(
                x=commodity_classes,
                y=[base_mode_emissions_shares[mode][cls] for cls in commodity_classes],
                name=f"{mode.capitalize()} (Baseline)",
                marker=dict(color=colors_[mode], pattern=dict(shape="\\")),
                offsetgroup=f"{mode}_baseline",
                legendgroup=f"{mode}_baseline"
            ))

            # Scenario Trace
            emissions_share_fig_energy.add_trace(go.Bar(
                x=commodity_classes,
                y=[mode_emissions_shares[mode][cls] for cls in commodity_classes],
                name=f"{mode.capitalize()} (Scenario)",
                marker_color=colors_[mode],
                offsetgroup=f"{mode}_scenario",
                legendgroup=f"{mode}_scenario"
            ))

        # Update layout
        emissions_share_fig_energy.update_layout(
            barmode="group",
            title="Mode Emissions Share by Commodity Class",
            xaxis_title="Commodity Class",
            yaxis_title="Emissions Share",
            legend_title="Mode & Scenario",
            height=500,
            xaxis_tickangle=-45
        )

        df_percent_system_totals = df_system_totals.copy()
        df_percent_system_totals["Scenario 1"] = 100 * df_system_totals["Scenario 1"] / df_system_totals[
            "Scenario 1"].sum()
        df_percent_system_totals["Scenario 2"] = 100 * df_system_totals["Scenario 2"] / df_system_totals[
            "Scenario 2"].sum()

        modes = df_percent_system_totals["Mode"].tolist()
        scenario1_percent = df_percent_system_totals["Scenario 1"].tolist()
        scenario2_percent = df_percent_system_totals["Scenario 2"].tolist()

        mode_share_fig_energy = go.Figure()

        for i, mode in enumerate(modes):
            mode_share_fig_energy.add_trace(go.Bar(
                x=["Baseline", "Current Scenario"],
                y=[scenario1_percent[i], scenario2_percent[i]],
                name=mode.capitalize()
            ))

        mode_share_fig_energy.update_layout(
            barmode='stack',
            title="Mode Share of Total Ton-Miles",
            xaxis_title="Scenario",
            yaxis_title="Percentage Share (%)",
            yaxis=dict(gridcolor='lightgray'),
            legend_title="Mode",
            height=450
        )

        metric_names = [
            "Travel Time Cost", "Dwell Time Cost", "Distance Cost",
            "Energy Cost", "Emissions Cost"
        ]

        # Extract raw values
        base_values = [
            results[scenario['name']]['base_tt_cost'],
            results[scenario['name']]['base_dt_cost'],
            results[scenario['name']]['base_dist_cost'],
            results[scenario['name']]['base_energy_cost'],
            results[scenario['name']]['base_emissions_cost']
        ]
        current_values = [
            results[scenario['name']]['travel_time_cost'],
            results[scenario['name']]['dwell_time_cost'],
            results[scenario['name']]['transportation_cost'],
            results[scenario['name']]['energy_cost'],
            results[scenario['name']]['emissions_cost']
        ]

        # Compute total costs
        base_total = sum(base_values)
        current_total = sum(current_values)

        # Compute percentage share of each component
        base_percentages = [(val / base_total) * 100 for val in base_values]
        current_percentages = [(val / current_total) * 100 for val in current_values]

        # Create stacked bar chart
        stacked_cost_fig_energy = go.Figure()

        # Add each cost component as a separate trace
        colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd']

        for i, name in enumerate(metric_names):
            stacked_cost_fig_energy.add_trace(go.Bar(
                name=name,
                x=['Baseline', 'Current'],
                y=[base_percentages[i], current_percentages[i]],
                marker_color=colors[i],
                text=[f"{base_percentages[i]:.1f}%", f"{current_percentages[i]:.1f}%"],
                textposition='auto'
            ))

        # Update layout
        stacked_cost_fig_energy.update_layout(
            title="Cost Component Shares of Total Cost",
            barmode='stack',
            yaxis=dict(title='Share of Total Cost (%)', range=[0, 100]),
            xaxis=dict(title='Scenario'),
            legend_title="Cost Components",
            template='plotly_white',
            height=500
        )

        metric_names_filtered = ['Travel Time', 'Emissions']

        # Extract just travel time and emissions
        base_tt = results[scenario['name']]['base_tt']
        base_emissions = results[scenario['name']]['base_emissions_g']
        current_tt = results[scenario['name']]['travel_time']
        current_emissions = results[scenario['name']]['emissions_g']

        # Compute percentage change
        percent_change_tt = ((current_tt - base_tt) / base_tt) * 100
        percent_change_emissions = ((current_emissions - base_emissions) / base_emissions) * 100

        # Create the figure
        fig_dual_y_energy = go.Figure()

        # Travel Time % Change Bar (Y-axis 1 - left)
        fig_dual_y_energy.add_trace(go.Bar(
            name='Travel Time % Change',
            x=[metric_names_filtered[0]],
            y=[percent_change_tt],
            marker_color='orange',
            yaxis='y'
        ))

        # Emissions % Change Bar (Y-axis 2 - right)
        fig_dual_y_energy.add_trace(go.Bar(
            name='Emissions % Change',
            x=[metric_names_filtered[1]],
            y=[percent_change_emissions],
            marker_color='green',
            yaxis='y2'
        ))

        # Layout with dual Y-axes (both now showing percentage change)
        fig_dual_y_energy.update_layout(
            title="Percentage Change in Travel Time and Emissions",
            yaxis=dict(
                title="Travel Time (% Change)",
                tickfont=dict(color="orange"),
                zeroline=True,
                zerolinecolor='gray'
            ),
            yaxis2=dict(
                title="Emissions (% Change)",
                tickfont=dict(color="green"),
                overlaying='y',
                side='right',
                zeroline=True,
                zerolinecolor='gray'
            ),
            barmode='group',
            template='plotly_white',
            legend=dict(orientation='h', yanchor='bottom', y=-0.3, xanchor='center', x=0.5),
            height=500
        )

        # return model_output_text, ton_mile_share_fig, emissions_share_fig, modal_shift_fig, mode_share_fig, stacked_cost_fig, fig_dual_y
        return model_output_text_time, ton_mile_share_fig_energy, emissions_share_fig_energy, mode_share_fig_energy, stacked_cost_fig_energy, fig_dual_y_energy

    # ------------------------------------------------------------------------------------------------------------------------------ for choice being fuel - end


    # ------------------------------------------------------------------------------------------------------------------------------ for choice being dist cost - start
    def get_facility_outputs(toggle_value, slider_value):
        global num_facilities
        if toggle_value == "yes":
            num_facilities = slider_value
            return {"display": "block"}, f"Number of Facilities: {num_facilities}", num_facilities
        else:
            num_facilities = 0
            return {"display": "none"}, "", num_facilities

    @app.callback(
        Output("intermodal-slider-container-dist", "style"),
        Output("num-facilities-output-dist", "children"),
        Output("intermodal-slider-dist", "value"),
        Input("intermodal-toggle-dist", "value"),
        Input("intermodal-slider-dist", "value"),
    )
    def update_slider_and_display(toggle_value, slider_value):
        style, label, slider_val = get_facility_outputs(toggle_value, slider_value)
        return style, label, slider_val

    @app.callback(
        [Output("model-results-dist", "children"),
         Output("ton_mile_share_fig_dist", "figure"),
         Output("emissions_share_fig_dist", "figure"),
         # Output("modal_shift_fig", "figure"),
         Output("mode_share_fig_dist", "figure"),
         Output("stacked_cost_fig_dist", "figure"),
         Output("fig_dual_y_dist", "figure"), ],
        [Input("run-model-btn-dist", "n_clicks")],
        [State("dist-slider", "value"),
         State("truck-fuel-dropdown", "value"),
         State("rail-fuel-dropdown", "value"),
         State("waterway-fuel-dropdown", "value")],
        prevent_initial_call=True
    )
    def execute_model(n_clicks, dist_reduction, truck_fuel, rail_fuel, waterway_fuel):
        ctx = callback_context
        if not ctx.triggered:
            return dash.no_update, False

        run_model, load_scenario_energy_cost_parameters, congestion_cost_calculations, run_model_congestion_iterations, transform_results_to_viz, generate_viz_results = mparouti()

        file_name = "hub_loc_files\od_pairs_dash_emissions.json"
        with open(file_name, "r") as f:
            od_pairs = json.load(f)

        file_path = "hub_loc_files\exploded_national_FINAL_dashboard_1_3_2025.pkl"
        with open(file_path, 'rb') as file:
            loaded_graph_exploded = pickle.load(file)

        file_name = "hub_loc_files\link_flows_base_emissions.json"
        with open(file_name, "r") as f:
            link_flows_loaded = json.load(f)
        link_flows_loaded = {eval(k): v for k, v in link_flows_loaded.items()}

        scenarios = [
            {
                'name': 'Baseline Scenario',
                'od_pairs': od_pairs,
                'congestion_level': 'no',
                'max_open_intermediate_hubs': num_facilities,
                'restricted_edges': None,
                'fixed_hubs': None,
                'road_energy_type': truck_fuel,
                'rail_energy_type': rail_fuel,
                'waterway_energy_type': waterway_fuel,
                'arc_cap': False,
                'node_cap': False,
                'congestion': False,
                'dwell_t': True,
                'dist_reduction': dist_reduction / 100,
                'base_link_flows': link_flows_loaded,
            },
        ]

        global results
        results = {}
        for scenario in scenarios:
            G, (m, x, z), runtime, hub_ids, df_system_totals, df_results = run_model(
                scenario=scenario,
                G=loaded_graph_exploded,
                od_pairs=scenario['od_pairs'],
                hub_budget=scenario.get('max_open_intermediate_hubs'),
                mode_tech={'road': scenario.get('road_energy_type'), 'rail': scenario.get('rail_energy_type'),
                           'waterway': scenario.get('waterway_energy_type')},
                congestion_travel_time_increase=None,
                fixed_hubs=scenario.get('fixed_hubs'),
                restricted_nodes=scenario.get('restricted_node'),
                restricted_edges=scenario.get('restricted_edges'),
                capped_arcs=scenario.get('arc_cap'),
                capped_nodes=scenario.get('node_cap'),
                dist_cost_lever=True,
                reduction_factor_dist_cost=dist_reduction / 100,
                base_tt=719.0472477924085,
                base_dt=372,
                base_dist=15664.958477593225,
                base_emissions=419012407794.12,
                base_emissions_g=49632.55999999998,
                base_tt_cost=14726327196.219152,
                base_dt_cost=16087422555.999998,
                base_dist_cost=174638210099.76627,
                base_energy_cost=2281204878.0702214,
                base_emissions_cost=1120596676.8463018,
                base_link_flows=scenario.get('base_link_flows'),
                base_mode_ton_miles={'waterway': {'low': 4956904169207.093,
                                                  'moderate': 0.0,
                                                  'high': 0.0},
                                     'road': {'low': 1273797055677.7185,
                                              'moderate': 885746067073.6261,
                                              'high': 220172979977.71442},
                                     'rail': {'low': 5056351985974.221,
                                              'moderate': 931205216065.5125,
                                              'high': 0.0}},
                base_mode_emissions={'waterway': {'low': 53980686402666.7,
                                                  'moderate': 0.0,
                                                  'high': 0.0},
                                     'road': {'low': 83115257882969.19,
                                              'moderate': 57794930876554.984,
                                              'high': 14366286943545.424},
                                     'rail': {'low': 130201063638835.17,
                                              'moderate': 23978534313686.9,
                                              'high': 0.0}},
                base_mode_ton_mile_shares={'waterway': {'low': 0.4391672544290296,
                                                        'moderate': 0.0,
                                                        'high': 0.0},
                                           'road': {'low': 0.11285470457889621,
                                                    'moderate': 0.48749026751188757,
                                                    'high': 1.0},
                                           'rail': {'low': 0.4479780409921208,
                                                    'moderate': 0.5125097324880447,
                                                    'high': 0.0}},
                base_mode_emissions_shares={'waterway': {'low': 0.2019502082040518,
                                                         'moderate': 0.0,
                                                         'high': 0.0},
                                            'road': {'low': 0.3109472063617531,
                                                     'moderate': 0.7067687634625093,
                                                     'high': 1.0},
                                            'rail': {'low': 0.4871025854342008,
                                                     'moderate': 0.29323123653743566,
                                                     'high': 0.0}},
                base_total_ton_miles={'low': 11287053210858.506,
                                      'moderate': 1816951283139.2617,
                                      'high': 220172979977.71442},
                base_total_emissions={'low': 267297007924469.53,
                                      'moderate': 81773465190246.39,
                                      'high': 14366286943545.424}
            )

        # ----------------------------- keep
        model_output_text_time = html.Div([
            html.P(f"Distance cost Reduction Target: {dist_reduction}%"),
            html.P(f"Selected Truck Fuel: {truck_fuel}"),
            html.P(f"Selected Rail Fuel: {rail_fuel}"),
            html.P(f"Selected Waterway Fuel: {waterway_fuel}"),
        ], style={"display": "none"})
        # -------------------------------

        mode_ton_mile_shares = results[scenario['name']]['mode_ton_mile_shares']
        mode_emissions_shares = results[scenario['name']]['mode_emissions_shares']
        base_mode_ton_mile_shares = results[scenario['name']]['base_mode_ton_mile_shares']
        base_mode_emissions_shares = results[scenario['name']]['base_mode_emissions_shares']

        commodity_classes = ['low', 'moderate', 'high']

        # Define the desired mode order
        mode_order = ["waterway", "rail", "road"]

        colors_ = {'road': 'red', 'rail': 'orange', 'waterway': 'blue'}
        ton_mile_share_fig_dist = go.Figure()

        for mode in mode_order:
            # Baseline Trace
            ton_mile_share_fig_dist.add_trace(go.Bar(
                x=commodity_classes,
                y=[base_mode_ton_mile_shares[mode][cls] for cls in commodity_classes],
                name=f"{mode.capitalize()} (Baseline)",
                marker=dict(color=colors_[mode], pattern=dict(shape="\\")),
                offsetgroup=f"{mode}_baseline",
                legendgroup=f"{mode}_baseline"
            ))

            # Scenario Trace
            ton_mile_share_fig_dist.add_trace(go.Bar(
                x=commodity_classes,
                y=[mode_ton_mile_shares[mode][cls] for cls in commodity_classes],
                name=f"{mode.capitalize()} (Scenario)",
                marker_color=colors_[mode],
                offsetgroup=f"{mode}_scenario",
                legendgroup=f"{mode}_scenario"
            ))

        # Update layout
        ton_mile_share_fig_dist.update_layout(
            barmode="group",
            title="Mode Ton-Mile Share by Commodity Class",
            xaxis_title="Commodity Class",
            yaxis_title="Ton-Mile Share",
            legend_title="Mode & Scenario",
            height=500,
            xaxis_tickangle=-45
        )

        # Emissions Share Figure
        emissions_share_fig_dist = go.Figure()

        for mode in mode_order:
            # Baseline Trace
            emissions_share_fig_dist.add_trace(go.Bar(
                x=commodity_classes,
                y=[base_mode_emissions_shares[mode][cls] for cls in commodity_classes],
                name=f"{mode.capitalize()} (Baseline)",
                marker=dict(color=colors_[mode], pattern=dict(shape="\\")),
                offsetgroup=f"{mode}_baseline",
                legendgroup=f"{mode}_baseline"
            ))

            # Scenario Trace
            emissions_share_fig_dist.add_trace(go.Bar(
                x=commodity_classes,
                y=[mode_emissions_shares[mode][cls] for cls in commodity_classes],
                name=f"{mode.capitalize()} (Scenario)",
                marker_color=colors_[mode],
                offsetgroup=f"{mode}_scenario",
                legendgroup=f"{mode}_scenario"
            ))

        # Update layout
        emissions_share_fig_dist.update_layout(
            barmode="group",
            title="Mode Emissions Share by Commodity Class",
            xaxis_title="Commodity Class",
            yaxis_title="Emissions Share",
            legend_title="Mode & Scenario",
            height=500,
            xaxis_tickangle=-45
        )

        df_percent_system_totals = df_system_totals.copy()
        df_percent_system_totals["Scenario 1"] = 100 * df_system_totals["Scenario 1"] / df_system_totals[
            "Scenario 1"].sum()
        df_percent_system_totals["Scenario 2"] = 100 * df_system_totals["Scenario 2"] / df_system_totals[
            "Scenario 2"].sum()

        modes = df_percent_system_totals["Mode"].tolist()
        scenario1_percent = df_percent_system_totals["Scenario 1"].tolist()
        scenario2_percent = df_percent_system_totals["Scenario 2"].tolist()

        mode_share_fig_dist = go.Figure()

        for i, mode in enumerate(modes):
            mode_share_fig_dist.add_trace(go.Bar(
                x=["Baseline", "Current Scenario"],
                y=[scenario1_percent[i], scenario2_percent[i]],
                name=mode.capitalize()
            ))

        mode_share_fig_dist.update_layout(
            barmode='stack',
            title="Mode Share of Total Ton-Miles",
            xaxis_title="Scenario",
            yaxis_title="Percentage Share (%)",
            yaxis=dict(gridcolor='lightgray'),
            legend_title="Mode",
            height=450
        )

        metric_names = [
            "Travel Time Cost", "Dwell Time Cost", "Distance Cost",
            "Energy Cost", "Emissions Cost"
        ]

        # Extract raw values
        base_values = [
            results[scenario['name']]['base_tt_cost'],
            results[scenario['name']]['base_dt_cost'],
            results[scenario['name']]['base_dist_cost'],
            results[scenario['name']]['base_energy_cost'],
            results[scenario['name']]['base_emissions_cost']
        ]
        current_values = [
            results[scenario['name']]['travel_time_cost'],
            results[scenario['name']]['dwell_time_cost'],
            results[scenario['name']]['transportation_cost'],
            results[scenario['name']]['energy_cost'],
            results[scenario['name']]['emissions_cost']
        ]

        # Compute total costs
        base_total = sum(base_values)
        current_total = sum(current_values)

        # Compute percentage share of each component
        base_percentages = [(val / base_total) * 100 for val in base_values]
        current_percentages = [(val / current_total) * 100 for val in current_values]

        # Create stacked bar chart
        stacked_cost_fig_dist = go.Figure()

        # Add each cost component as a separate trace
        colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd']

        for i, name in enumerate(metric_names):
            stacked_cost_fig_dist.add_trace(go.Bar(
                name=name,
                x=['Baseline', 'Current'],
                y=[base_percentages[i], current_percentages[i]],
                marker_color=colors[i],
                text=[f"{base_percentages[i]:.1f}%", f"{current_percentages[i]:.1f}%"],
                textposition='auto'
            ))

        # Update layout
        stacked_cost_fig_dist.update_layout(
            title="Cost Component Shares of Total Cost",
            barmode='stack',
            yaxis=dict(title='Share of Total Cost (%)', range=[0, 100]),
            xaxis=dict(title='Scenario'),
            legend_title="Cost Components",
            template='plotly_white',
            height=500
        )

        metric_names_filtered = ['Travel Time', 'Emissions']

        # Extract just travel time and emissions
        base_tt = results[scenario['name']]['base_tt']
        base_emissions = results[scenario['name']]['base_emissions_g']
        current_tt = results[scenario['name']]['travel_time']
        current_emissions = results[scenario['name']]['emissions_g']

        # Compute percentage change
        percent_change_tt = ((current_tt - base_tt) / base_tt) * 100
        percent_change_emissions = ((current_emissions - base_emissions) / base_emissions) * 100

        # Create the figure
        fig_dual_y_dist = go.Figure()

        # Travel Time % Change Bar (Y-axis 1 - left)
        fig_dual_y_dist.add_trace(go.Bar(
            name='Travel Time % Change',
            x=[metric_names_filtered[0]],
            y=[percent_change_tt],
            marker_color='orange',
            yaxis='y'
        ))

        # Emissions % Change Bar (Y-axis 2 - right)
        fig_dual_y_dist.add_trace(go.Bar(
            name='Emissions % Change',
            x=[metric_names_filtered[1]],
            y=[percent_change_emissions],
            marker_color='green',
            yaxis='y2'
        ))

        # Layout with dual Y-axes (both now showing percentage change)
        fig_dual_y_dist.update_layout(
            title="Percentage Change in Travel Time and Emissions",
            yaxis=dict(
                title="Travel Time (% Change)",
                tickfont=dict(color="orange"),
                zeroline=True,
                zerolinecolor='gray'
            ),
            yaxis2=dict(
                title="Emissions (% Change)",
                tickfont=dict(color="green"),
                overlaying='y',
                side='right',
                zeroline=True,
                zerolinecolor='gray'
            ),
            barmode='group',
            template='plotly_white',
            legend=dict(orientation='h', yanchor='bottom', y=-0.3, xanchor='center', x=0.5),
            height=500
        )

        # return model_output_text, ton_mile_share_fig, emissions_share_fig, modal_shift_fig, mode_share_fig, stacked_cost_fig, fig_dual_y
        return model_output_text_time, ton_mile_share_fig_dist, emissions_share_fig_dist, mode_share_fig_dist, stacked_cost_fig_dist, fig_dual_y_dist

    # ------------------------------------------------------------------------------------------------------------------------------ for choice being dist cost - end





    # @app.callback(
    #     Output("custom-weight-container", "style"),
    #     Input("optimization-objective", "value")
    # )
    # def toggle_weight_inputs(selected_option):
    #     if selected_option == "custom":
    #         return {"display": "block", "marginTop": "10px"}
    #     return {"display": "none"}

    @app.callback(
        Output("optimization-preferences-store", "data"),
        Input("optimization-objective", "value"),
        Input("weight-energy", "value"),
        Input("weight-emissions", "value"),
        Input("weight-time", "value"),
        Input("weight-cost", "value")
    )
    def get_optimization_preferences(objective_, w_energy, w_emissions, w_time, w_cost):
        global objective
        global weights
        if objective_ == "custom":
            objective = objective_
            weights = {
                "energy": w_energy or 0,
                "emissions": w_emissions or 0,
                "time": w_time or 0,
                "cost": w_cost or 0,
            }
            return {"objective": objective, "weights": weights}
        else:
            objective = objective_
            weights = {
                "energy": 1,
                "emissions": 1,
                "time": 1,
                "cost": 1,
            }
            return {"objective": objective}

    defined_freight_flows = [
    4354580, 4077957, 3573723, 3531965, 3253443, 3229440, 3105949, 2746998, 2382357, 2347656,
    2298192, 2068028, 1868534, 1833354, 1790175, 1777911, 1734243, 1727516, 1688504, 1642644,
    1629306, 1626657, 1589034, 1560798, 1548093, 1399914, 1375927, 1375854, 1308855, 1294347,
    1226157, 1207254, 1178528, 1162043, 1119845, 1107988, 1088170, 1046109, 1034607, 1030565,
    1005281, 978349, 949401, 31376239, 21230935, 16605845, 13820522, 12413186, 12363285]

    @app.callback(
        Output('demand-flow-input', 'value'),
        Input('demand-flow-option', 'value')
    )
    def update_demand_flow(option):
        if option == "predefined":
            return random.choice(defined_freight_flows)
        return None  # In this case, the user will manually enter value in demand-flow-input

    @app.callback(
        Output("another-component", "children"),
        Input("intermodal-toggle", "value"),
        Input("intermodal-slider", "value"),
    )
    def reuse_elsewhere(toggle_value, slider_value):
        global num_facilities
        _, _, num_facilities = get_facility_outputs(toggle_value, slider_value)
        return f"You selected {num_facilities} facilities"

    # def get_facility_outputs(toggle_value, slider_value):
    #     global num_facilities
    #     if toggle_value == "yes":
    #         num_facilities = slider_value
    #         return {"display": "block"}, f"Number of Facilities: {num_facilities}", num_facilities
    #     else:
    #         num_facilities = 0
    #         return {"display": "none"}, "", num_facilities

    @app.callback(
        Output('model-run-status', 'children'),
        Output('selected-nodes', 'data'),
        Output('node-selection-status', 'children'),
        Output('od-pairs', 'data'),
        Output('od-pair-list', 'children'),
        Output("stacked_cost_fig_opt", "figure"),
        Output("fig_dual_y_opt", "figure"),
        [Input(f'node-{row["id"]}', 'n_clicks') for _, row in nodes_gdf.iterrows()] +
        [Input('add-od-pair', 'n_clicks'),
         Input('initiate-optimization', 'n_clicks'),
         Input("reset-od-selection", "n_clicks")],
        State('selected-nodes', 'data'),
        State('demand-flow-input', 'value'),
        State('commodity-type', 'value'),
        State('od-pairs', 'data'),
        prevent_initial_call=True
    )

    def combined_callback(*args):
        ctx = dash.callback_context
        if not ctx.triggered:
            return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update

        triggered_id = ctx.triggered[0]['prop_id'].split('.')[0]

        # Unpack states
        selected_nodes = args[-4]
        demand_flow = args[-3]
        commodity_type = args[-2]
        existing_pairs = args[-1]
        stacked_cost_fig_opt = go.Figure()
        fig_dual_y_opt = go.Figure()


        # Handle node selection
        if "node-" in triggered_id:
            node_id = triggered_id.replace("node-", "")
            if selected_nodes["origin"] is None:
                selected_nodes["origin"] = f"{node_id}_O"
                return dash.no_update, selected_nodes, f"Origin node selected: {node_id}", dash.no_update, dash.no_update, dash.no_update, dash.no_update
            elif selected_nodes["destination"] is None:
                selected_nodes["destination"] = f"{node_id}_D"
                return dash.no_update, selected_nodes, f"Destination node selected: {node_id}", dash.no_update, dash.no_update, dash.no_update, dash.no_update
            else:
                return dash.no_update, selected_nodes, "Both origin and destination already selected. Add OD pair or reset.", dash.no_update, dash.no_update, dash.no_update, dash.no_update

        # Handle Add OD Pair
        elif triggered_id == "add-od-pair":
            if selected_nodes["origin"] and selected_nodes["destination"] and demand_flow and commodity_type:
                new_pair = (selected_nodes["origin"], selected_nodes["destination"], demand_flow, commodity_type)
                existing_pairs.append(new_pair)

                selected_nodes = {"origin": None, "destination": None}

                return dash.no_update, selected_nodes, "OD Pair added. Select a new origin and destination.", existing_pairs, dash.no_update, dash.no_update, dash.no_update
            # else:
            #     return "Please fill all fields before adding OD pair.", dash.no_update, dash.no_update, dash.no_update, dash.no_update
        elif triggered_id == "reset-od-selection":
            return dash.no_update, {"origin": None,
                                    "destination": None}, "Selection reset. Pick origin and destination or run model.", existing_pairs, dash.no_update, dash.no_update, dash.no_update

        # Handle Model Run
        elif triggered_id == "initiate-optimization":
            if not existing_pairs or len(existing_pairs) == 0:
                return "No OD pairs selected. Please define OD pairs before running the model.", dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update
            # ---------------- MODEL EXECUTION ----------------
            run_model, load_scenario_energy_cost_parameters, congestion_cost_calculations, run_model_congestion_iterations, transform_results_to_viz, generate_viz_results = mparouti()

            file_path = "hub_loc_files/exploded_national_FINAL_dashboard_1_3_2025.pkl"
            with open(file_path, 'rb') as file:
                loaded_graph_exploded = pickle.load(file)

            objectives = {'energy', 'emissions', 'time', 'cost'}
            scenarios = [
                {
                'name': 'User"s choice',
                'od_pairs': existing_pairs,
                'congestion_level': 'no',
                'max_open_intermediate_hubs': num_facilities,
                'restricted_edges': None,
                'fixed_hubs': None,
                'road_energy_type': 'diesel',
                'rail_energy_type': 'diesel',
                'waterway_energy_type': 'diesel',
                'arc_cap': False,
                'node_cap': False,
                'congestion': False,
                'dwell_t': True,
                'emissions_reduction': None,
                'base_link_flows': None,
                'objective':objective,
                'weights':weights
            }]

            for obj in objectives - {objective}:
                scenarios.append({
                    'name': f'{obj.capitalize()} Objective Scenario',
                    'od_pairs': existing_pairs,
                    'congestion_level': 'no',
                    'max_open_intermediate_hubs': num_facilities,
                    'restricted_edges': None,
                    'fixed_hubs': None,
                    'road_energy_type': 'diesel',
                    'rail_energy_type': 'diesel',
                    'waterway_energy_type': 'diesel',
                    'arc_cap': False,
                    'node_cap': False,
                    'congestion': False,
                    'dwell_t': True,
                    'emissions_reduction': None,
                    'base_link_flows': None,
                    'objective': obj,
                    'weights': weights
                })

            if objective != 'custom': #-------------add multiobjective scenario with equal weights to show differences
                scenarios.append({
                    'name': 'Custom Equal Weights Scenario',
                    'od_pairs': existing_pairs,
                    'congestion_level': 'no',
                    'max_open_intermediate_hubs': num_facilities,
                    'restricted_edges': None,
                    'fixed_hubs': None,
                    'road_energy_type': 'diesel',
                    'rail_energy_type': 'diesel',
                    'waterway_energy_type': 'diesel',
                    'arc_cap': False,
                    'node_cap': False,
                    'congestion': False,
                    'dwell_t': True,
                    'emissions_reduction': None,
                    'base_link_flows': None,
                    'objective': 'custom',
                    'weights': {'energy': 0.25, 'emissions': 0.25, 'time': 0.25, 'cost': 0.25}
                })

            global results
            results = {}
            viz_results = [] #------------------------------------ CHEKC IF NEEDED
            for scenario in scenarios:
                G, (m, x, z), runtime, viz_results, hub_ids = run_model(
                    scenario=scenario,
                    G=loaded_graph_exploded,
                    od_pairs=scenario['od_pairs'],
                    hub_budget=scenario.get('max_open_intermediate_hubs'),
                    mode_tech={'road': scenario.get('road_energy_type'), 'rail': scenario.get('rail_energy_type'),
                               'waterway': scenario.get('waterway_energy_type')},
                    congestion_travel_time_increase=None,
                    fixed_hubs=scenario.get('fixed_hubs'),
                    restricted_nodes=scenario.get('restricted_node'),
                    restricted_edges=scenario.get('restricted_edges'),
                    capped_arcs=scenario.get('arc_cap'),
                    capped_nodes=scenario.get('node_cap'),
                    emissions_lever=False,
                    optimization_lever=True,
                    objective=scenario.get('objective'),
                    weights=scenario.get('weights'),
                )

            metric_names = [
                "Travel Time Cost", "Dwell Time Cost", "Distance Cost",
                "Energy Cost", "Emissions Cost"
            ]
            colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd']

            # Collect all scenario names
            scenario_names = [sc['name'] for sc in scenarios]

            # Build data for all scenarios
            cost_percentages_all = []

            for sc in scenarios:
                sc_name = sc['name']
                current_values = [
                    results[sc_name]['travel_time_cost'],
                    results[sc_name]['dwell_time_cost'],
                    results[sc_name]['transportation_cost'],
                    results[sc_name]['energy_cost'],
                    results[sc_name]['emissions_cost']
                ]
                total = sum(current_values)
                percentages = [(val / total) * 100 for val in current_values]
                cost_percentages_all.append(percentages)

            # Transpose: Get each component's values across all scenarios
            stacked_cost_fig_opt = go.Figure()

            for i, name in enumerate(metric_names):
                y_vals = [scenario[i] for scenario in cost_percentages_all]
                stacked_cost_fig_opt.add_trace(go.Bar(
                    name=name,
                    x=scenario_names,
                    y=y_vals,
                    marker_color=colors[i],
                    text=[f"{val:.1f}%" for val in y_vals],
                    textposition='auto'
                ))

            # Update layout
            stacked_cost_fig_opt.update_layout(
                title="Cost Component Shares by Objective Scenario",
                barmode='stack',
                yaxis=dict(title='Share of Total Cost (%)', range=[0, 100]),
                xaxis=dict(title='Objective Scenario'),
                legend_title="Cost Components",
                template='plotly_white',
                height=500
            )

            # Store values per scenario
            x_labels = [sc['name'] for sc in scenarios]
            travel_time_vals = [results[sc['name']]['travel_time'] for sc in scenarios]
            emissions_vals = [results[sc['name']]['emissions_g'] for sc in scenarios]

            fig_dual_y_opt = go.Figure()

            # Travel Time Bars (Y1 - left axis)
            fig_dual_y_opt.add_trace(go.Bar(
                name='Travel Time',
                x=x_labels,
                y=travel_time_vals,
                marker_color='orange',
                yaxis='y',
                offsetgroup=0
            ))

            # Emissions Bars (Y2 - right axis)
            fig_dual_y_opt.add_trace(go.Bar(
                name='Emissions',
                x=x_labels,
                y=emissions_vals,
                marker_color='green',
                yaxis='y2',
                offsetgroup=1
            ))

            # Update layout
            fig_dual_y_opt.update_layout(
                title="Total Travel Time and Emissions Across Objective Scenarios",
                xaxis=dict(title="Scenarios"),
                yaxis=dict(
                    title="Travel Time (e.g., minutes or hours)",

                    tickfont=dict(color="orange"),
                    zeroline=True,
                    zerolinecolor='gray'
                ),
                yaxis2=dict(
                    title="Emissions (grams)",

                    tickfont=dict(color="green"),
                    overlaying='y',
                    side='right',
                    zeroline=True,
                    zerolinecolor='gray'
                ),
                barmode='group',
                template='plotly_white',
                legend=dict(orientation='h', yanchor='bottom', y=-0.3, xanchor='center', x=0.5),
                height=500
            )

        # Default fallback
        return (
            dash.no_update,
            dash.no_update,
            dash.no_update,
            dash.no_update,
            dash.no_update,
            stacked_cost_fig_opt,  # NEW: figure for Output('stacked-cost-plot', 'figure')
            fig_dual_y_opt,  # NEW: figure for Output('dual-axis-plot', 'figure')
        )


