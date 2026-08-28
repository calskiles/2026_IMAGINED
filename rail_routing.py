"""
Given the Origin and Destination zip code
Get origin short haul truck routes (highway or road name, distance (meters), route polyline)
rail yard name, rail routes (distance, routes)
and destination short haul truck routes (highway or road name, distance (meters), route polyline)
"""

import os
import geopandas as gpd
import pandas as pd
import numpy as np

from shapely.geometry import Point, LineString, MultiLineString
import matplotlib.pyplot as plt
from shapely.ops import nearest_points, unary_union
from scipy.spatial import KDTree
from geopy.distance import geodesic
import polyline
from shapely.ops import linemerge
import plotly.graph_objects as go

import networkx as nx
import momepy
import itertools
import googlemaps

from util import GIS_DIR
from truck_routing import *

# Initialize Google Maps client with your API key
gmaps = googlemaps.Client(key='AIzaSyA-Ucw-UjCYf0ZyOMRhyoCAFZAGcJ2cUeQ')

# ------------------------------------------------ Load datafiles ---------------------------------------------------

# Rail links for BNSF, CN, CPKC, CSXT, NS, UP
RAIL_LINKS_DIR = os.path.join(GIS_DIR, 'rail_links')
railroads = ['BNSF', 'CN', 'CPKC', 'CSXT', 'NS', 'UP']
rail_links_gdfs = {}
for rr in railroads:
    shapefile_path = os.path.join(RAIL_LINKS_DIR, f'{rr}_base_links', f'{rr}_base_links.shp')
    rail_links_gdfs[rr] = gpd.read_file(shapefile_path)

# Rail yards and Intermodal transfer
rail_yards_gdf = gpd.read_file(os.path.join(GIS_DIR, 'Rail_Yards.shp'))
rail_toco_gdf = gpd.read_file(os.path.join(GIS_DIR, 'Intermodal_Freight_Facilities_Rail_TOFC_COFC.shp'))

# Reproject all GeoDataFrames to the same CRS
target_crs = 'EPSG:4326'
for key, gdf in rail_links_gdfs.items():
    rail_links_gdfs[key] = gdf.to_crs(target_crs)
rail_yards_gdf = rail_yards_gdf.to_crs(target_crs)
rail_toco_gdf = rail_toco_gdf.to_crs(target_crs)

# Replace 'KCS' and 'CPRS' with 'CPKC' in the 'RROWNER1' column of rail yards
rail_yards_gdf.loc[rail_yards_gdf['RROWNER1'].isin(["KCS", "CPRS"]), 'RROWNER1'] = "CPKC"

# Replace 'CSX' with 'CSXT' in the 'RAIL_CO' column of rail TOFC/COFC
rail_toco_gdf['RAIL_CO'] = rail_toco_gdf['RAIL_CO'].str.replace(r'\bCSX\b', 'CSXT', regex=True)
rail_toco_gdf['RAIL_CO'] = rail_toco_gdf['RAIL_CO'].str.replace(r'\b(KCS|CP)\b', 'CPKC', regex=True)

# ---------------------------------------------- Routing ------------------------------------------------------

# Step 1: Find the geometry of origin & destination from ZIP codes

# Step 2: Find the closest rail yards from each company (within 150 miles)
# Function to get a representative point from MultiLineString or LineString
def get_representative_point(geometry):
    """
    Convert MultiLineString or LineString to a representative Point (for yards)
    :param geometry:
    :return: Point geometry
    """
    if isinstance(geometry, Point):
        return geometry  # Already a Point
    elif isinstance(geometry, LineString):
        return Point(geometry.coords[0])  # First coordinate as point
    elif isinstance(geometry, MultiLineString):
        return Point(geometry.geoms[0].coords[0])  # First coordinate of first LineString
    else:
        raise ValueError("Unsupported geometry type")


