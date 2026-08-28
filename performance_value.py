"""
Calculate fuel consumption (Btu/ton-mile), ghg emissions (g/ton-mile), and fuel prices ($/ton-mile)
Note:
    Truck, Rail uses low-sulfur diesel
    Water uses marine diesel oil: MDO (0.1% sulfur)
"""

import os
import pandas as pd
import geopandas as gpd

from shapely.geometry import Point
import geopy.distance

from util import PERFORMANCE_DIR, REGION_DIR

# Load region
REGION_DIRS = {
    "NERC_Regio": os.path.join(REGION_DIR, 'nerc', 'nerc_regions.shp'),
    "PADD_Regio": os.path.join(REGION_DIR, 'padd', 'padd_regions.shp'),
    "Census_Reg": os.path.join(REGION_DIR, 'census', 'census_regions.shp')
}
regions_gdfs = {key: gpd.read_file(path).to_crs(epsg=4326) for key, path in REGION_DIRS.items()}

# Load data file paths
fuel_consumption_file = os.path.join(PERFORMANCE_DIR, 'fuel_consumption_raw.xlsx')
fuel_characteristics_file = os.path.join(PERFORMANCE_DIR, 'fuel_characteristics.xlsx')
unit_conversion_file = os.path.join(PERFORMANCE_DIR, 'unit_conversion.xlsx')
ghg_factor_file = os.path.join(PERFORMANCE_DIR, 'ghg_factor.xlsx')
fuel_prices_file = os.path.join(PERFORMANCE_DIR, 'fuel_prices.xlsx')
commodity_energy_factor_file = os.path.join(PERFORMANCE_DIR, 'EI_Factor.xlsx')

# Read fuel characteristics data
fuel_LHV_data = pd.read_excel(fuel_characteristics_file, sheet_name='LHV_Btu_gal')
fuel_density_data = pd.read_excel(fuel_characteristics_file, sheet_name='Density_g_gal')
low_sulfur_diesel_LHV = fuel_LHV_data['low-sulfur diesel'].iloc[0]   # Btu/gal
biodiesel_LHV = fuel_LHV_data['biodiesel'].iloc[0]   # Btu/gal
hydrogen_LHV = fuel_LHV_data['liquid hydrogen'].iloc[0]   # Btu/gal
mdo_LHV = fuel_LHV_data['MDO'].iloc[0]   # Btu/gal
hydrogen_density = fuel_density_data['liquid hydrogen'].iloc[0]   # g/gal

# Read assumed vehicle operation data
fuel_consumption_assump = pd.read_excel(fuel_consumption_file, sheet_name='Assumption')
truck_payload = fuel_consumption_assump['truck_payload_ton'].iloc[0]   # ton
vessel_power_hp = fuel_consumption_assump['vessel_power_hp'].iloc[0]   # horsepower
vessel_speed_mph = fuel_consumption_assump['vessel_speed_mph'].iloc[0]   # mile/hour
vessel_payload_ton = fuel_consumption_assump['vessel_payload_ton'].iloc[0]   # ton
vessel_electricity_efficiency = fuel_consumption_assump['vessel_electricity_efficiency'].iloc[0]
vessel_hydrogen_efficiency = fuel_consumption_assump['vessel_hydrogen_efficiency'].iloc[0]

# Read ghg emission factor data
wtp_ghg_factor_data = pd.read_excel(ghg_factor_file, sheet_name='wtp')

# Read commodity data
commodity_energy_factor_data = pd.read_excel(commodity_energy_factor_file)

# Read unit conversion data
unit_conversion_data = pd.read_excel(unit_conversion_file)
hph2kWh = unit_conversion_data['hph2kWh'].iloc[0]
hph2Btu = unit_conversion_data['hph2Btu'].iloc[0]
Btu2mmBtu = unit_conversion_data['Btu2mmBtu'].iloc[0]
Btu2kWh = unit_conversion_data['Btu2kWh'].iloc[0]


