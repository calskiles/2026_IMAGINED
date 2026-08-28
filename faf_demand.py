"""
Load and preprocess the demand data from the FAF file
Create mode, commodity, faf zones mapping from FAF
Plot the faf zones and mode, commodity bar charts
"""

import os
import pandas as pd
import geopandas as gpd
import plotly.express as px
import plotly.graph_objects as go

from util import DEMAND_DIR
from util import GIS_DIR


# Load FAF data
def load_demand_data(year):
    demand_data_file = os.path.join(DEMAND_DIR, 'FAF5.6.1_HiLoForecasts.csv')
    demand_data = pd.read_csv(demand_data_file)

    # Select the desired columns
    demand_data = demand_data[['fr_orig', 'dms_orig', 'dms_dest', 'fr_dest', 'fr_inmode', 'dms_mode',
                               'fr_outmode', 'sctg2', f'tons_{year}', f'value_{year}', f'tmiles_{year}']]

    demand_data['dms_orig'] = demand_data['dms_orig'].astype(str).str.zfill(3)
    demand_data['dms_dest'] = demand_data['dms_dest'].astype(str).str.zfill(3)
    demand_data = demand_data[demand_data['dms_orig'] != demand_data['dms_dest']]

    demand_data = demand_data.rename(columns={f'tons_{year}': 'tons'})
    demand_data = demand_data.rename(columns={f'value_{year}': 'value'})
    demand_data = demand_data.rename(columns={f'tmiles_{year}': 'tmiles'})
    return demand_data


# Get the data with specified origin, destination, mode, and commodity
def get_filtered_data(year=2035, dms_origin=None, dms_destination=None, mode=None, commodity=None):
    """
    Filter the demand data based on the provided parameters.

    Parameters:
        year: selected year
        dms_origin: The domestic origin (dms_orig) code. "all" or None for no filter.
        dms_destination: The domestic destination (dms_dest) code. "all" or None for no filter.
        mode: The transportation mode (dms_mode). "all" or None for no filter.
        commodity: The SCTG2 commodity code. "all" or None for no filter.

    Returns:
        pd.DataFrame: The filtered rows.
    """
    # Start with the full dataset
    filtered_data = load_demand_data(year)

    # Apply filters if the respective parameters are provided
    if dms_origin and dms_origin != "all":
        filtered_data = filtered_data[filtered_data['dms_orig'] == dms_origin]

    if dms_destination and dms_destination != "all":
        filtered_data = filtered_data[filtered_data['dms_dest'] == dms_destination]

    if mode and mode != "all":
        filtered_data = filtered_data[filtered_data['dms_mode'] == mode]

    if commodity and commodity != "all":
        filtered_data = filtered_data[filtered_data['sctg2'] == commodity]

    return filtered_data


# # Example usage
# data = load_demand_data()
# result = get_filtered_data(data, 'all', 'all', 1, 1)
# print(f"{result}")


# Create mapping
def get_mappings():
    """
    Reads mappings from the Excel file and returns separate dictionaries for commodities, FAF zones, and modes.

    :return: A dictionary containing:
        - "commodity": Mapping of numeric labels to descriptions for commodities.
        - "faf_zone": Mapping of FAF zone numeric labels to descriptions.
        - "mode": Mapping of mode numeric labels to descriptions.
    """
    # Define the path to the mapping file
    mapping_file = os.path.join(DEMAND_DIR, 'FAF5_metadata.xlsx')

    # Initialize the mappings dictionary
    mappings = {}

    # Commodity Mapping (SCTG2)
    commodity_mapping_data = pd.read_excel(mapping_file, sheet_name='Commodity (SCTG2)')
    mappings["commodity"] = dict(zip(commodity_mapping_data["Numeric Label"], commodity_mapping_data["Description"]))

    # FAF Zone Mapping (Domestic)
    faf_zone_mapping_data = pd.read_excel(mapping_file, sheet_name='FAF Zone (Domestic)')
    mappings["faf_zone"] = dict(zip(faf_zone_mapping_data["Numeric Label"], faf_zone_mapping_data["Long Description"]))

    # Mode Mapping
    mode_mapping_data = pd.read_excel(mapping_file, sheet_name='Mode')
    mappings["mode"] = dict(zip(mode_mapping_data["Numeric Label"], mode_mapping_data["Description"]))

    return mappings