def find_nearest_rail_yards(point_geom, rail_yards_gdf=rail_yards_gdf, max_distance=150):
    """
    Find the closest rail yard for each rail company within a given distance.

    :param point_geom: The Point geometry of the location.
    :param rail_yards_gdf: GeoDataFrame containing rail yards.
    :param max_distance: Maximum search distance in miles.
    :return: Dictionary mapping each rail company to its closest rail yard.
    """
    results = {}

    rail_yards_gdf = rail_yards_gdf.copy()

    # Convert all geometries to representative Points
    rail_yards_gdf["geometry"] = rail_yards_gdf["geometry"].apply(get_representative_point)

    for company in railroads:
        # Filter rail yards by company
        company_yards = rail_yards_gdf[rail_yards_gdf["RROWNER1"] == company].copy()
        if company_yards.empty:
            continue  # Skip if no yards for the company

        # Build KDTree for efficient nearest-neighbor search
        points = list(zip(company_yards.geometry.x, company_yards.geometry.y))
        tree = KDTree(points)

        # Find the nearest yard
        distance, idx = tree.query([point_geom.x, point_geom.y])

        # Retrieve the nearest yard data
        nearest_yard = company_yards.iloc[idx]
        yard_distance = geodesic((point_geom.y, point_geom.x), (nearest_yard.geometry.y, nearest_yard.geometry.x)).miles

        if yard_distance <= max_distance:
            results[company] = nearest_yard.to_dict()  # Store as dictionary for easy access

    return results


# Step 3: Find rail paths given origin, destination and links gdf
def find_rail_paths(orig_rail, dest_rail, links_gdf):
    """find shortest path in given links_gdf for given origin point and destination point"""

    # 1. Build a NetworkX graph from rail links
    G = nx.Graph()

    # Extract the start ('u') and end ('v') nodes from rail link geometries
    links_gdf = links_gdf.copy()
    links_gdf["u"] = links_gdf.geometry.apply(lambda geom: geom.coords[0] if geom else None)
    links_gdf["v"] = links_gdf.geometry.apply(lambda geom: geom.coords[-1] if geom else None)

    for _, row in links_gdf.iterrows():
        if row["u"] and row["v"]:  # Ensure valid coordinates
            G.add_edge(row["u"], row["v"], weight=row['MILES'])  # Default weight = 1 if 'MilesGeo' is missing

    # 2. Find shortest nodes in the G for origin and destination
    node_positions = list(G.nodes())
    tree = KDTree(node_positions)

    def find_nearest_node(point):
        """Finds the nearest existing node in the graph using KDTree."""
        if isinstance(point, Point):
            point = (point.x, point.y)  # Convert Shapely Point to tuple
        _, idx = tree.query(point)
        return node_positions[idx]  # Ensure node format matches G.nodes()

    # Find nearest nodes for origin and destination yards
    nearest_orig_node = find_nearest_node(orig_rail)
    nearest_dest_node = find_nearest_node(dest_rail)

    # 3. Shortest path
    p_nodes = nx.shortest_path(G, source=nearest_orig_node, target=nearest_dest_node, weight="weight")
    p_edges = [(p_nodes[i], p_nodes[i + 1]) for i in range(len(p_nodes) - 1)]
    shortest_path_links = links_gdf[
        links_gdf.apply(lambda row: (row['u'], row['v']) in p_edges or (row['v'], row['u']) in p_edges,
                        axis=1)]

    total_distance_km = shortest_path_links["KM"].sum()

    # Merge lines into a single geometry
    p_geom = linemerge(shortest_path_links.geometry.tolist())

    # Handle MultiLineString case
    route_geometry = []
    if isinstance(p_geom, LineString):
        route_geometry = [(coord[1], coord[0]) for coord in p_geom.coords]  # Swap (lon, lat)
    elif isinstance(p_geom, MultiLineString):
        for line in p_geom.geoms:
            route_geometry.extend([(coord[1], coord[0]) for coord in line.coords])

    return route_geometry, total_distance_km