def get_fuel_consumption(mode, fuel):
    """
    Get the fuel consumption value (Btu/ton-mile) given the mode and fuel technology
    :param mode: (str) 'short truck', 'long truck', 'rail', 'water'
    :param fuel: (str) 'diesel', 'biodiesel', 'electricity', 'hydrogen'
    :return: fuel consumption value (Btu/ton-mile)
    """

    mode_sheets = {
        'short truck': 'short_truck_mpg',
        'long truck': 'long_truck_mpg',
        'rail': 'rail_Btu_tmile',
        'water': 'water_Btu_kWh'
    }

    fuel_consumption_data = pd.read_excel(fuel_consumption_file, sheet_name=mode_sheets[mode])
    fuel_consumption_value = 0
    if mode in ['short truck', 'long truck']:
        fuel_consumption_value_raw = fuel_consumption_data[fuel].iloc[0]  # mile/gal
        # transfer fuel consumption to Btu/ton-mile
        fuel_consumption_value = low_sulfur_diesel_LHV / fuel_consumption_value_raw / truck_payload

    elif mode == 'rail':
        fuel_consumption_value = fuel_consumption_data[fuel].iloc[0]  # Btu/ton-mile

    elif mode == 'water':
        if fuel == 'diesel':
            fuel_consumption_value_raw = fuel_consumption_data['MDO'].iloc[0]  # Btu/kWh operation
            fuel_consumption_value = (vessel_power_hp * hph2kWh * fuel_consumption_value_raw
                                      / vessel_payload_ton / vessel_speed_mph)    # Btu/ton-mile
        elif fuel == 'biodiesel':
            fuel_consumption_value_raw = fuel_consumption_data['biodiesel'].iloc[0]  # Btu/kWh operation
            fuel_consumption_value = (vessel_power_hp * hph2kWh * fuel_consumption_value_raw
                                      / vessel_payload_ton / vessel_speed_mph)  # Btu/ton-mile
        elif fuel == 'electricity':
            fuel_consumption_value = (vessel_power_hp * hph2Btu / vessel_electricity_efficiency
                                      / vessel_payload_ton / vessel_speed_mph)  # Btu/ton-mile
        elif fuel == 'hydrogen':
            fuel_consumption_value = (vessel_power_hp * hph2Btu / vessel_hydrogen_efficiency
                                      / vessel_payload_ton / vessel_speed_mph)  # Btu/ton-mile

    return fuel_consumption_value


# # Example Use
# print(get_fuel_consumption('short truck', 'diesel'))
# print(get_fuel_consumption('short truck', 'electricity'))


