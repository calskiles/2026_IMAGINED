"""
Given the Origin and Destination zip code
Get truck routes (highway or road name, distance (meters), route polyline)
"""

import polyline
import plotly.graph_objects as go
import googlemaps

from performance_value import *

# Initialize Google Maps client with API key
gmaps = googlemaps.Client(key='AIzaSyA-Ucw-UjCYf0ZyOMRhyoCAFZAGcJ2cUeQ')

charging_time_truck = 3   # hours/1000 km
refueling_time_truck = 0.1   # hours/1000 km for hydrogen


# Get coordinates given location
def geocode_location(location):
    geocode_result = gmaps.geocode(location)
    if geocode_result:
        lat = geocode_result[0]['geometry']['location']['lat']
        lon = geocode_result[0]['geometry']['location']['lng']
        return Point(lon, lat)
    return None

# ------------------------------------------- Truck routing ----------------------------------------------------

# Get truck routes info given origin and destination geometry
def get_truck_routes(orig_geom, dest_geom):
    """
    Fetch truck routes and performance metrics between two ZIP codes
    :return: A list of dictionaries, each containing route summary, distance (in meters), and polyline
    """
    orig_lat, orig_lon = orig_geom.y, orig_geom.x
    dest_lat, dest_lon = dest_geom.y, dest_geom.x

    directions = gmaps.directions(
        origin=(orig_lat, orig_lon),
        destination=(dest_lat, dest_lon),
        mode='driving',
        alternatives=False,
    )

    # Process the response and extract route information
    routes = []
    for route in directions:
        # Extract route summary
        summary = route.get('summary', 'No summary available')

        # Extract distance
        legs = route.get('legs', [{}])
        distance_meter = legs[0].get('distance', {}).get('value',None)  # in meters
        distance_km = distance_meter / 1000

        # Extract the travel time
        travel_time_seconds = legs[0].get('duration', {}).get('value', None)
        travel_time_hours = travel_time_seconds / 3600 if travel_time_seconds else None

        # Extract polyline and decode it
        route_polyline = route['overview_polyline']['points'] if 'overview_polyline' in route else None
        decoded_points = polyline.decode(route_polyline) if route_polyline else []
        lats, lons = zip(*decoded_points) if decoded_points else ([], [])

        # Append route details
        routes.append({
            "summary": summary,
            "distance_km": distance_km,
            "time_hrs": travel_time_hours,
            "lats": lats,
            "lons": lons
        })

    return routes


# # Example usage
# print(get_truck_routes_and_metrics('60201', '60043', 'diesel', mode="long truck"))

# ------------------------------------------- Performance ----------------------------------------------------
def get_truck_metrics(truck_route, orig_geom, energy, mode, commodity, ship_weight):
    # trip time
    trip_time = truck_route.get('time_hrs')
    trip_distance = truck_route.get('distance_km')
    if energy == 'electricity':
        trip_time += trip_distance / 1000 * charging_time_truck

    if energy in ['NG w/o CCS', 'NG w/ CCS', 'Electrolysis Solar', 'Electrolysis Nuclear']:
        trip_time += trip_distance / 1000 * refueling_time_truck

    # ghg emission, fuel price
    ghg_tmile, price_tmile = get_metrics(orig_geom, energy, mode, commodity)

    total_ghg = ghg_tmile * trip_distance * 0.621371 * ship_weight  # g
    total_price = price_tmile * trip_distance * 0.621371 * ship_weight  # $

    return trip_time, total_ghg, total_price


# ------------------------------------------- Plotting ----------------------------------------------------
# Plot truck routes on the given figure for given truck routes
def plot_truck_routes(updated_fig, routes):
    for i, route in enumerate(routes):
        lats, lons = route['lats'], route['lons']

        hover_text = f"""
        Highway: {route.get('summary', 'N/A')}<br>
        Distance: {route.get('distance_km'):.2f} km
            """
        updated_fig.add_trace(
            go.Scattermapbox(
                mode="lines",
                lat=lats,
                lon=lons,
                line=dict(width=2, color="black"),
                hoverinfo="text",  # Show only custom hover text
                hovertext=hover_text,  # Define the hover text
                hoverlabel=dict(
                    bgcolor="white",  # Background color
                    font=dict(
                        color="black"  # Font color
                    )
                ),
                showlegend=False  # Do not show the line label in the legend
            )
        )
        return updated_fig