# ------------------------------- Function: Get Complete Rail Routes ------------------------------- #
# Main structure function
def get_rail_routes(orig_geom, dest_geom):
    # 1. Find nearest yards for each company
    orig_yards = find_nearest_rail_yards(orig_geom)
    dest_yards = find_nearest_rail_yards(dest_geom)

    orig_yards_co = set(orig_yards.keys())
    dest_yards_co = set(dest_yards.keys())
    overlap_co = orig_yards_co.intersection(dest_yards_co)

    # 2. Check if nearest yard belong to the same company
    if overlap_co:
        # If belong to the same company, Find the shortest rail path and corresponding truck route
        min_distance = float("inf")  # Initialize with a large value
        shortest_route = None
        best_orig_yard = None
        best_dest_yard = None

        for co in overlap_co:
            orig_yard = orig_yards[co]  # Get the nearest origin yard for this company
            dest_yard = dest_yards[co]  # Get the nearest destination yard for this company

            orig_rail_ge = orig_yard.get('geometry')  # Geometry of the nearest origin yard
            dest_rail_ge = dest_yard.get('geometry')  # Geometry of the nearest destination yard

            # Get the relevant rail links for this company
            links_gdf = rail_links_gdfs[co]

            # Find the shortest rail path
            route, distance_km = find_rail_paths(orig_rail_ge, dest_rail_ge, links_gdf)

            if distance_km < min_distance:
                min_distance = distance_km
                shortest_route = {
                    "rail_co": co,
                    "distance_km": distance_km,
                    "route_geometry": route
                }
                best_orig_yard = orig_yard
                best_dest_yard = dest_yard

        orig_truck_route = get_truck_routes(orig_geom, best_orig_yard['geometry'])
        dest_truck_route = get_truck_routes(best_dest_yard['geometry'], dest_geom)

        return {
            "orig_yard": best_orig_yard,
            "dest_yard": best_dest_yard,
            "rail_route": shortest_route,
            "orig_truck_route": orig_truck_route,
            "dest_truck_route": dest_truck_route
        }

    else:
        # Find transfer routes
        print('no')

    # 3. Find intermodal transfer nodes if no yards belong to the same company

    # 4. Find intermodal rail routes given yard orig, transfer orig, transfer dest, dest yard

# ------------------------------------------- Performance metrics ----------------------------------------------------

charging_time_rail = 2.5  # hours/1000 km
refueling_time_rail = 0.1  # hours/1000 km for hydrogen
speed_rail = 30  # mile/hr


def get_dire_rail_metrics(rail_routes, energy_rail, energy_s_truck, commodity, ship_weight):
    # ----------- origin truck route -----------------
    orig_truck_route = rail_routes.get('orig_truck_route')
    first_route = orig_truck_route[0]

    # origin truck trip time
    orig_truck_time = first_route['time_hrs']
    orig_truck_dist = first_route['distance_km']

    if energy_s_truck == 'electricity':
        orig_truck_time += orig_truck_dist / 1000 * charging_time_truck

    if energy_s_truck in ['NG w/o CCS', 'NG w/ CCS', 'Electrolysis Solar', 'Electrolysis Nuclear']:
        orig_truck_time += orig_truck_dist / 1000 * refueling_time_truck

    # origin truck ghg, fuel price
    first_lat = first_route['lats'][0]
    first_lon = first_route['lons'][0]

    orig_truck_point = Point(first_lon, first_lat)

    # parameter
    ghg_tmile_orig_truck, price_tmile_orig_truck = get_metrics(orig_truck_point, energy_s_truck, 'short truck',
                                                               commodity)

    total_ghg_orig_truck = ghg_tmile_orig_truck * orig_truck_dist * 0.621371 * ship_weight  # g
    total_price_orig_truck = price_tmile_orig_truck * orig_truck_dist * 0.621371 * ship_weight  # $

    # ----------------- dest truck route -----------------
    dest_truck_route = rail_routes.get('dest_truck_route')
    dest_first_route = dest_truck_route[0]

    # destination truck trip time
    dest_truck_time = dest_first_route['time_hrs']
    dest_truck_dist = dest_first_route['distance_km']

    if energy_s_truck == 'electricity':
        dest_truck_time += dest_truck_dist / 1000 * charging_time_truck

    if energy_s_truck in ['NG w/o CCS', 'NG w/ CCS', 'Electrolysis Solar', 'Electrolysis Nuclear']:
        dest_truck_time += dest_truck_dist / 1000 * refueling_time_truck

    # destination truck ghg, fuel price
    dest_first_lat = dest_first_route['lats'][0]
    dest_first_lon = dest_first_route['lons'][0]

    dest_truck_point = Point(dest_first_lon, dest_first_lat)

    # parameter
    ghg_tmile_dest_truck, price_tmile_dest_truck = get_metrics(dest_truck_point, energy_s_truck, 'short truck',
                                                               commodity)

    total_ghg_dest_truck = ghg_tmile_dest_truck * dest_truck_dist * 0.621371 * ship_weight  # g
    total_price_dest_truck = price_tmile_dest_truck * dest_truck_dist * 0.621371 * ship_weight  # $

    # ------------------- rail route ------------------------
    dire_rail_route = rail_routes.get('rail_route')
    rail_dist = dire_rail_route['distance_km']
    rail_time = rail_dist / speed_rail * 0.621371

    if energy_rail == 'electricity':
        rail_time += rail_dist / 1000 * charging_time_rail

    if energy_rail in ['NG w/o CCS', 'NG w/ CCS', 'Electrolysis Solar', 'Electrolysis Nuclear']:
        rail_time += rail_dist / 1000 * refueling_time_rail

    #
    rail_lat, rail_lon = rail_routes.get('rail_route')['route_geometry'][0]
    rail_point = Point(rail_lon, rail_lat)

    ghg_tmile_rail, price_tmile_rail = get_metrics(rail_point, energy_rail, 'rail', commodity)

    total_ghg_rail = ghg_tmile_rail * rail_dist * 0.621371* ship_weight  # g
    total_price_rail = price_tmile_rail * rail_dist * 0.621371 * ship_weight  # $

    return {
        'orig truck time': orig_truck_time,
        'orig truck ghg': total_ghg_orig_truck,
        'orig truck price': total_price_orig_truck,
        'dest truck time': dest_truck_time,
        'dest truck ghg': total_ghg_dest_truck,
        'dest truck price': total_price_dest_truck,
        'rail time': rail_time,
        'rail ghg': total_ghg_rail,
        'rail price': total_price_rail,
    }


