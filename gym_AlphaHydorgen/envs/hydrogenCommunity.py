import gym
from gym import error, spaces, utils
from gym.utils import seeding
from gym_AlphaBuilding.envs.other_heat_gain import get_intHG_schd, get_solarHG_schd

import pandas as pd
import numpy as np

from model import *

class AlphaResEnv(gym.Env):
    """ AlphaHydorgen is a custom Gym Environment to simulate a community equiped with on-site renewables,
    hydrogen station, hydrogen vehicles and smart grid
    ------------------------------------------------------------------------------------------------------
    Args:
        - stepLenth: length of time step, unit: s
        - building_list: a list of buildings, each element in the list is a tuple of (buildingLoad.csv, number of buildings)
            example: [('inputs/building1.csv', 10), ('inputs/building2.csv', 10), ('inputs/building3.csv', 10)]
        - pv_list: a list of on-site pvs, each element in the list is a tuple of (pvGeneration.csv, number of PVs)
            example: [('inputs/pv1.csv', 10), ('inputs/pv2.csv', 10), ('inputs/pv3.csv', 10)]
        - vehicle_list: a list of hydrogen vehicles, 
            first element is parkSchedule.csv, 
            the remaining elements in the list are tuples of 
                (vehicleParameter.csv, fuelCellEff, fuelCellCap, number of vehicles)
            example: ['inputs/vehicle_atHomeSchd.csv', ('inputs/vehicle1.csv', 100, 300, 10), 
                      ('inputs/vehicle2.csv', 100, 300, 10), ('inputs/vehicle3.csv', 100, 300, 10)]
        - h2Station: a dictionary of hydrogen station parameters
            example: {'pipeChargingCapacity':60*1000,
                      'vehicleDischargingCapacity':1000,
                      'storageCapacity':1000*1000,
                      'electrolyzerEff':0.01,
                      'electrolyzerCapacity':10}
    ------------------------------------------------------------------------------------------------------
    States:
        - buildingLoad: total building load of the community, [kW]
        - pvGeneration: total on-site PV generation, [kW] 
        - vehicle_park: binary variable, whether the vechile is parked at home or not
        - vehicle_dist: travel distance of today, [km]
        - vehicle_tank: hydorgen stored in the vehicle's tank, [g]
        - station_tank: hydorgen stored in the station's tank, [g]
    ------------------------------------------------------------------------------------------------------
    Actions:
        - 