# # Example usage
# mappings = get_mappings()
#
# # Print mappings for verification
# print("Commodity Mapping:")
# print(mappings["commodity"])
#
# print("\nFAF Zone Mapping:")
# print(mappings["faf_zone"])
#
# print("\nMode Mapping:")
# print(mappings["mode"])


def plot_faf_shapefile():
    """
    Plot the FAF shapefile using geopandas and Plotly
    """

    faf_shapefile_path = os.path.join(GIS_DIR, "Freight_Analysis_Framework_Regions_faf5_regions_Apri.shp")
    faf_regions = gpd.read_file(faf_shapefile_path)  # Load the shape file
    faf_regions = faf_regions.to_crs("EPSG:4326")

    fig = px.choropleth_mapbox(
        faf_regions,
        geojson=faf_regions.geometry,  # Use geometry from the GeoDataFrame
        locations=faf_regions.index,  # Use the index of the GeoDataFrame for locations
        color_discrete_sequence=["gainsboro"],  # Set US map regions to grey
        mapbox_style="white-bg",  # Set background to white
        zoom=3,  # Set zoom level
        center={"lat": 37.8, "lon": -96},  # Center on the US
        hover_name='cfs17_name',
        hover_data=None
    )

    # fig.show()
    return fig


# plot_faf_shapefile()


def update_faf_map(data, in_flow, out_flow):
    # Load FAF regions shapefile
    faf_shapefile_path = os.path.join(GIS_DIR, "Freight_Analysis_Framework_Regions_faf5_regions_Apri.shp")
    faf_regions = gpd.read_file(faf_shapefile_path)  # Load the shapefile
    faf_regions = faf_regions.to_crs("EPSG:4326")  # Convert to WGS84 for mapping

    filtered_data = data

    inflow_domestic = (
        filtered_data
        .groupby('dms_dest')['tons']
        .sum()
        .reset_index()
        .rename(columns={'dms_dest': 'faf_zone', 'tons': 'Inflow_Domestic'})
    )

    outflow_domestic = (
        filtered_data
        .groupby('dms_orig')['tons']
        .sum()
        .reset_index()
        .rename(columns={'dms_orig': 'faf_zone', 'tons': 'Outflow_Domestic'})
    )

    faf_regions = faf_regions.merge(inflow_domestic, on='faf_zone', how='left')
    faf_regions = faf_regions.merge(outflow_domestic, on='faf_zone', how='left')

    # Fill NaN values with 0 before further processing
    faf_regions['Inflow_Domestic'] = faf_regions['Inflow_Domestic'].fillna(0)
    faf_regions['Outflow_Domestic'] = faf_regions['Outflow_Domestic'].fillna(0)

    # Calculate the color metric based on selected inflows
    faf_regions['Weight'] = 0
    if in_flow and out_flow:
        faf_regions['Weight'] = faf_regions['Inflow_Domestic'].fillna(0) + faf_regions['Outflow_Domestic'].fillna(0)
    elif in_flow:
        faf_regions['Weight'] = faf_regions['Inflow_Domestic'].fillna(0)
    elif out_flow:
        faf_regions['Weight'] = faf_regions['Outflow_Domestic'].fillna(0)

    # Avoid casting errors by converting to integer safely
    faf_regions['Inflow_Domestic'] = faf_regions['Inflow_Domestic'].astype(int)
    faf_regions['Outflow_Domestic'] = faf_regions['Outflow_Domestic'].astype(int)

    # Initialize the base map
    fig = px.choropleth_mapbox(
        faf_regions,
        geojson=faf_regions.geometry,  # Use geometry from the GeoDataFrame
        locations=faf_regions.index,  # Use the index of the GeoDataFrame for locations
        color='Weight',  # Use the calculated weight for coloring
        color_continuous_scale="Greys",  # Use a red scale for tonnage visualization
        mapbox_style="white-bg",  # Set background to white
        zoom=3,  # Set zoom level
        center={"lat": 37.8, "lon": -96},  # Center on the US
        hover_name='cfs17_name',  # Show region name on hover
        hover_data=None
    )

    fig.update_traces(
        hovertemplate=(
            "FAF Zone: %{hovertext}<br><br>"
            "Weight (in thousand tons):<br>"
            "       Inflow: %{customdata[0]}<br>"
            "       Outflow: %{customdata[1]}<br>"
        ),
        hovertext=faf_regions['faf_zone'].astype(str) + " - " + faf_regions['cfs17_name'],
        customdata=faf_regions[[
            'Inflow_Domestic',
            'Outflow_Domestic'
        ]].values
    )

    fig.update_layout(
        margin={"r": 0, "t": 0, "l": 0, "b": 0},
        coloraxis_colorbar=dict(
            title="Tonnage",
            ticksuffix="k tons",
            lenmode="fraction",
            len=0.8,
        )
    )

    # fig.show()
    return fig