# ------------------------------------------- Plotting ----------------------------------------------------
# Plot direct rail route on the given figure for given rail route
def plot_dire_rail_routes(updated_fig, rail_routes):
    # Origin truck routes
    orig_truck_route = rail_routes.get('orig_truck_route')
    updated_fig = plot_truck_routes(updated_fig, orig_truck_route)

    # Destination truck routes
    dest_truck_route = rail_routes.get('dest_truck_route')
    updated_fig = plot_truck_routes(updated_fig, dest_truck_route)

    # Rail routes
    rail_route = rail_routes.get('rail_route')
    orig_yard = rail_routes.get('orig_yard')
    dest_yard = rail_routes.get('dest_yard')

    #
    rail_geometry = rail_route.get('route_geometry')
    rail_co = rail_route.get('rail_co')
    rail_distance_km = rail_route.get('distance_km')

    lats, lons = zip(*rail_geometry)

    hover_text = f"""
        Rail Company: {rail_co} <br>
        Origin Rail Yard: {orig_yard.get('YARDNAME')}<br>
        Destination Rail Yard: {dest_yard.get('YARDNAME')}<br>
        Distance: {rail_distance_km:.2f} km
            """
    updated_fig.add_trace(
        go.Scattermapbox(
            mode="lines",
            lat=lats,
            lon=lons,
            line=dict(width=2, color="orange"),
            hoverinfo="text",  # Show only custom hover text
            hovertext=hover_text,  # Define the hover text
            showlegend=False  # Do not show the line label in the legend
        )
    )
    return updated_fig


