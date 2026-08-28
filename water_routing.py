"""
Given the Origin and Destination zip code
Get origin short haul truck routes (highway or road name, distance (meters), route polyline)
port or ro-ro points, waterway routes (distance, routes)
and destination short haul truck routes (highway or road name, distance (meters), route polyline)
"""

import numpy as np
import geopandas as gpd

import networkx as nx
import momepy

from shapely.ops import linemerge
from shapely.geometry import Point, LineString, MultiLineString
from scipy.spatial import KDTree

import googlemaps
from geopy.distance import geodesic
import plotly.graph_objects as go

from util import GIS_DIR
from truck_routing import *
from performance_value import *

# Initialize Google Maps client with API key
gmaps = googlemaps.Client(key='AIzaSyA-Ucw-UjCYf0ZyOMRhyoCAFZAGcJ2cUeQ')

# ------------------------------------------------ Load datafiles ---------------------------------------------------

# Load data files
waterways_links_gdf = gpd.read_file(os.path.join(GIS_DIR, 'connected_waterways_links.shp'))
port_nodes_gdf = gpd.read_file(os.path.join(GIS_DIR, 'Draft_Designated_Marine_Ports.shp'))
marine_roro_nodes_gdf = gpd.read_file(os.path.join(GIS_DIR, 'Intermodal_Freight_Facilities_Marine_Roll_on_Roll_off.shp'))

port_nodes_gdf['PORT'] = port_nodes_gdf['PORT_NAME']

# Same crs
target_crs = "EPSG:4326"
waterways_links_gdf = waterways_links_gdf.to_crs(target_crs)
port_nodes_gdf = port_nodes_gdf.to_crs(target_crs)
marine_roro_nodes_gdf = marine_roro_nodes_gdf.to_crs(target_crs)
w_nodes_gdf = gpd.GeoDataFrame(pd.concat([port_nodes_gdf, marine_roro_nodes_gdf], ignore_index=True))


# ------------------------------------------------ Routing ---------------------------------------------------

def find_closest_port_truck_route(node_geom, nodes_gdf):
    """
    Finds the closest port node and calculates the route from the ZIP code to that node.

    :param zip_code: ZIP code as a string.
    :param nodes_gdf: GeoDataFrame containing port or roro nodes with 'geometry' column.
    :return: Closest port or roro node ID, distance (km), and the route (lat, lng) as a list of coordinates.
    """
    nodes_gdf = nodes_gdf.to_crs("EPSG:4326")

    # Step 1: Geocode the ZIP code to get its coordinates
    origin_coords = (node_geom.y, node_geom.x)

    # Step 2: Calculate distances in km
    nodes_gdf['distance_km'] = nodes_gdf['geometry'].apply(
        lambda geom: geodesic((geom.y, geom.x), origin_coords).kilometers
    )

    # Step 3: Find the closest rail node
    closest_node = nodes_gdf.loc[nodes_gdf['distance_km'].idxmin()]
    closest_node_geometry = closest_node['geometry']

    # Step 4: Use Google Maps API to calculate the route
    directions = gmaps.directions(
        origin={"lat": node_geom.y, "lng": node_geom.x},
        destination={"lat": closest_node_geometry.y, "lng": closest_node_geometry.x},
        mode="driving",
        alternatives=False
    )
    route_summary = directions[0].get('summary', 'No summary available')

    # Extract the route geometry
    route_geometry = [(node_geom.y, node_geom.x)]  # Include the origin point
    route_geometry += [
        (step['start_location']['lat'], step['start_location']['lng'])
        for step in directions[0]['legs'][0]['steps']
    ]
    route_geometry.append((closest_node_geometry.y, closest_node_geometry.x))

    return {
        "port_name": closest_node['PORT'],
        "route_summary": route_summary,
        "distance_km": closest_node['distance_km'],
        "route_geometry": route_geometry
    }


# # Example use
# print(find_closest_port_truck_route('60201', w_nodes_gdf))