def get_ghg_value(mode, fuel, electricity_GHG_region, hydrogen_pathway):
    """
    calculate the GHG emission value (gGHG/ton-mile)
    :param mode: (str) 'short truck', 'long truck', 'rail', 'water'
    :param fuel: (str) 'diesel', 'biodiesel', 'electricity', 'hydrogen'
    :param electricity_GHG_region: (str) 'ASCC', 'FRCC', 'HICC', 'MRO', 'NPCC', 'RFC', 'SERC', 'SPP', 'TRE', 'WECC', 'CA'
    :param hydrogen_pathway: (str) 'NG w/o CCS', 'NG w/ CCS', 'Electrolysis Solar', 'Electrolysis Nuclear'
    :return: WTP, PTW, and total ghg emission (g/ton-mile)
    """

    # get fuel consumption (Btu/ton-mile) for given mode and fuel
    fuel_consumption = get_fuel_consumption(mode, fuel)  # Btu/ton-mile

    # Get well-to-pump GHG emission factors (g/mmBtu)
    wtp_ghg_factor = 0
    if fuel == 'diesel':
        if mode in ['short truck', 'long truck', 'rail']:
            wtp_ghg_factor = wtp_ghg_factor_data[fuel].iloc[0]
        elif mode == 'water':
            wtp_ghg_factor = wtp_ghg_factor_data['MDO'].iloc[0]
    elif fuel == 'biodiesel':
        wtp_ghg_factor = wtp_ghg_factor_data[fuel].iloc[0]
    elif fuel == 'electricity':
        if electricity_GHG_region is None or f'electricity_{electricity_GHG_region}' not in wtp_ghg_factor_data.columns:
            wtp_ghg_factor = wtp_ghg_factor_data['electricity_US'].iloc[0]
        else:
            wtp_ghg_factor = wtp_ghg_factor_data[f'electricity_{electricity_GHG_region}'].iloc[0]
    elif fuel == 'hydrogen':
        if hydrogen_pathway == 'NG w/o CCS':
            wtp_ghg_factor = wtp_ghg_factor_data['hydrogen_NG_wo_CCS'].iloc[0]
        elif hydrogen_pathway == 'NG w/ CCS':
            wtp_ghg_factor = wtp_ghg_factor_data['hydrogen_NG_w_CCS'].iloc[0]
        elif hydrogen_pathway == 'Electrolysis Solar':
            wtp_ghg_factor = wtp_ghg_factor_data['hydrogen_ele_Solar'].iloc[0]
        elif hydrogen_pathway == 'Electrolysis Nuclear':
            wtp_ghg_factor = wtp_ghg_factor_data['hydrogen_ele_Nuclear'].iloc[0]

    # Calculate well-to-pump GHG emissions (gGHG/ton-mile)
    wtp_ghg_emission = fuel_consumption * wtp_ghg_factor * Btu2mmBtu

    # Get pump-to-wheel GHG emission factors (g/mmBtu)
    ptw_ghg_factor = 0
    mode_sheets = {
        'short truck': 'ptw_short_truck',
        'long truck': 'ptw_long_truck',
        'rail': 'ptw_rail',
        'water': 'ptw_water'
    }
    ptw_ghg_factor_data = pd.read_excel(ghg_factor_file, sheet_name=mode_sheets[mode])
    if fuel in ['diesel', 'biodiesel']:
        ptw_ghg_factor = ptw_ghg_factor_data[fuel].iloc[0]
    else:
        ptw_ghg_factor = 0

    # Calculate pump-to-wheel GHG emissions (gGHG/ton-mile)
    ptw_ghg_emission = fuel_consumption * ptw_ghg_factor * Btu2mmBtu

    # Calculate total GHG emission (gGHG/ton-mile): the sum of well-tp-pump and pump-to-wheel
    total_ghg_emission = wtp_ghg_emission + ptw_ghg_emission

    return total_ghg_emission


# # Example use
# print(get_ghg_value('long truck', 'electricity', 'CA', None))


def get_fuel_price(mode, fuel, diesel_price_region, electricity_price_region, hydrogen_pathway):
    """
    calculate the fuel price value ($/ton-mile)
    :param mode: (str) 'short truck', 'long truck', 'rail', 'water'
    :param fuel: (str) 'diesel', 'biodiesel', 'electricity', 'hydrogen'
    :param diesel_price_region: (str) for both diesel and biodiesel， None, or 'PADD 1A', 'PADD 1B', 'PADD 1C', 'PADD 2',
    'PADD 3', 'PADD 4', 'PADD 5'
    :param electricity_price_region: （str), None, or 'Region 1', 'Region 2', 'Region 3', ... 'Region 10'
    :param hydrogen_pathway: (str) 'NG w/o CCS', 'NG w/ CCS', 'Electrolysis Solar', 'Electrolysis Nuclear'
    :return: fuel price value ($/ton-mile)
    """

    # get fuel consumption (Btu/ton-mile) for given mode and fuel
    fuel_consumption = get_fuel_consumption(mode, fuel)  # Btu/ton-mile
    fuel_price = 0

    # diesel
    if fuel == 'diesel':
        diesel_price = 0
        diesel_price_data = pd.read_excel(fuel_prices_file, sheet_name='diesel_$_gal')
        if diesel_price_region is None or diesel_price_region not in diesel_price_data.columns:
            diesel_price = diesel_price_data['U.S.'].iloc[0]
        else:
            diesel_price = diesel_price_data[diesel_price_region].iloc[0]   # $/gal
        fuel_price = fuel_consumption / low_sulfur_diesel_LHV * diesel_price   # $/ton-mile

    elif fuel == 'biodiesel':
        biodiesel_price = 0
        biodiesel_price_data = pd.read_excel(fuel_prices_file, sheet_name='biodiesel_$_gal')
        if diesel_price_region is None or diesel_price_region not in biodiesel_price_data.columns:
            biodiesel_price = biodiesel_price_data['U.S.'].iloc[0]
        else:
            biodiesel_price = biodiesel_price_data[diesel_price_region].iloc[0]  # $/gal
        fuel_price = fuel_consumption / biodiesel_LHV * biodiesel_price    # $/ton-mile

    elif fuel == 'electricity':
        electricity_price = 0
        electricity_price_data = pd.read_excel(fuel_prices_file, sheet_name='electricity_c_kWh')
        if electricity_price_region is None or electricity_price_region not in electricity_price_data.columns:
            electricity_price = electricity_price_data['U.S. Total'].iloc[0]
        else:
            electricity_price = electricity_price_data[electricity_price_region].iloc[0]  # cent/kWh
        fuel_price = fuel_consumption * Btu2kWh * electricity_price * 0.01     # $/ton-mile

    elif fuel == 'hydrogen':
        hydrogen_price_data = pd.read_excel(fuel_prices_file, sheet_name='hydrogen_$_kg')
        hydrogen_price = hydrogen_price_data[hydrogen_pathway].iloc[0]  # $/kg
        fuel_price = fuel_consumption / hydrogen_LHV * hydrogen_density * hydrogen_price * 0.001  # $/ton-mile

    return fuel_price