# test = load_demand_data()
# test = get_filtered_data(test, '011', 'all', 'all', 'all')
# update_faf_map(test, 1, 1)


def generate_mode_chart(data):
    """
        Creates a mode bar chart based on the given data

        :param data: DataFrame containing the FAF demand data.
        :return: A Plotly Figure object representing the mode bar chart.
        """
    # Group by mode and calculate the sum of tons
    mode_data = data.groupby('dms_mode')['tons'].sum().reset_index()

    # Sort by tons in ascending order
    mode_data = mode_data.sort_values(by='tons', ascending=True)

    # Map mode codes to mode names using the mode_mapping dictionary
    mappings = get_mappings()
    mode_mapping = mappings["mode"]
    mode_data['mode_name'] = mode_data['dms_mode'].map(mode_mapping)

    # Create the bar chart
    fig = go.Figure()

    fig.add_trace(go.Bar(
        y=mode_data['mode_name'],  # Transport modes as the y-axis
        x=mode_data['tons'],  # Values as the x-axis
        orientation='h',  # Horizontal bar chart
        text=mode_data['tons'].apply(lambda x: f"{x:,.0f}"),  # Add text labels with commas
        textposition='auto'  # Position text in bars
        # width=0.5
    ))

    # Customize layout
    fig.update_layout(
        title="Mode - Weight (in thousand tons)",
        xaxis=dict(
            showgrid=True,
            zeroline=True,
            # gridcolor='lightgrey',
            visible=False  # Remove x-axis labels like 0, 2M, 4M, etc.
        ),
        yaxis=dict(
            title=None,  # Remove the y-axis title
            showgrid=False
        ),
        plot_bgcolor='white',  # Set background color
        margin=dict(l=120, r=20, t=50, b=40),  # Adjust margins
        width=400  # Adjust the width of the chart
    )

    # fig.show()
    return fig


# test = load_demand_data()
# result = get_filtered_data(test, '011', 'all', 'all', 'all')
# generate_mode_chart(result)


def generate_commodity_chart(data):
    """
    Create a horizontal bar chart for the top 8 commodities by weight.

    Parameters:
        data (pd.DataFrame): DataFrame containing FAF demand data.

    Returns:
        fig (plotly.graph_objects.Figure): The generated bar chart.
    """
    # Aggregate and process the data
    commodity_data = data.groupby('sctg2')['tons'].sum().reset_index()
    commodity_data = commodity_data.sort_values(by='tons', ascending=True)

    # Map mode codes to mode names using the mode_mapping dictionary
    mappings = get_mappings()
    commodity_mapping = mappings["commodity"]
    commodity_data['commodity_name'] = commodity_data['sctg2'].map(commodity_mapping)

    # Select the top 8 commodities by weight
    commodity_data = commodity_data.tail(8)

    # Create the bar chart
    fig = go.Figure()

    fig.add_trace(go.Bar(
        y=commodity_data['commodity_name'],  # Commodity names as the y-axis
        x=commodity_data['tons'],  # Tons as the x-axis
        orientation='h',  # Horizontal bar chart
        text=commodity_data['tons'].apply(lambda x: f"{x:,.0f}"),  # Add text labels with commas
        textposition='auto'  # Position text in bars
    ))

    # Customize layout
    fig.update_layout(
        title="Commodity - Weight (in thousand tons)",
        xaxis=dict(
            showgrid=True,
            zeroline=True,
            gridcolor='lightgrey',
            visible=False  # Hide axis labels like 0, 2M, etc.
        ),
        yaxis=dict(
            title=None,  # Remove the y-axis title
            showgrid=False
        ),
        plot_bgcolor='white',  # Background color
        margin=dict(l=120, r=20, t=50, b=40),  # Adjust margins
        width=400  # Chart width
    )

    return fig