def find_water_route(orig_port_name, dest_port_name, links_gdf, nodes_gdf):
    """
    find waterway route between two ports and return the geometry
    :param nodes_gdf: all nodes (port, marine roro) gdf
    :param orig_port_name: origin port name
    :param dest_port_name: destination port name
    :param links_gdf: waterway links gdf
    :return: Geometry of the shortest path
    """

    nodes_gdf = nodes_gdf.to_crs("EPSG:5070")
    links_gdf = links_gdf.to_crs("EPSG:5070")

    # Origin and Destination Points
    orig_port_geometry = nodes_gdf[nodes_gdf['PORT'] == orig_port_name].geometry.iloc[0]
    dest_port_geometry = nodes_gdf[nodes_gdf['PORT'] == dest_port_name].geometry.iloc[0]

    # Create the network
    G = momepy.gdf_to_nx(links_gdf, approach="primal", length="MilesGeo")

    # Find the Nearest Nodes in the Graph for Port & RoRo Nodes
    node_positions = np.array(list(G.nodes))  # Convert graph nodes to NumPy array
    kdtree = KDTree(node_positions)  # Build KDTree

    def find_nearest_node(point, kdtree, node_positions):
        """
        Finds the nearest existing node in the graph using KDTree.
        """
        dist, idx = kdtree.query([point.x, point.y])  # Find nearest node
        return tuple(node_positions[idx])  # Return as tuple for NetworkX

    nearest_orig_node = find_nearest_node(orig_port_geometry, kdtree, node_positions)
    nearest_dest_node = find_nearest_node(dest_port_geometry, kdtree, node_positions)

    p_nodes = nx.shortest_path(G, source=nearest_orig_node, target=nearest_dest_node, weight="MilesGeo")
    p_edges = [(p_nodes[i], p_nodes[i + 1]) for i in range(len(p_nodes) - 1)]

    # Extract start and end nodes from geometry
    links_gdf['u'] = links_gdf['geometry'].apply(
        lambda geom: geom.coords[0] if isinstance(geom, LineString) else None)
    links_gdf['v'] = links_gdf['geometry'].apply(
        lambda geom: geom.coords[-1] if isinstance(geom, LineString) else None)

    shortest_path_links = links_gdf[
        links_gdf.apply(lambda row: (row['u'], row['v']) in p_edges or (row['v'], row['u']) in p_edges,
                                  axis=1)]

    p_geom = linemerge(shortest_path_links.geometry.tolist())
    p_gdf = gpd.GeoDataFrame(geometry=[p_geom], crs=links_gdf.crs)
    p_length_meters = p_gdf.geometry.iloc[0].length
    p_gdf = p_gdf.to_crs("EPSG:4326")

    # Extract the transformed geometry
    shortest_path_geom = p_gdf.geometry.iloc[0]
    # Get the transformed coordinates
    route_geometry = []
    route_geometry = [(coord[1], coord[0]) for coord in shortest_path_geom.coords]

    return {
        "distance_km": p_length_meters / 1000,
        "route_geometry": route_geometry
    }


# # Example use
# orig_port_name = 'Illinois International Port, IL'
# dest_port_name = 'Memphis-Shelby County Port, TN'
# print(find_water_route(orig_port_name, dest_port_name, waterways_links_gdf, w_nodes_gdf))


def get_water_routes(orig_geom, dest_geom, nodes_gdf=w_nodes_gdf, links_gdf=waterways_links_gdf):
    """
    find the combination of truck and water routes between origin and destination zips
    :param orig_geom: origin zip code
    :param dest_geom: destination zip code
    :param nodes_gdf: all ports and marine roro nodes
    :param links_gdf: waterway links
    :return: A dictionary with the closest port nodes, route geometry, and total distances.
    """

    # Step 1: Find the closest port node to origin ZIP and destination zip
    orig_port_truck_route = find_closest_port_truck_route(orig_geom, nodes_gdf)
    dest_port_truck_route = find_closest_port_truck_route(dest_geom, nodes_gdf)

    # Step 2: Find the waterway routes between origin port and destination port
    water_route = find_water_route(orig_port_truck_route.get("port_name"), dest_port_truck_route.get("port_name"),
                                   links_gdf, nodes_gdf)

    # Step 3: Output results
    return {
        "truck_orig_distance_km": orig_port_truck_route.get("distance_km"),
        "truck_dest_distance_km": dest_port_truck_route.get("distance_km"),
        "water_distance_km": water_route.get("distance_km"),

        "port_orig_name": orig_port_truck_route.get("port_name"),
        "port_dest_name": dest_port_truck_route.get("port_name"),

        "truck_orig_route": orig_port_truck_route.get("route_geometry"),
        "truck_dest_route": dest_port_truck_route.get("route_geometry"),
        "water_route": water_route.get("route_geometry"),

        "truck_orig_highway": orig_port_truck_route.get("route_summary"),
        "truck_dest_highway": dest_port_truck_route.get("route_summary"),
        }
#
# orig_geom = geocode_zip('60201')
# dest_geom = geocode_zip('37501')
# print(find_truck_water_routes(orig_geom, dest_geom))

# ------------------------------------------- Performance ----------------------------------------------------
charging_time_water = 2.5  # hours/1000 km
refueling_time_water = 0.1  # hours/1000 km for hydrogen
speed_water = 15  # mile/hour