def plot_dire_rail_ghg(ghg_bar_chart, rail_metrics):
    # Add Truck GHG Emissions
    ghg_bar_chart.add_trace(
        go.Bar(
            name="Origin Drayage Truck",
            x=["Rail GHG"],
            y=[rail_metrics.get('orig truck ghg') / 1e3],  # Convert to kg
            text=[f"{rail_metrics.get('orig truck ghg') / 1e3:.2f} kg"],
            textposition="auto",
            marker=dict(color="gray")  # Change to desired color
        )
    )

    ghg_bar_chart.add_trace(
        go.Bar(
            name="Destination Drayage Truck",
            x=["Rail GHG"],
            y=[rail_metrics.get('dest truck ghg') / 1e3],  # Convert to kg
            text=[f"{rail_metrics.get('dest truck ghg') / 1e3:.2f} kg"],
            textposition="auto",
            marker=dict(color="gray")  # Change to desired color
        )
    )

    # Add Rail GHG Emissions (Stacked on Truck)
    ghg_bar_chart.add_trace(
        go.Bar(
            name="Rail",
            x=["Rail GHG"],
            y=[rail_metrics.get('rail ghg') / 1e3],  # Convert to kg
            text=[f"{rail_metrics.get('rail ghg') / 1e3:.2f} kg"],
            textposition="auto",
            marker=dict(color="orange")  # Change to desired color
        )
    )

    # Update layout for stacked bar chart
    ghg_bar_chart.update_layout(
        title="Total GHG Emissions (kg)",
        xaxis_title="Metrics",
        yaxis_title="kg",
        barmode="stack",  # Stack bars for emissions
        showlegend=False
    )

    return ghg_bar_chart


def plot_dire_rail_time(time_bar_chart, rail_metrics):
    time_bar_chart.add_trace(
        go.Bar(
            name="Origin Drayage Truck",
            x=["Rail Time"],
            y=[rail_metrics.get('orig truck time')],
            text=[f"{rail_metrics.get('orig truck time'):.2f} hour"],
            textposition="auto",
            marker=dict(color="gray")  # Change to desired color
        )
    )

    time_bar_chart.add_trace(
        go.Bar(
            name="Destination Drayage Truck",
            x=["Rail Time"],
            y=[rail_metrics.get('dest truck time')],
            text=[f"{rail_metrics.get('dest truck time'):.2f} hour"],
            textposition="auto",
            marker=dict(color="gray")  # Change to desired color
        )
    )

    # Add Rail GHG Emissions (Stacked on Truck)
    time_bar_chart.add_trace(
        go.Bar(
            name="Rail",
            x=["Rail Time"],
            y=[rail_metrics.get('rail time')],
            text=[f"{rail_metrics.get('rail time'):.2f} hour"],
            textposition="auto",
            marker=dict(color="orange")  # Change to desired color
        )
    )

    # Update layout for stacked bar chart
    time_bar_chart.update_layout(
        title="Total Trip time (hour)",
        xaxis_title="Metrics",
        yaxis_title="hour",
        barmode="stack",  # Stack bars for emissions
        showlegend=False
    )

    return time_bar_chart


def plot_dire_rail_cost(fuel_cost_bar_chart, rail_metrics):
    fuel_cost_bar_chart.add_trace(
        go.Bar(
            name="Origin Drayage Truck",
            x=["Rail Fuel Cost"],
            y=[rail_metrics.get('orig truck price')],
            text=[f"{rail_metrics.get('orig truck price'):.2f} $"],
            textposition="auto",
            marker=dict(color="gray")  # Change to desired color
        )
    )

    fuel_cost_bar_chart.add_trace(
        go.Bar(
            name="Destination Drayage Truck",
            x=["Rail Fuel Cost"],
            y=[rail_metrics.get('dest truck price')],
            text=[f"{rail_metrics.get('dest truck price'):.2f} $"],
            textposition="auto",
            marker=dict(color="gray")  # Change to desired color
        )
    )

    # Add Rail GHG Emissions (Stacked on Truck)
    fuel_cost_bar_chart.add_trace(
        go.Bar(
            name="Rail",
            x=["Rail Fuel Cost"],
            y=[rail_metrics.get('rail price')],
            text=[f"{rail_metrics.get('rail price'):.2f} $"],
            textposition="auto",
            marker=dict(color="orange")  # Change to desired color
        )
    )

    # Update layout for stacked bar chart
    fuel_cost_bar_chart.update_layout(
        title="Total Fuel Cost ($)",
        xaxis_title="Metrics",
        yaxis_title="$",
        barmode="stack",  # Stack bars for emissions
        showlegend=False
    )

    return fuel_cost_bar_chart