# print(get_fuel_price('long truck', 'electricity', None, 'Region 6', None))

def get_metrics(point, fuel, mode, commodity):
    # Identify the regions
    temp_gdf = gpd.GeoDataFrame(geometry=[point], crs="EPSG:4326")

    # Default values
    diesel_price_region = None
    elec_ghg_region = None
    elec_price_region = None
    hydrogen_pathway = None

    # Identify PADD region for diesel and biodiesel fuel price calculations
    if fuel in ["diesel", "biodiesel"]:
        padd_region = gpd.sjoin(temp_gdf, regions_gdfs["PADD_Regio"][["PADD_Regio", "geometry"]], how="left",
                                predicate="within")
        diesel_price_region = padd_region['PADD_Regio'].iloc[0] if not padd_region.empty else None

    # Identify nerc region for electricity ghg emission, census region for electricity price
    if fuel == "electricity":
        # nerc region for ghg emission
        nerc_region = gpd.sjoin(temp_gdf, regions_gdfs["NERC_Regio"][["NERC_Regio", "geometry"]], how="left",
                                predicate="within")
        elec_ghg_region = nerc_region["NERC_Regio"].iloc[0] if not nerc_region.empty else None
        ghg_per_ton_mile = get_ghg_value(mode, fuel, elec_ghg_region, hydrogen_pathway)

        # census region for price
        census_region = gpd.sjoin(temp_gdf, regions_gdfs["Census_Reg"][["Census_Reg", "geometry"]], how="left",
                                  predicate="within")
        elec_price_region = census_region['Census_Reg'].iloc[0] if not census_region.empty else None
        price_per_ton_mile = get_fuel_price(mode, fuel, diesel_price_region, elec_price_region, hydrogen_pathway)

    if fuel in ['NG w/o CCS', 'NG w/ CCS', 'Electrolysis Solar', 'Electrolysis Nuclear']:
        hydrogen_pathway = fuel
        fuel = 'hydrogen'

    ghg_base_per_ton_mile = get_ghg_value(mode, fuel, elec_ghg_region, hydrogen_pathway)
    price_base_per_ton_mile = get_fuel_price(mode, fuel, diesel_price_region, elec_price_region, hydrogen_pathway)
    commodity_factor = \
    commodity_energy_factor_data.loc[commodity_energy_factor_data["commodity_group"] == commodity, mode].values[0]

    ghg_per_ton_mile = ghg_base_per_ton_mile * commodity_factor
    price_per_ton_mile = price_base_per_ton_mile * commodity_factor

    return ghg_per_ton_mile, price_per_ton_mile