def get_water_metrics(water_routes, energy_water, energy_s_truck, commodity, ship_weight):
    # ----------- origin truck route -----------------
    orig_truck_dist = water_routes.get('truck_orig_distance_km')

    # origin truck trip time
    orig_truck_time = orig_truck_dist / 50

    if energy_s_truck == 'electricity':
        orig_truck_time += orig_truck_dist / 1000 * charging_time_truck

    if energy_s_truck in ['NG w/o CCS', 'NG w/ CCS', 'Electrolysis Solar', 'Electrolysis Nuclear']:
        orig_truck_time += orig_truck_dist / 1000 * refueling_time_truck

    # origin truck ghg, fuel price
    orig_truck_route = water_routes.get('truck_orig_route')
    first_lat = orig_truck_route[0][0]
    first_lon = orig_truck_route[0][1]

    orig_truck_point = Point(first_lon, first_lat)

    # parameter
    ghg_tmile_orig_truck, price_tmile_orig_truck = get_metrics(orig_truck_point, energy_s_truck, 'short truck',
                                                               commodity)

    total_ghg_orig_truck = ghg_tmile_orig_truck * orig_truck_dist * 0.621371 * ship_weight  # g
    total_price_orig_truck = price_tmile_orig_truck * orig_truck_dist * 0.621371 * ship_weight  # $

    # ----------------- dest truck route -----------------
    dest_truck_dist = water_routes.get('truck_dest_distance_km')

    # origin truck trip time
    dest_truck_time = dest_truck_dist / 50

    if energy_s_truck == 'electricity':
        dest_truck_time += dest_truck_dist / 1000 * charging_time_truck

    if energy_s_truck in ['NG w/o CCS', 'NG w/ CCS', 'Electrolysis Solar', 'Electrolysis Nuclear']:
        dest_truck_time += dest_truck_dist / 1000 * refueling_time_truck

    # destination truck ghg, fuel price
    dest_truck_route = water_routes.get('truck_dest_route')
    dest_first_lat = dest_truck_route[0][0]
    dest_first_lon = dest_truck_route[0][1]

    dest_truck_point = Point(dest_first_lon, dest_first_lat)

    # parameter
    ghg_tmile_dest_truck, price_tmile_dest_truck = get_metrics(dest_truck_point, energy_s_truck, 'short truck',
                                                               commodity)

    total_ghg_dest_truck = ghg_tmile_dest_truck * dest_truck_dist * 0.621371 * ship_weight  # g
    total_price_dest_truck = price_tmile_dest_truck * dest_truck_dist * 0.621371 * ship_weight  # $

    # ------------------- water route ------------------------
    dire_water_route = water_routes.get('water_route')
    water_dist = water_routes.get("water_distance_km")
    water_time = water_dist / speed_water * 0.621371

    if energy_water == 'electricity':
        water_time += water_dist / 1000 * charging_time_water

    if energy_water in ['NG w/o CCS', 'NG w/ CCS', 'Electrolysis Solar', 'Electrolysis Nuclear']:
        water_time += water_dist / 1000 * refueling_time_water

    #
    water_lat, water_lon = dire_water_route[0]
    water_point = Point(water_lon, water_lat)

    ghg_tmile_water, price_tmile_water = get_metrics(water_point, energy_water, 'water', commodity)

    total_ghg_water = ghg_tmile_water * water_dist * 0.621371* ship_weight  # g
    total_price_water = price_tmile_water * water_dist * 0.621371 * ship_weight  # $

    return {
        'orig truck time': orig_truck_time,
        'orig truck ghg': total_ghg_orig_truck,
        'orig truck price': total_price_orig_truck,
        'dest truck time': dest_truck_time,
        'dest truck ghg': total_ghg_dest_truck,
        'dest truck price': total_price_dest_truck,
        'water time': water_time,
        'water ghg': total_ghg_water,
        'water price': total_price_water,
    }

# ------------------------------------------- Plotting ----------------------------------------------------

def plot_truck_water_route(updated_fig, routes):
    """
    Add short haul truck routes in the origin and destination, and rail routes to the updated_fig
    :param updated_fig:
    :param routes:
    :return:
    """

    # Truck origin route
    truck_origin_route = routes.get("truck_orig_route", [])
    truck_origin_hover_text = f"""
        Highway: {routes.get('truck_orig_highway', 'N/A')}<br>
        Distance: {routes.get('truck_orig_distance_km'):.2f} km
        """
    if truck_origin_route:
        lats, lons = zip(*truck_origin_route)
        updated_fig.add_trace(
            go.Scattermapbox(
                mode="lines",
                lat=lats,
                lon=lons,
                line=dict(width=2, color="black"),
                hoverinfo="text",  # Show only custom hover text
                hovertext=truck_origin_hover_text,
                showlegend=False
            )
        )

    # Truck destination route
    truck_destination_route = routes.get("truck_dest_route", [])
    truck_destination_hover_text = f"""
        Highway: {routes.get('truck_dest_highway', 'N/A')}<br>
        Distance: {routes.get('truck_dest_distance_km'):.2f} km
        """
    if truck_destination_route:
        lats, lons = zip(*truck_destination_route)
        updated_fig.add_trace(
            go.Scattermapbox(
                mode="lines",
                lat=lats,
                lon=lons,
                line=dict(width=2, color="green"),
                hoverinfo="text",  # Show only custom hover text
                hovertext=truck_destination_hover_text,
                showlegend=False
            )
        )

    # Water route
    water_route_geometry = routes.get("water_route", [])
    water_hover_text = f"""
        Origin Port: {routes.get('port_orig_name')}<br>
        Destination Port: {routes.get('port_dest_name')}<br>
        Distance: {routes.get('water_distance_km'):.2f} km
        """
    if water_route_geometry:
        lats, lons = zip(*water_route_geometry)
        updated_fig.add_trace(
            go.Scattermapbox(
                mode="lines",
                lat=lats,
                lon=lons,
                line=dict(width=2, color="blue"),
                hoverinfo="text",  # Show only custom hover text
                hovertext=water_hover_text,
                showlegend=False
            )
        )

    return updated_fig


def plot_dire_water_ghg(ghg_bar_chart, water_metrics):
    # Add Truck GHG Emissions
    ghg_bar_chart.add_trace(
        go.Bar(
            name="Origin Drayage Truck",
            x=["Water GHG"],
            y=[water_metrics.get('orig truck ghg') / 1e3],  # Convert to kg
            text=[f"{water_metrics.get('orig truck ghg') / 1e3:.2f} kg"],
            textposition="auto",
            marker=dict(color="gray")  # Change to desired color
        )
    )

    ghg_bar_chart.add_trace(
        go.Bar(
            name="Destination Drayage Truck",
            x=["Water GHG"],
            y=[water_metrics.get('dest truck ghg') / 1e3],  # Convert to kg
            text=[f"{water_metrics.get('dest truck ghg') / 1e3:.2f} kg"],
            textposition="auto",
            marker=dict(color="gray")  # Change to desired color
        )
    )

    # Add water GHG Emissions (Stacked on Truck)
    ghg_bar_chart.add_trace(
        go.Bar(
            name="Water",
            x=["Water GHG"],
            y=[water_metrics.get('water ghg') / 1e3],  # Convert to kg
            text=[f"{water_metrics.get('water ghg') / 1e3:.2f} kg"],
            textposition="auto",
            marker=dict(color="blue")  # Change to desired color
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


def plot_dire_water_time(time_bar_chart, water_metrics):
    time_bar_chart.add_trace(
        go.Bar(
            name="Origin Drayage Truck",
            x=["Water Time"],
            y=[water_metrics.get('orig truck time')],
            text=[f"{water_metrics.get('orig truck time'):.2f} hour"],
            textposition="auto",
            marker=dict(color="gray")  # Change to desired color
        )
    )

    time_bar_chart.add_trace(
        go.Bar(
            name="Destination Drayage Truck",
            x=["Water Time"],
            y=[water_metrics.get('dest truck time')],
            text=[f"{water_metrics.get('dest truck time'):.2f} hour"],
            textposition="auto",
            marker=dict(color="gray")  # Change to desired color
        )
    )

    # Add Rail GHG Emissions (Stacked on Truck)
    time_bar_chart.add_trace(
        go.Bar(
            name="Water",
            x=["Water Time"],
            y=[water_metrics.get('water time')],
            text=[f"{water_metrics.get('water time'):.2f} hour"],
            textposition="auto",
            marker=dict(color="blue")  # Change to desired color
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


def plot_dire_water_cost(fuel_cost_bar_chart, water_metrics):
    fuel_cost_bar_chart.add_trace(
        go.Bar(
            name="Origin Drayage Truck",
            x=["Water Fuel Cost"],
            y=[water_metrics.get('orig truck price')],
            text=[f"{water_metrics.get('orig truck price'):.2f} $"],
            textposition="auto",
            marker=dict(color="gray")  # Change to desired color
        )
    )

    fuel_cost_bar_chart.add_trace(
        go.Bar(
            name="Destination Drayage Truck",
            x=["Water Fuel Cost"],
            y=[water_metrics.get('dest truck price')],
            text=[f"{water_metrics.get('dest truck price'):.2f} $"],
            textposition="auto",
            marker=dict(color="gray")  # Change to desired color
        )
    )

    # Add Rail GHG Emissions (Stacked on Truck)
    fuel_cost_bar_chart.add_trace(
        go.Bar(
            name="Water",
            x=["Water Fuel Cost"],
            y=[water_metrics.get('water price')],
            text=[f"{water_metrics.get('water price'):.2f} $"],
            textposition="auto",
            marker=dict(color="blue")  # Change to desired color
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